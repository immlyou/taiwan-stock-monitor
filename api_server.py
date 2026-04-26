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

from api.deps import API_KEY
from api.response import SafeJSONResponse
from api.state import loader
from core.data_loader import FinLabQuotaExceededError

# ── Router 匯入 ──────────────────────────────────────────
from api.routers import (
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
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
_cors_allow_credentials = _cors_origins != ["*"]


# ── Lifespan：startup 警告 + 資料預熱 ───────────────────
@asynccontextmanager
async def _lifespan(app: FastAPI):
    _log = logging.getLogger(__name__)

    if not API_KEY:
        _log.warning(
            "STOCK_API_KEY 環境變數未設定——所有 API 端點無需認證即可存取。"
            " 生產環境請務必設定此變數。"
        )
    if not _cors_allow_credentials:
        _log.warning(
            "CORS_ORIGINS 未設定或為 '*'，已停用 allow_credentials。"
            " 生產環境請設定 CORS_ORIGINS 為具體域名。"
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

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load)

    yield


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
    scanner_router,      # /scanner/*
    market_router,       # /market/*
    stock_router,        # /stock/{id}/*
    strategy_router,     # /strategy/*
    ai_router,           # /ai/*
    screener_router,     # /screener
    backtest_router,     # /backtest/*
    optimizer_router,    # /optimizer/*
    reports_router,      # /morning-report
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
