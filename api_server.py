#!/usr/bin/env python3
"""台股戰情中心 API Server

精簡的 FastAPI 進入點。所有端點由 api/routers/ 底下的子模組提供，
這個檔案只負責：
- 建立 FastAPI app（含 SafeJSONResponse、lifespan、CORS、GZip）
- FinLabQuotaExceededError 的全域 exception handler
- 掛載所有 APIRouter
- uvicorn 啟動 CLI

啟動方式:
    python api_server.py
    python api_server.py --host 0.0.0.0 --port 8000

API 文件:
    啟動後訪問 http://localhost:8000/docs
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.deps import API_KEY, IS_CLOUD
from api.response import SafeJSONResponse
from api.state import loader
from core.data_loader import FinLabQuotaExceededError

# ── Router 匯入 ──────────────────────────────────────────
from api.routers import (
    advisor as advisor_router,
    ai as ai_router,
    alerts as alerts_router,
    backtest as backtest_router,
    dashboard as dashboard_router,
    journal as journal_router,
    market as market_router,
    news as news_router,
    optimizer as optimizer_router,
    portfolios as portfolios_router,
    predictions as predictions_router,
    quote as quote_router,
    radar as radar_router,
    reports as reports_router,
    risk as risk_router,
    saved_strategies as saved_strategies_router,
    scanner as scanner_router,
    screener as screener_router,
    settings as settings_router,
    social as social_router,
    stock as stock_router,
    stocks as stocks_router,
    strategy as strategy_router,
    system as system_router,
    watchlists as watchlists_router,
)

logger = logging.getLogger(__name__)


# ── CORS 設定 ───────────────────────────────────────────
# 雲端環境未設定 CORS_ORIGINS 時預設「拒絕所有跨域」（fail-closed）。
# 瀏覽器流量一律走 Next.js 的 /api proxy（server-to-server，不經 CORS），
# 因此雲端不需要開放任何跨域來源；本地開發才預設 '*'。
_cors_origins_raw = os.getenv("CORS_ORIGINS", "" if IS_CLOUD else "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
_cors_allow_credentials = bool(_cors_origins) and _cors_origins != ["*"]


# ── Lifespan：startup 警告 + 資料預熱 ───────────────────
@asynccontextmanager
async def _lifespan(app: FastAPI):
    _log = logging.getLogger(__name__)

    if not API_KEY:
        if IS_CLOUD:
            _log.error(
                "STOCK_API_KEY 未設定且偵測到雲端環境——"
                "所有受保護端點將回 503（fail-closed）。"
                "請在 Railway 設定 STOCK_API_KEY 後重新部署。"
            )
        else:
            _log.warning(
                "STOCK_API_KEY 環境變數未設定——本地開發模式，"
                "所有 API 端點無需認證即可存取。"
            )
    if not _cors_allow_credentials:
        _log.warning(
            "CORS_ORIGINS 未設定（雲端預設拒絕所有跨域；本地預設 '*'）。"
            " 若需瀏覽器直連後端，請設定 CORS_ORIGINS 為具體域名。"
        )

    # 資料預熱：把常用資料集預先載入快取
    from core.data_loader import DataCache, FINLAB_CACHE_TTL

    preload_keys = [
        'close', 'open', 'high', 'low', 'volume',
        'pe_ratio', 'pb_ratio', 'dividend_yield',
        'revenue_yoy', 'market_value', 'categories',
        'foreign_investors', 'investment_trust', 'dealer',
    ]

    def _load():
        cache = DataCache()
        skipped = loaded = failed = 0
        for key in preload_keys:
            if cache.has(key, max_age=FINLAB_CACHE_TTL if FINLAB_CACHE_TTL > 0 else 0):
                skipped += 1
                continue
            try:
                loader.get(key)
                loaded += 1
            except Exception as e:
                _log.warning("預熱 %s 失敗: %s", key, e)
                failed += 1
        _log.info(
            "資料預熱完成 — 新載入: %d，快取命中跳過: %d，失敗: %d",
            loaded, skipped, failed,
        )

        # 預熱全市場評分表（memoized）：讓 smart-preview / advisor / radar 第一次
        # 請求就命中快取，避免冷啟動重算 ~2300 檔評分（原本 ~23s）而超過前端 timeout。
        try:
            from core.stock_score import calculate_score_table
            calculate_score_table(loader)
            _log.info("評分表預熱完成")
        except Exception as e:
            _log.warning("評分表預熱失敗: %s", e)

        # 預熱評分歷史的近 20 日各日全市場評分表（memoized、跨股票共用）。
        # 用一檔代表股觸發即可填滿日表快取，避免使用者第一次開個股頁時 score-history
        # 重算 20 份全市場表（~50s，且前端 10s timeout 會 abort 而永遠無法暖快取）。
        try:
            from core.intelligence import calculate_score_history
            calculate_score_history(loader, "2330", days=20)
            _log.info("評分歷史日表預熱完成")
        except Exception as e:
            _log.warning("評分歷史預熱失敗: %s", e)

        # 預熱每日晨報（冷啟動 ~18s：3 策略 + 新聞掃描，會超過前端 timeout）。
        try:
            from api.routers.reports import warm_morning_report
            warm_morning_report()
            _log.info("每日晨報預熱完成")
        except Exception as e:
            _log.warning("每日晨報預熱失敗: %s", e)

        # 預熱操盤雷達重端點（backtest 冷啟動 ~15s、notifications ~3.7s）。
        try:
            from api.routers.radar import warm_radar
            warm_radar()
            _log.info("操盤雷達預熱完成")
        except Exception as e:
            _log.warning("操盤雷達預熱失敗: %s", e)

    # 資料預熱改為「背景非阻塞」執行。
    # 雲端（Railway）走 FinLab API 模式時，預熱會逐一下載多個全市場大資料集；
    # 若在此 await，會阻塞 app startup 與 /health healthcheck，導致 Railway 判定
    # 啟動失敗而回 502。改為背景執行後 app 立即可服務，資料邊載入邊就緒（含快取）。
    def _safe_load() -> None:
        try:
            _load()
        except Exception:  # noqa: BLE001 — 背景任務不可讓例外逸出
            _log.exception("背景資料預熱發生未預期錯誤")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _safe_load)  # 不 await：背景預熱，不阻塞啟動

    # 背景排程器：盤中自動警報檢查（環境開關 ENABLE_SCHEDULER；雲端預設開）。
    # 在獨立執行緒運作，不阻塞啟動與 /health。
    try:
        from core.scheduler import start_scheduler
        start_scheduler()
    except Exception:  # noqa: BLE001 — 排程啟動失敗不可拖垮整個 app
        _log.exception("排程器啟動失敗")

    yield

    # ── 關閉：停掉排程器 ─────────────────────────────────
    try:
        from core.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:  # noqa: BLE001
        _log.exception("排程器關閉失敗")


# ── App 建構 ────────────────────────────────────────────
app = FastAPI(
    title="台股戰情中心 API",
    description="提供台股數據查詢、選股策略、警報等功能，供 Next.js 前端及外部系統串接",
    version="2.0.0",
    default_response_class=SafeJSONResponse,
    lifespan=_lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception handler：FinLab 額度超限時不回 500 ──────
@app.exception_handler(FinLabQuotaExceededError)
async def finlab_quota_handler(request: Request, exc: FinLabQuotaExceededError) -> Response:
    return SafeJSONResponse(
        status_code=503,
        content={
            "status": "quota_exceeded",
            "error": (
                "FinLab API 每日額度已達上限（5,000 MB/日），已自動切換備用資料來源。"
                "部分資料可能暫時無法顯示，額度將於午夜重置。"
            ),
            "fallback_active": True,
        },
    )


# ── Router 掛載 ─────────────────────────────────────────
for _router_module in (
    system_router,       # /, /health
    news_router,         # /news/*
    social_router,       # /social/*
    watchlists_router,   # /watchlists/*
    journal_router,      # /journal/*
    alerts_router,       # /alerts/*
    dashboard_router,    # /dashboard/*
    portfolios_router,   # /portfolios/*
    predictions_router,  # /predictions/*
    saved_strategies_router,  # /strategies/saved/*
    settings_router,     # /settings
    stocks_router,       # /stocks/list, /search, /active, /compare
    quote_router,        # /quote/realtime/*
    risk_router,         # /risk/*
    radar_router,        # /radar/*
    scanner_router,      # /scanner/*
    market_router,       # /market/*
    stock_router,        # /stock/{id}/*
    strategy_router,     # /strategy/*
    ai_router,           # /ai/*
    screener_router,     # /screener
    backtest_router,     # /backtest/*
    optimizer_router,    # /optimizer/*
    reports_router,      # /morning-report
    advisor_router,      # /advisor/*
):
    app.include_router(_router_module.router)


# ── CLI 啟動 ────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台股戰情中心 API Server")
    parser.add_argument("--host", default="0.0.0.0", help="綁定 Host (預設 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="綁定 Port (預設 8000)")
    parser.add_argument("--reload", action="store_true", help="開發模式 (自動重載)")
    args = parser.parse_args()

    print("台股戰情中心 API 啟動中...")
    print(f"    http://{args.host}:{args.port}")
    print(f"    API 文件: http://{args.host}:{args.port}/docs")
    print(f"    API Key: {'已設定' if API_KEY else '未設定 (開放存取)'}")

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
