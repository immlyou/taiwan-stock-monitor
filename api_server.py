#!/usr/bin/env python3
"""
台股戰情中心 API Server
========================
提供 REST API 讓 Next.js 前端或外部系統串接查詢台股數據。

啟動方式:
    python api_server.py
    python api_server.py --host 0.0.0.0 --port 8000

API 文件:
    啟動後訪問 http://localhost:8000/docs
"""
import os
import json
import uuid
import time
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from functools import wraps
from enum import Enum

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
import uvicorn
import pandas as pd
import numpy as np
import json as _json
import math

# API 層模組（從 api_server.py 拆分）
from api.response import SafeJSONResponse
from api.deps import verify_api_key, security, API_KEY
from api.state import loader, multi_source, DATA_DIR
from api.helpers import (
    _safe_json,
    _get_stock_latest,
    _load_json_file,
    _save_json_file,
    _get_stock_name_map,
    _get_industry_map,
    cached_response,
)
from api.routers import system as system_router
from api.routers import news as news_router
from api.routers import social as social_router
from api.routers import watchlists as watchlists_router
from api.routers import journal as journal_router
from api.routers import alerts as alerts_router
from api.routers import portfolios as portfolios_router
from api.routers import predictions as predictions_router
from api.routers import saved_strategies as saved_strategies_router
from api.routers import settings as settings_router
from api.routers import stocks as stocks_router
from api.routers import quote as quote_router

from config import STRATEGY_PARAMS, TRADING_COSTS, BACKTEST_DEFAULTS
from core.data_loader import get_data_summary, get_active_stocks, FinLabQuotaExceededError
from core.indicators import (
    calculate_rsi, calculate_macd, calculate_sma, calculate_ema,
    calculate_bollinger_bands, calculate_kdj, calculate_atr,
    calculate_bias, calculate_williams_r, calculate_cci,
)
from core.alerts import AlertEngine
from core.strategies.value import ValueStrategy
from core.strategies.growth import GrowthStrategy
from core.strategies.momentum import MomentumStrategy

# ─── Lifespan（取代已 deprecated 的 @app.on_event）────────
@asynccontextmanager
async def _lifespan(app: FastAPI):
    """應用程式生命週期：startup → yield → shutdown"""
    import logging as _logging
    _log = _logging.getLogger(__name__)

    # ── startup ──
    # 1. 安全設定警告
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

    # 2. 資料預熱
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

    yield  # 應用程式運行中

    # ── shutdown（如有需要可在此清理資源）──


# ─── 初始化 ─────────────────────────────────────────────
app = FastAPI(
    title="台股戰情中心 API",
    description="提供台股數據查詢、選股策略、警報等功能，供 Next.js 前端及外部系統串接",
    version="2.0.0",
    default_response_class=SafeJSONResponse,
    lifespan=_lifespan,
)

import logging

logger = logging.getLogger(__name__)

# CORS 設定：從環境變數讀取允許的來源（逗號分隔），預設為 "*"
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
_cors_allow_credentials = _cors_origins != ["*"]

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全域 FinLab 額度超限 handler — 攔截所有端點中的 FinLabQuotaExceededError
from starlette.requests import Request
from starlette.responses import Response

@app.exception_handler(FinLabQuotaExceededError)
async def finlab_quota_handler(request: Request, exc: FinLabQuotaExceededError) -> Response:
    """當 FinLab 額度超限時，回傳友善訊息而非 500"""
    return SafeJSONResponse(
        status_code=503,
        content={
            "status": "quota_exceeded",
            "error": "FinLab API 每日額度已達上限（5,000 MB/日），已自動切換備用資料來源。部分資料可能暫時無法顯示，額度將於午夜重置。",
            "fallback_active": True,
        },
    )

# cached_response / loader / multi_source / DATA_DIR 從 api.helpers 與 api.state
# 引入（見上方 imports）。舊定義已搬遷至 api/ 套件。




# ─── 工具函數 已搬遷至 api/helpers.py ───────────────────


# ─── Pydantic Models 已搬遷至 api/models.py ─────────────
from api.models import (
    HoldingItem,
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    WatchlistCreateRequest,
    WatchlistUpdateRequest,
    JournalEntryRequest,
    AlertCreateRequest,
    BacktestRequest,
    PredictionRequest,
    StrategyCreateRequest,
    PortfolioRiskRequest,
    SettingsUpdateRequest,
    NewsSentimentRequest,
    JournalReviewRequest,
    StockChatRequest,
    PostMarketSummaryRequest,
)


# ─── API 端點 ───────────────────────────────────────────

# 系統 router (/、/health) 已抽出到 api/routers/system.py
app.include_router(system_router.router)
app.include_router(news_router.router)
app.include_router(social_router.router)
app.include_router(watchlists_router.router)
app.include_router(journal_router.router)
app.include_router(alerts_router.router)
app.include_router(portfolios_router.router)
app.include_router(predictions_router.router)
app.include_router(saved_strategies_router.router)
app.include_router(settings_router.router)
app.include_router(stocks_router.router)
app.include_router(quote_router.router)


# ════════════════════════════════════════════════════════
# 第一批：通用 + 市場資料
# ════════════════════════════════════════════════════════


# /stocks/list, /stocks/search, /stocks/active 已抽出到 api/routers/stocks.py


@app.get("/market/summary", tags=["市場"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=60)
async def market_summary():
    """
    市場總覽 - 取得大盤指數、上漲/下跌家數等摘要資訊。
    OpenClaw 可用此端點取得每日市場概況。
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用 TWSE 大盤指數 ──
    if _finlab_quota_exceeded:
        logger.info("[market_summary] FinLab 額度超限，走 TWSE fallback")
        from core.twse_api import fetch_taiex_realtime
        taiex = fetch_taiex_realtime()
        return {
            "date": taiex.get("date") if taiex else datetime.now().strftime("%Y-%m-%d"),
            "taiex_index": taiex.get("index") if taiex else None,
            "taiex_change": taiex.get("change") if taiex else None,
            "total_stocks": None,
            "up_count": None,
            "down_count": None,
            "flat_count": None,
            "top_gainers": [],
            "top_losers": [],
            "source": "twse",
            "note": "FinLab 額度超限，僅提供大盤指數",
        }

    summary = get_data_summary()
    if "error" in summary:
        raise HTTPException(status_code=500, detail=summary["error"])

    close = loader.get("close")
    active = get_active_stocks()

    latest = close[active].iloc[-1]
    prev = close[active].iloc[-2]
    changes = (latest - prev) / prev * 100

    up_count = int((changes > 0).sum())
    down_count = int((changes < 0).sum())
    flat_count = int((changes == 0).sum())

    top_gainers = changes.nlargest(10)
    top_losers = changes.nsmallest(10)

    return {
        "date": summary.get("latest_date"),
        "taiex_index": _safe_json(summary.get("taiex_index")),
        "taiex_change": _safe_json(summary.get("taiex_change")),
        "total_stocks": summary.get("total_stocks"),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "top_gainers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_gainers.items()
        ],
        "top_losers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_losers.items()
        ],
    }


@app.get("/market/heatmap", tags=["市場"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def market_heatmap():
    """
    市場熱力圖資料 - 依產業分組，顯示各股漲跌幅。

    回傳每支活躍股票的漲跌幅及產業分類，供前端繪製熱力圖。
    """
    try:
        close = loader.get("close")
        active = get_active_stocks()
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()

        latest = close[active].iloc[-1]
        prev = close[active].iloc[-2]
        changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

        # 依產業分組
        industry_groups: Dict[str, list] = {}
        for sid in active:
            industry = industry_map.get(sid, "其他")
            raw_price = latest.get(sid, 0)
            raw_change = changes.get(sid, 0)
            # 防止 NaN/inf 導致 JSON 序列化失敗
            price = 0.0 if (pd.isna(raw_price) or np.isinf(raw_price)) else float(raw_price)
            change = 0.0 if (pd.isna(raw_change) or np.isinf(raw_change)) else float(raw_change)
            if price <= 0:
                continue
            if industry not in industry_groups:
                industry_groups[industry] = []
            industry_groups[industry].append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "price": round(price, 2),
                "change_pct": round(change, 2),
            })

        return {
            "date": close.index[-1].strftime("%Y-%m-%d"),
            "industries": [
                {"industry": ind, "stocks": stocks}
                for ind, stocks in sorted(industry_groups.items())
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/money-flow", tags=["市場"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def market_money_flow():
    """
    市場資金流向 - 三大法人買賣超統計。

    回傳外資、投信、自營商的整體買賣超金額與最活躍標的。
    """
    try:
        result = {
            "date": None,
            "foreign": {"total_net": 0, "top_buy": [], "top_sell": []},
            "investment_trust": {"total_net": 0, "top_buy": [], "top_sell": []},
            "dealer": {"total_net": 0, "top_buy": [], "top_sell": []},
        }

        name_map = _get_stock_name_map()

        for key, label in [
            ("foreign_investors", "foreign"),
            ("investment_trust", "investment_trust"),
            ("dealer", "dealer"),
        ]:
            try:
                df = loader.get(key)
                latest = df.iloc[-1].dropna()
                if result["date"] is None:
                    result["date"] = df.index[-1].strftime("%Y-%m-%d")
                result[label]["total_net"] = _safe_json(latest.sum())
                top_buy = latest.nlargest(10)
                top_sell = latest.nsmallest(10)
                result[label]["top_buy"] = [
                    {"stock_id": sid, "name": name_map.get(sid, ""), "net_shares": int(v)}
                    for sid, v in top_buy.items() if v > 0
                ]
                result[label]["top_sell"] = [
                    {"stock_id": sid, "name": name_map.get(sid, ""), "net_shares": int(v)}
                    for sid, v in top_sell.items() if v < 0
                ]
            except Exception:
                pass

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/after-hours", tags=["市場"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def market_after_hours():
    """
    盤後總覽 - 含市場統計與三大策略 AI 選股結果。

    整合當日收盤數據與 value / growth / momentum 策略各取前 5 名。
    """
    try:
        close = loader.get("close")
        active = get_active_stocks()

        latest = close[active].iloc[-1]
        prev = close[active].iloc[-2]
        changes = ((latest - prev) / prev * 100).dropna()
        name_map = _get_stock_name_map()

        top_gainers = changes.nlargest(5)
        top_losers = changes.nsmallest(5)

        strategies_summary = {}
        for stype in ("value", "growth", "momentum"):
            try:
                resp = await run_strategy(stype, preset="standard", top_n=5)
                strategies_summary[stype] = {
                    "total": resp["total_matches"],
                    "top5": [
                        {"stock_id": s["stock_id"], "name": name_map.get(s["stock_id"], "")}
                        for s in resp["stocks"][:5]
                    ],
                }
            except Exception:
                strategies_summary[stype] = {"total": 0, "top5": []}

        # 大盤指數
        taiex_data = {}
        try:
            benchmark = loader.get_benchmark()
            if benchmark is not None and len(benchmark) >= 2:
                taiex_close = float(benchmark.iloc[-1])
                taiex_prev = float(benchmark.iloc[-2])
                taiex_change = taiex_close - taiex_prev
                taiex_change_pct = (taiex_change / taiex_prev * 100) if taiex_prev != 0 else 0
                taiex_data = {
                    "close": round(taiex_close, 2),
                    "change": round(taiex_change, 2),
                    "change_pct": round(taiex_change_pct, 2),
                }
        except Exception:
            pass

        # 三大法人
        institutional_data = {}
        for key, label in [("foreign_investors", "foreign"), ("investment_trust", "trust"), ("dealer", "dealer")]:
            try:
                df = loader.get(key)
                net = float(df.iloc[-1].dropna().sum())
                institutional_data[label] = {"total_net": _safe_json(net)}
            except Exception:
                institutional_data[label] = {"total_net": 0}

        return {
            "date": close.index[-1].strftime("%Y-%m-%d"),
            "taiex": taiex_data,
            "institutional": institutional_data,
            "market": {
                "up": int((changes > 0).sum()),
                "down": int((changes < 0).sum()),
                "flat": int((changes == 0).sum()),
            },
            "top_gainers": [
                {"stock_id": sid, "name": name_map.get(sid, ""), "change_pct": round(float(pct), 2)}
                for sid, pct in top_gainers.items()
            ],
            "top_losers": [
                {"stock_id": sid, "name": name_map.get(sid, ""), "change_pct": round(float(pct), 2)}
                for sid, pct in top_losers.items()
            ],
            "ai_picks": strategies_summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/benchmark", tags=["市場"], dependencies=[Depends(verify_api_key)])
async def market_benchmark(
    days: int = Query(default=252, ge=20, le=1260, description="取得最近 N 個交易日"),
):
    """
    大盤指數時序資料。

    回傳加權股價報酬指數歷史數據，供前端繪製大盤走勢圖。
    """
    try:
        benchmark = loader.get_benchmark()
        series = benchmark.dropna().tail(days)
        start_val = float(series.iloc[0])
        return {
            "days": days,
            "start_date": series.index[0].strftime("%Y-%m-%d"),
            "end_date": series.index[-1].strftime("%Y-%m-%d"),
            "latest_value": _safe_json(series.iloc[-1]),
            "total_return_pct": round((float(series.iloc[-1]) / start_val - 1) * 100, 2),
            "data": [
                {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                for d, v in series.items()
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/industries", tags=["市場"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def market_industries():
    """
    產業列表與各產業統計。

    回傳所有產業分類及其包含的股票數量、當日漲跌幅平均值。
    """
    try:
        active = get_active_stocks()
        close = loader.get("close")
        industry_map = _get_industry_map()
        name_map = _get_stock_name_map()

        latest = close[active].iloc[-1]
        prev = close[active].iloc[-2]
        changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

        industry_stats: Dict[str, Dict] = {}
        for sid in active:
            ind = industry_map.get(sid, "其他")
            if ind not in industry_stats:
                industry_stats[ind] = {"count": 0, "changes": []}
            industry_stats[ind]["count"] += 1
            chg = float(changes.get(sid, 0) or 0)
            industry_stats[ind]["changes"].append(chg)

        industries = []
        for ind, stats in sorted(industry_stats.items()):
            chgs = stats["changes"]
            avg_chg = sum(chgs) / len(chgs) if chgs else 0
            up_count = sum(1 for c in chgs if c > 0)
            industries.append({
                "industry": ind,
                "stock_count": stats["count"],
                "avg_change_pct": round(avg_chg, 2),
                "up_count": up_count,
                "down_count": stats["count"] - up_count,
            })

        return {
            "date": close.index[-1].strftime("%Y-%m-%d"),
            "total_industries": len(industries),
            "industries": industries,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════
# 個股查詢（原有端點保持不變）
# ════════════════════════════════════════════════════════

@app.get("/stock/{stock_id}", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_info(
    stock_id: str,
    days: int = Query(default=5, description="取得最近 N 天的資料", ge=1, le=250),
):
    """
    個股基本資訊與近期行情。
    範例: /stock/2330?days=10
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用替代來源 ──
    if _finlab_quota_exceeded:
        logger.info("[stock_info] FinLab 額度超限，走 fallback: %s", stock_id)
        return await _stock_info_fallback(stock_id, days)

    try:
        close = loader.get("close")
    except FinLabQuotaExceededError:
        logger.warning("[stock_info] FinLab quota hit, switching to fallback: %s", stock_id)
        return await _stock_info_fallback(stock_id, days)
    if stock_id not in close.columns:
        # Fallback: 嘗試從 Goodinfo 取得資料（支援興櫃等 FinLab 不涵蓋的股票）
        return await _goodinfo_stock_fallback(stock_id)

    price_data = close[stock_id].dropna().tail(days)
    latest_price = float(price_data.iloc[-1])
    prev_price = float(price_data.iloc[-2]) if len(price_data) >= 2 else latest_price
    change_pct = round((latest_price - prev_price) / prev_price * 100, 2)

    pe = pb = dy = None
    try:
        pe_df = loader.get("pe_ratio")
        if stock_id in pe_df.columns:
            pe = _safe_json(pe_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass
    try:
        pb_df = loader.get("pb_ratio")
        if stock_id in pb_df.columns:
            pb = _safe_json(pb_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass
    try:
        dy_df = loader.get("dividend_yield")
        if stock_id in dy_df.columns:
            dy = _safe_json(dy_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    rev_yoy = None
    try:
        yoy_df = loader.get("revenue_yoy")
        if stock_id in yoy_df.columns:
            rev_yoy = _safe_json(yoy_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    name_map = _get_stock_name_map()
    industry_map = _get_industry_map()

    return {
        "stock_id": stock_id,
        "name": name_map.get(stock_id, ""),
        "industry": industry_map.get(stock_id, ""),
        "latest_price": round(latest_price, 2),
        "change_pct": change_pct,
        "date": price_data.index[-1].strftime("%Y-%m-%d"),
        "pe_ratio": pe,
        "pb_ratio": pb,
        "dividend_yield": dy,
        "revenue_yoy": rev_yoy,
        "price_history": [
            {
                "date": d.strftime("%Y-%m-%d"),
                "price": round(float(p), 2),
            }
            for d, p in price_data.items()
        ],
    }


async def _goodinfo_ohlcv_fallback(stock_id: str, days: int = 120):
    """Goodinfo OHLCV fallback：從 Goodinfo 取得歷史價格"""
    from core.goodinfo import fetch_ohlcv
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, fetch_ohlcv, stock_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    # 只取最近 days 筆
    records = records[-days:]
    return {
        "stock_id": stock_id,
        "days": len(records),
        "data": records,
        "source": "goodinfo",
    }


async def _goodinfo_stock_fallback(stock_id: str):
    """Goodinfo fallback：用於 FinLab 不涵蓋的股票（如興櫃）"""
    from core.goodinfo import fetch_stock_detail
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, fetch_stock_detail, stock_id)
    if not data or "price" not in data:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "stock_id": stock_id,
        "name": data.get("name", ""),
        "industry": data.get("industry", ""),
        "latest_price": data.get("price"),
        "change_pct": data.get("change_pct"),
        "date": today,
        "pe_ratio": data.get("per"),
        "pb_ratio": data.get("pbr"),
        "dividend_yield": data.get("dividend_yield"),
        "revenue_yoy": None,
        "price_history": [{"date": today, "price": data.get("price")}] if data.get("price") else [],
        "source": "goodinfo",
        "market": data.get("market", ""),
    }


async def _stock_info_fallback(stock_id: str, days: int):
    """stock_info 的 fallback 實作: yfinance + FinMind"""
    # 價格來自 yfinance
    ohlcv = multi_source.get_ohlcv(stock_id, days)
    if not ohlcv or not ohlcv.get("data"):
        raise HTTPException(status_code=503, detail="FinLab 額度超限且 fallback 來源無資料")

    price_history = ohlcv["data"]
    latest = price_history[-1]
    prev = price_history[-2] if len(price_history) >= 2 else latest
    latest_price = latest.get("close") or 0
    prev_price = prev.get("close") or latest_price
    change_pct = round((latest_price - prev_price) / prev_price * 100, 2) if prev_price else 0

    # 基本面來自 FinMind
    fund = multi_source.get_fundamentals(stock_id)
    pe = fund.get("pe_ratio") if fund else None
    pb = fund.get("pb_ratio") if fund else None
    dy = fund.get("dividend_yield") if fund else None

    # 即時報價取得股票名稱
    quote = multi_source.get_realtime_quote(stock_id)
    name = quote.get("name", "") if quote else ""

    return {
        "stock_id": stock_id,
        "name": name,
        "industry": "",
        "latest_price": round(latest_price, 2),
        "change_pct": change_pct,
        "date": latest.get("date", ""),
        "pe_ratio": pe,
        "pb_ratio": pb,
        "dividend_yield": dy,
        "revenue_yoy": None,
        "price_history": [
            {"date": r["date"], "price": round(r.get("close") or 0, 2)}
            for r in price_history
        ],
        "source": "fallback",
    }


@app.get("/stock/{stock_id}/technical", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_technical(stock_id: str):
    """
    個股技術指標：RSI、MACD、均線（最新一筆快照）。
    範例: /stock/2330/technical
    """
    close = loader.get("close")
    if stock_id not in close.columns:
        # Fallback: 用 Goodinfo OHLCV 計算技術指標
        return await _goodinfo_technical_fallback(stock_id)

    series = close[stock_id].dropna()

    rsi_14 = calculate_rsi(series, period=14)
    latest_rsi = _safe_json(rsi_14.iloc[-1]) if len(rsi_14) > 0 else None

    macd_line, signal_line, histogram = calculate_macd(series)
    latest_macd = _safe_json(macd_line.iloc[-1]) if len(macd_line) > 0 else None
    latest_signal = _safe_json(signal_line.iloc[-1]) if len(signal_line) > 0 else None

    sma_5 = calculate_sma(series, period=5)
    sma_20 = calculate_sma(series, period=20)
    sma_60 = calculate_sma(series, period=60)

    latest_price = float(series.iloc[-1])

    trend = "盤整"
    if sma_5.iloc[-1] > sma_20.iloc[-1] > sma_60.iloc[-1]:
        trend = "多頭排列"
    elif sma_5.iloc[-1] < sma_20.iloc[-1] < sma_60.iloc[-1]:
        trend = "空頭排列"

    rsi_signal = "中性"
    if latest_rsi and latest_rsi > 70:
        rsi_signal = "超買"
    elif latest_rsi and latest_rsi < 30:
        rsi_signal = "超賣"

    return {
        "stock_id": stock_id,
        "price": round(latest_price, 2),
        "rsi_14": latest_rsi,
        "rsi_signal": rsi_signal,
        "macd": latest_macd,
        "macd_signal": latest_signal,
        "macd_histogram": _safe_json(histogram.iloc[-1]) if len(histogram) > 0 else None,
        "sma_5": _safe_json(sma_5.iloc[-1]),
        "sma_20": _safe_json(sma_20.iloc[-1]),
        "sma_60": _safe_json(sma_60.iloc[-1]),
        "trend": trend,
    }


async def _goodinfo_technical_fallback(stock_id: str):
    """用 Goodinfo OHLCV 計算技術指標"""
    import pandas as pd
    from core.goodinfo import fetch_ohlcv
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, fetch_ohlcv, stock_id)
    if not records or len(records) < 5:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    closes = pd.Series(
        [r["close"] for r in records],
        index=pd.to_datetime([r["date"] for r in records]),
    )

    latest_price = float(closes.iloc[-1])
    result = {"stock_id": stock_id, "price": round(latest_price, 2), "source": "goodinfo"}

    try:
        rsi = calculate_rsi(closes, period=14)
        result["rsi_14"] = _safe_json(rsi.iloc[-1]) if len(rsi) > 0 else None
        if result["rsi_14"] and result["rsi_14"] > 70:
            result["rsi_signal"] = "超買"
        elif result["rsi_14"] and result["rsi_14"] < 30:
            result["rsi_signal"] = "超賣"
        else:
            result["rsi_signal"] = "中性"
    except Exception:
        result["rsi_14"] = None
        result["rsi_signal"] = "中性"

    try:
        macd_line, signal_line, histogram = calculate_macd(closes)
        result["macd"] = _safe_json(macd_line.iloc[-1]) if len(macd_line) > 0 else None
        result["macd_signal"] = _safe_json(signal_line.iloc[-1]) if len(signal_line) > 0 else None
        result["macd_histogram"] = _safe_json(histogram.iloc[-1]) if len(histogram) > 0 else None
    except Exception:
        result["macd"] = result["macd_signal"] = result["macd_histogram"] = None

    try:
        sma_5 = calculate_sma(closes, period=5)
        sma_20 = calculate_sma(closes, period=20)
        result["sma_5"] = _safe_json(sma_5.iloc[-1]) if len(sma_5) > 0 else None
        result["sma_20"] = _safe_json(sma_20.iloc[-1]) if len(sma_20) > 0 else None
        result["sma_60"] = None  # 資料不足 60 天

        if result["sma_5"] and result["sma_20"]:
            result["trend"] = "多頭排列" if result["sma_5"] > result["sma_20"] else "空頭排列"
        else:
            result["trend"] = "盤整"
    except Exception:
        result["sma_5"] = result["sma_20"] = result["sma_60"] = None
        result["trend"] = "盤整"

    return result


@app.get("/stock/{stock_id}/chip", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_chip(
    stock_id: str,
    days: int = Query(default=5, description="最近 N 天", ge=1, le=60),
):
    """
    個股籌碼分析：三大法人買賣超、外資持股比率、融資融券。
    範例: /stock/2330/chip?days=10
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用 TWSE ──
    if _finlab_quota_exceeded:
        logger.info("[chip] FinLab 額度超限，走 TWSE fallback: %s", stock_id)
        result = multi_source.get_institutional(stock_id, days) or {"stock_id": stock_id}
        margin = multi_source.get_margin(stock_id, days)
        if margin:
            result["margin_buy"] = margin.get("margin_buy")
            result["margin_sell"] = margin.get("margin_sell")
        result["source"] = "fallback"
        return result

    result = {"stock_id": stock_id}

    for key, label in [
        ("foreign_investors", "外資"),
        ("investment_trust", "投信"),
        ("dealer", "自營商"),
    ]:
        try:
            df = loader.get(key)
            if stock_id in df.columns:
                data = df[stock_id].dropna().tail(days)
                total = float(data.sum())
                result[label] = {
                    "total_shares": int(total),
                    "daily": [
                        {"date": d.strftime("%Y-%m-%d"), "shares": int(v)}
                        for d, v in data.items()
                    ],
                }
        except Exception:
            pass

    try:
        fh = loader.get("foreign_holding")
        if stock_id in fh.columns:
            latest = fh[stock_id].dropna().iloc[-1]
            result["foreign_holding_pct"] = _safe_json(latest)
    except Exception:
        pass

    try:
        mb = loader.get("margin_buy")
        ms = loader.get("margin_sell")
        if stock_id in mb.columns:
            result["margin_buy"] = _safe_json(mb[stock_id].dropna().iloc[-1])
        if stock_id in ms.columns:
            result["margin_sell"] = _safe_json(ms[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    return result


# ════════════════════════════════════════════════════════
# 第二批：個股擴充
# ════════════════════════════════════════════════════════

@app.get("/stock/{stock_id}/ohlcv", tags=["個股"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def stock_ohlcv(
    stock_id: str,
    days: int = Query(default=120, ge=5, le=1260, description="最近 N 個交易日"),
):
    """
    個股 OHLCV 時序資料。

    回傳開高低收量的每日時序，供前端繪製 K 線圖。
    範例: /stock/2330/ohlcv?days=120
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用 yfinance ──
    if _finlab_quota_exceeded:
        logger.info("[ohlcv] FinLab 額度超限，走 yfinance fallback: %s", stock_id)
        fallback = multi_source.get_ohlcv(stock_id, days)
        if fallback:
            return fallback
        raise HTTPException(status_code=503, detail="FinLab 額度超限且 fallback 來源無資料")

    try:
        close = loader.get("close")
        if stock_id not in close.columns:
            # Fallback: Goodinfo OHLCV（支援興櫃等 FinLab 不涵蓋的股票）
            return await _goodinfo_ohlcv_fallback(stock_id, days)

        close_s = close[stock_id].dropna().tail(days)
        dates = close_s.index

        # 一次載入所需的 DataFrame，避免重複讀取 pickle
        open_s = high_s = low_s = vol_s = None
        for key, name in [("open", "open_s"), ("high", "high_s"), ("low", "low_s"), ("volume", "vol_s")]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].reindex(dates)
                    if name == "open_s": open_s = series
                    elif name == "high_s": high_s = series
                    elif name == "low_s": low_s = series
                    elif name == "vol_s": vol_s = series
            except Exception:
                pass

        records = []
        for d in dates:
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "close": _safe_json(close_s.loc[d]),
                "open": _safe_json(open_s.loc[d]) if open_s is not None else None,
                "high": _safe_json(high_s.loc[d]) if high_s is not None else None,
                "low": _safe_json(low_s.loc[d]) if low_s is not None else None,
                "volume": _safe_json(vol_s.loc[d]) if vol_s is not None else None,
            }
            records.append(row)

        return {
            "stock_id": stock_id,
            "days": len(records),
            "data": records,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stock/{stock_id}/technical-chart", tags=["個股"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def stock_technical_chart(
    stock_id: str,
    days: int = Query(default=120, ge=30, le=1260, description="最近 N 個交易日"),
):
    """
    個股完整技術指標時序。

    回傳含 SMA5/20/60、RSI14、MACD、BB 的每日時序，供前端繪製技術分析圖。
    範例: /stock/2330/technical-chart?days=120
    """
    try:
        close = loader.get("close")
        if stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

        series = close[stock_id].dropna()
        # 取末 days 筆，但計算指標需要更多歷史（額外取 60 筆緩衝）
        full_series = series.tail(days + 80)
        tail_dates = series.tail(days).index

        sma5 = calculate_sma(full_series, 5)
        sma20 = calculate_sma(full_series, 20)
        sma60 = calculate_sma(full_series, 60)
        rsi14 = calculate_rsi(full_series, 14)
        macd_line, signal_line, histogram = calculate_macd(full_series)
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(full_series, 20)

        high_s = low_s = None
        try:
            high_df = loader.get("high")
            low_df = loader.get("low")
            if stock_id in high_df.columns:
                high_s = high_df[stock_id].dropna()
            if stock_id in low_df.columns:
                low_s = low_df[stock_id].dropna()
        except Exception:
            pass

        kdj_k = kdj_d = kdj_j = None
        if high_s is not None and low_s is not None:
            try:
                h_full = high_s.reindex(full_series.index)
                l_full = low_s.reindex(full_series.index)
                kdj_k, kdj_d, kdj_j = calculate_kdj(h_full, l_full, full_series)
            except Exception:
                pass

        records = []
        for d in tail_dates:
            if d not in full_series.index:
                continue
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "close": _safe_json(full_series.loc[d]),
                "sma5": _safe_json(sma5.loc[d]) if d in sma5.index else None,
                "sma20": _safe_json(sma20.loc[d]) if d in sma20.index else None,
                "sma60": _safe_json(sma60.loc[d]) if d in sma60.index else None,
                "rsi14": _safe_json(rsi14.loc[d]) if d in rsi14.index else None,
                "macd": _safe_json(macd_line.loc[d]) if d in macd_line.index else None,
                "macd_signal": _safe_json(signal_line.loc[d]) if d in signal_line.index else None,
                "macd_hist": _safe_json(histogram.loc[d]) if d in histogram.index else None,
                "bb_upper": _safe_json(bb_upper.loc[d]) if d in bb_upper.index else None,
                "bb_mid": _safe_json(bb_mid.loc[d]) if d in bb_mid.index else None,
                "bb_lower": _safe_json(bb_lower.loc[d]) if d in bb_lower.index else None,
                "kdj_k": _safe_json(kdj_k.loc[d]) if kdj_k is not None and d in kdj_k.index else None,
                "kdj_d": _safe_json(kdj_d.loc[d]) if kdj_d is not None and d in kdj_d.index else None,
                "kdj_j": _safe_json(kdj_j.loc[d]) if kdj_j is not None and d in kdj_j.index else None,
            }
            records.append(row)

        return {
            "stock_id": stock_id,
            "days": len(records),
            "data": records,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stock/{stock_id}/financials", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_financials(
    stock_id: str,
    months: int = Query(default=12, ge=3, le=60, description="最近 N 個月"),
):
    """
    個股財報資料 - 月營收、本益比、股價淨值比、殖利率。

    範例: /stock/2330/financials
    """
    try:
        result: Dict[str, Any] = {"stock_id": stock_id, "months": months}

        for key, label in [
            ("monthly_revenue", "monthly_revenue"),
            ("revenue_yoy", "revenue_yoy"),
            ("revenue_mom", "revenue_mom"),
            ("pe_ratio", "pe_ratio"),
            ("pb_ratio", "pb_ratio"),
            ("dividend_yield", "dividend_yield"),
        ]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna().tail(months)
                    result[label] = [
                        {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                        for d, v in series.items()
                    ]
                else:
                    result[label] = []
            except Exception:
                result[label] = []

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stock/{stock_id}/chip/detail", tags=["個股"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=300)
async def stock_chip_detail(
    stock_id: str,
    days: int = Query(default=30, ge=5, le=120, description="最近 N 天"),
):
    """
    個股詳細籌碼分析 - 含大戶持股分布時序。

    範例: /stock/2330/chip/detail?days=30
    """
    try:
        result: Dict[str, Any] = {"stock_id": stock_id, "days": days}

        # 三大法人時序
        for key, label in [
            ("foreign_investors", "foreign"),
            ("investment_trust", "investment_trust"),
            ("dealer", "dealer"),
        ]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna().tail(days)
                    result[label] = {
                        "latest": _safe_json(series.iloc[-1]) if len(series) > 0 else None,
                        "total": _safe_json(series.sum()),
                        "data": [
                            {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                            for d, v in series.items()
                        ],
                    }
            except Exception:
                result[label] = None

        # 外資持股比率
        try:
            fh = loader.get("foreign_holding")
            if stock_id in fh.columns:
                series = fh[stock_id].dropna().tail(days)
                result["foreign_holding"] = {
                    "latest": _safe_json(series.iloc[-1]) if len(series) > 0 else None,
                    "data": [
                        {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                        for d, v in series.items()
                    ],
                }
        except Exception:
            result["foreign_holding"] = None

        # 融資融券時序
        for key, label in [("margin_buy", "margin_buy"), ("margin_sell", "margin_sell")]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna().tail(days)
                    result[label] = {
                        "latest": _safe_json(series.iloc[-1]) if len(series) > 0 else None,
                        "data": [
                            {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                            for d, v in series.items()
                        ],
                    }
            except Exception:
                result[label] = None

        # 大戶持股分布（取最新一筆）
        inventory_keys = [
            "inventory_total_holders",
            "inventory_over_1000_ratio",
            "inventory_over_400_ratio",
            "inventory_under_10_ratio",
        ]
        inventory_data = {}
        for key in inventory_keys:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna()
                    if len(series) > 0:
                        inventory_data[key] = _safe_json(series.iloc[-1])
            except Exception:
                pass
        result["inventory"] = inventory_data

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stocks/compare", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stocks_compare(
    ids: str = Query(..., description="股票代號，逗號分隔，如 2330,2317"),
    days: int = Query(default=60, ge=10, le=500, description="最近 N 個交易日"),
):
    """
    多股比較 - 回傳多支股票的標準化價格序列（以第一天為基準 = 100）。

    範例: /stocks/compare?ids=2330,2317&days=60
    """
    try:
        stock_ids = [s.strip() for s in ids.split(",") if s.strip()]
        if not stock_ids:
            raise HTTPException(status_code=400, detail="請提供至少一個股票代號")
        if len(stock_ids) > 10:
            raise HTTPException(status_code=400, detail="最多比較 10 支股票")

        close = loader.get("close")
        name_map = _get_stock_name_map()

        result_stocks = []
        for sid in stock_ids:
            if sid not in close.columns:
                continue
            series = close[sid].dropna().tail(days)
            if len(series) == 0:
                continue
            base = float(series.iloc[0])
            normalized = [(float(v) / base * 100) if base > 0 else 100 for v in series]
            result_stocks.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "base_price": round(base, 2),
                "latest_price": round(float(series.iloc[-1]), 2),
                "total_return_pct": round((float(series.iloc[-1]) / base - 1) * 100, 2) if base > 0 else 0,
                "data": [
                    {"date": d.strftime("%Y-%m-%d"), "price": round(float(p), 2), "normalized": round(n, 2)}
                    for (d, p), n in zip(series.items(), normalized)
                ],
            })

        return {
            "days": days,
            "stocks": result_stocks,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════
# Claude AI 個股分析端點
# ════════════════════════════════════════════════════════

_claude_analyzer = None


def _get_claude_analyzer():
    """Lazy init ClaudeStockAnalyzer。"""
    global _claude_analyzer
    if _claude_analyzer is None:
        from core.ai_models import ClaudeStockAnalyzer
        _claude_analyzer = ClaudeStockAnalyzer()
    return _claude_analyzer


@app.get("/strategy/ai-claude/{stock_id}", tags=["策略", "AI 分析"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=3600)
async def strategy_ai_claude(stock_id: str):
    """使用 Claude API 對個股進行智慧分析，回傳綜合分析摘要、投資建議與關鍵因素。

    - 結果快取 1 小時，降低 API 費用。
    - 需要設定環境變數 ANTHROPIC_API_KEY。
    - 若未設定，回傳 {"error": "ANTHROPIC_API_KEY 未設定"}。
    """
    import asyncio as _asyncio

    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY 未設定"}

    # 驗證股票是否存在
    try:
        close = loader.get("close")
        if close is None or stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 取得股票名稱（供回應使用）
    name = stock_id
    try:
        name_map = _get_stock_name_map()
        name = name_map.get(stock_id, stock_id)
    except Exception:
        pass

    # 在執行緒中執行同步的 Claude API 呼叫，不阻塞 event loop
    loop = _asyncio.get_event_loop()
    analyzer = _get_claude_analyzer()
    try:
        result = await loop.run_in_executor(None, analyzer.analyze, stock_id, loader)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude 分析失敗: {e}")

    if result.get("error"):
        return {"stock_id": stock_id, "name": name, **result}

    return {
        "stock_id": stock_id,
        "name": name,
        "summary": result.get("summary", ""),
        "recommendation": result.get("recommendation", ""),
        "risk_level": result.get("risk_assessment", ""),
        "key_factors": result.get("key_factors", []),
        "analyzed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ─── LSTM 趨勢預測端點 ─────────────────────────────────

_lstm_predictor = None


def _get_lstm_predictor():
    """Lazy init LSTMTrendPredictor（避免 import 時初始化）"""
    global _lstm_predictor
    if _lstm_predictor is None:
        from core.ai_models import LSTMTrendPredictor
        _lstm_predictor = LSTMTrendPredictor()
    return _lstm_predictor


@app.get("/strategy/ai-lstm/{stock_id}", tags=["策略", "AI 分析"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=1800)
async def strategy_ai_lstm(stock_id: str):
    """LSTM 價格趨勢預測 — 預測個股未來 5 日趨勢方向與估計價格。

    - PyTorch 可用時使用 LSTM 深度學習模型（即時訓練，無需預訓練權重）。
    - PyTorch 不可用時自動降級為 EWMA 趨勢偵測 fallback。
    - 結果快取 30 分鐘（1800 秒）。
    - 不支援大型預訓練模型，適合記憶體受限的部署環境（如 Railway）。

    回傳欄位：
    - direction: 上漲 / 下跌 / 盤整
    - confidence: 預測信心度 (0.0–1.0)
    - predicted_prices: 未來 5 天估計價格列表
    - trend_strength: 趨勢強度 (0.0–1.0)
    """
    import asyncio as _asyncio

    # 驗證股票存在
    try:
        close = loader.get("close")
        if close is None or stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 取得股票名稱
    name = stock_id
    try:
        name_map = _get_stock_name_map()
        name = name_map.get(stock_id, stock_id)
    except Exception:
        pass

    predictor = _get_lstm_predictor()
    loop = _asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, predictor.predict, stock_id, loader)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LSTM 預測失敗: {e}")

    return {
        "stock_id": stock_id,
        "name": name,
        "direction": result["direction"],
        "confidence": result["confidence"],
        "predicted_prices": result["predicted_prices"],
        "trend_strength": result["trend_strength"],
        "predicted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ─── XGBoost 因子選股端點 ──────────────────────────────

_xgboost_picker = None


def _get_xgboost_picker():
    """Lazy init XGBoostStockPicker（避免 import 時觸發 xgboost 相依性）。"""
    global _xgboost_picker
    if _xgboost_picker is None:
        from core.ai_models import XGBoostStockPicker
        _xgboost_picker = XGBoostStockPicker()
    return _xgboost_picker


@app.get("/strategy/ai-xgboost", tags=["策略", "AI 分析"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=3600)
async def strategy_ai_xgboost(
    top_n: int = Query(default=20, ge=1, le=50, description="回傳預測報酬前 N 名股票"),
):
    """XGBoost 因子選股 — 以多因子模型預測未來 20 日報酬率後排名選股。

    特徵包含：PE/PB/殖利率、RSI/MACD/均線位置、成交量比、
    月營收年增/月增率、外資近 5 日買賣超、近 5/20/60 日報酬率。

    - 訓練集：最近 252 個交易日（約 1 年）
    - 目標：未來 20 交易日報酬率
    - 結果快取 1 小時（模型訓練開銷較大）
    - 需要安裝 xgboost 和 scikit-learn

    回傳欄位：
    - stocks: 排名後的股票清單（含 predicted_return、confidence、factors）
    - feature_importance: 各因子對模型的重要性分數
    """
    import asyncio as _asyncio

    name_map = _get_stock_name_map()

    try:
        picker = _get_xgboost_picker()
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"XGBoost 模型不可用：{exc}，請確認 xgboost 與 scikit-learn 已安裝",
        )

    loop = _asyncio.get_event_loop()
    try:
        all_results = await loop.run_in_executor(None, picker.predict, loader)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"XGBoost 選股失敗: {exc}")

    # 取出 feature_importance（每筆都帶同一份，取第一筆即可）
    feature_importance: Dict[str, Any] = {}
    if all_results:
        feature_importance = all_results[0].pop("__feature_importance__", {})
        for item in all_results[1:]:
            item.pop("__feature_importance__", None)

    # 取前 top_n，補上股票名稱，清理 NaN/inf
    top_results = all_results[:top_n]
    for item in top_results:
        item["name"] = name_map.get(item["stock_id"], "")
        for k, v in list(item.items()):
            if isinstance(v, float) and (pd.isna(v) or np.isinf(v)):
                item[k] = 0.0
            elif isinstance(v, dict):
                for kk, vv in list(v.items()):
                    if isinstance(vv, float) and (pd.isna(vv) or np.isinf(vv)):
                        v[kk] = 0.0

    # feature_importance 也清理
    for k, v in list(feature_importance.items()):
        if isinstance(v, float) and (pd.isna(v) or np.isinf(v)):
            feature_importance[k] = 0.0

    return {
        "date":               datetime.now().strftime("%Y-%m-%d"),
        "total_candidates":   len(all_results),
        "stocks":             top_results,
        "feature_importance": feature_importance,
    }


# ════════════════════════════════════════════════════════
# AI 工具端點
# ════════════════════════════════════════════════════════

@app.post("/ai/news-sentiment", tags=["AI 分析"], dependencies=[Depends(verify_api_key)])
async def ai_news_sentiment(req: NewsSentimentRequest):
    """AI 新聞情緒分析 - 用 Claude 批次分析新聞情緒"""
    from core.ai_models import ClaudeNewsSentimentAnalyzer
    loop = asyncio.get_event_loop()
    analyzer = ClaudeNewsSentimentAnalyzer()
    results = await loop.run_in_executor(None, analyzer.analyze_batch, req.news)
    return {"results": results}


@app.get("/ai/anomalies", tags=["AI 分析"], dependencies=[Depends(verify_api_key)])
async def ai_anomalies(
    scope: str = Query(default="watchlist", description="掃描範圍: watchlist / all"),
    explain: bool = Query(default=True, description="是否啟用 AI 解讀"),
):
    """AI 異常偵測 - 偵測爆量、跳空、法人轉向等異常訊號"""
    from core.ai_models import AnomalyDetector
    loop = asyncio.get_event_loop()

    detector = AnomalyDetector()

    stock_ids = None
    if scope == "watchlist":
        # 收集自選股 + 持倉
        try:
            watchlist_file = Path(__file__).parent / "data" / "watchlists.json"
            portfolio_file = Path(__file__).parent / "data" / "portfolios.json"
            ids = set()
            if watchlist_file.exists():
                import json
                wl_data = json.loads(watchlist_file.read_text(encoding="utf-8"))
                if isinstance(wl_data, dict):
                    for wl in wl_data.values():
                        for s in (wl.get("stocks", []) if isinstance(wl, dict) else []):
                            ids.add(s if isinstance(s, str) else s.get("stock_id", ""))
            if portfolio_file.exists():
                import json
                pf_data = json.loads(portfolio_file.read_text(encoding="utf-8"))
                if isinstance(pf_data, dict):
                    for p in pf_data.values():
                        for h in (p.get("holdings", []) if isinstance(p, dict) else []):
                            ids.add(h.get("stock_id", ""))
            stock_ids = list(ids - {""}) if ids else None
        except Exception:
            stock_ids = None

    anomalies = await loop.run_in_executor(None, detector.detect, loader, stock_ids)

    explanation = ""
    if explain and anomalies:
        explanation = await loop.run_in_executor(None, detector.explain, anomalies)

    return {
        "anomalies": anomalies,
        "explanation": explanation,
        "total": len(anomalies),
        "high_count": sum(1 for a in anomalies if a.get("severity") == "high"),
        "medium_count": sum(1 for a in anomalies if a.get("severity") == "medium"),
    }


@app.post("/ai/journal-review", tags=["AI 分析"], dependencies=[Depends(verify_api_key)])
async def ai_journal_review(req: JournalReviewRequest):
    """AI 交易日誌回顧 - 分析交易行為偏誤"""
    from core.ai_models import TradingJournalAnalyzer
    loop = asyncio.get_event_loop()
    analyzer = TradingJournalAnalyzer()
    result = await loop.run_in_executor(None, analyzer.analyze, req.entries)
    return result


@app.post("/ai/stock-chat", tags=["AI 分析"], dependencies=[Depends(verify_api_key)])
async def ai_stock_chat(req: StockChatRequest):
    """AI 個股對話 - 自然語言問答"""
    from core.ai_models import StockChatAssistant
    loop = asyncio.get_event_loop()

    assistant = StockChatAssistant()

    # 收集數據上下文
    context_parts = []
    try:
        close = loader.get("close")
        if close is not None and req.stock_id in close.columns:
            prices = close[req.stock_id].dropna()
            if len(prices) > 0:
                latest = float(prices.iloc[-1])
                prev = float(prices.iloc[-2]) if len(prices) > 1 else latest
                chg = (latest / prev - 1) * 100
                context_parts.append(f"收盤價: {latest:.2f} (漲跌: {chg:+.2f}%)")
                high_52w = float(prices.iloc[-252:].max()) if len(prices) >= 252 else float(prices.max())
                low_52w = float(prices.iloc[-252:].min()) if len(prices) >= 252 else float(prices.min())
                context_parts.append(f"52週高低: {high_52w:.2f} / {low_52w:.2f}")
    except Exception:
        pass
    for key, label in [("pe_ratio", "本益比"), ("pb_ratio", "股價淨值比"), ("dividend_yield", "殖利率")]:
        try:
            df = loader.get(key)
            if df is not None and req.stock_id in df.columns:
                val = float(df[req.stock_id].dropna().iloc[-1])
                context_parts.append(f"{label}: {val:.2f}")
        except Exception:
            pass

    # 取得股票名稱
    name = req.stock_id
    try:
        info = loader.get_stock_info()
        if info is not None:
            row = info[info["stock_id"] == req.stock_id]
            if len(row) > 0:
                name = row["name"].values[0]
    except Exception:
        pass

    data_context = "\n".join(context_parts) if context_parts else "暫無數據"

    reply = await loop.run_in_executor(
        None, assistant.chat, req.stock_id, name, data_context, req.question, req.history
    )
    return {"reply": reply, "stock_id": req.stock_id, "name": name}


@app.post("/ai/post-market-summary", tags=["AI 分析"], dependencies=[Depends(verify_api_key)])
async def ai_post_market_summary(req: PostMarketSummaryRequest):
    """AI 盤後摘要 - 生成覆盤報告"""
    from core.ai_models import PostMarketSummarizer
    loop = asyncio.get_event_loop()

    summarizer = PostMarketSummarizer()

    # 自動收集市場數據
    market_data = req.market_data or {}
    if not market_data:
        try:
            close = loader.get("close")
            if close is not None and len(close) > 1:
                market_data["date"] = close.index[-1].strftime("%Y-%m-%d")
                change_pct = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).fillna(0)

                info = loader.get_stock_info()
                name_map = dict(zip(info["stock_id"], info["name"])) if info is not None else {}

                sorted_change = change_pct.sort_values(ascending=False)
                market_data["top_gainers"] = [
                    {"stock_id": s, "name": name_map.get(s, ""), "change_pct": float(sorted_change[s])}
                    for s in sorted_change.head(5).index
                ]
                market_data["top_losers"] = [
                    {"stock_id": s, "name": name_map.get(s, ""), "change_pct": float(sorted_change[s])}
                    for s in sorted_change.tail(5).index
                ]

            for key, field in [("foreign_investors", "foreign_net"), ("investment_trust", "trust_net"), ("dealer", "dealer_net")]:
                df = loader.get(key)
                if df is not None and len(df) > 0:
                    market_data[field] = float(df.iloc[-1].sum()) / 100_000_000
        except Exception:
            pass

    result = await loop.run_in_executor(None, summarizer.generate, market_data)
    return result


# ════════════════════════════════════════════════════════
# 策略端點（固定路徑優先於動態路徑）
# ════════════════════════════════════════════════════════

# 注意：/strategy/ai-pick、/strategy/composite、/strategy/ai-claude/{stock_id}
# /strategy/ai-lstm/{stock_id}、/strategy/ai-xgboost 均定義在
# /strategy/{strategy_type} 之前，確保 FastAPI 路由匹配正確。

@app.get("/strategy/ai-pick", tags=["策略"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=600)
async def strategy_ai_pick_early(
    top_n: int = Query(default=10, ge=1, le=30, description="每策略回傳前 N 檔"),
):
    """AI 選股 - 整合三大策略，取各策略前 N 名並進行綜合評分。(路由前置版)"""
    return await strategy_ai_pick(top_n=top_n)


@app.get("/strategy/composite", tags=["策略"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=600)
async def strategy_composite_early(
    top_n: int = Query(default=20, ge=1, le=50),
):
    """綜合策略選股 - 計算每支股票在三大策略的綜合排名分數。(路由前置版)"""
    return await strategy_composite(top_n=top_n)


class StrategyType(str, Enum):
    value = "value"
    growth = "growth"
    momentum = "momentum"

@app.get("/strategy/{strategy_type}", tags=["策略"], dependencies=[Depends(verify_api_key)])
async def run_strategy(
    strategy_type: StrategyType,
    preset: str = Query(default="standard", description="預設組合: conservative/standard/aggressive"),
    top_n: int = Query(default=20, description="回傳前 N 檔", ge=1, le=50),
):
    """
    執行選股策略，回傳符合條件的股票清單。

    策略類型:
    - value: 價值投資（低本益比、高殖利率）
    - growth: 成長投資（營收年增率高）
    - momentum: 動能投資（突破、量能）

    範例: /strategy/value?preset=conservative&top_n=10
    """
    # strategy_type 已由 StrategyType Enum 自動驗證

    from config import STRATEGY_PRESETS

    active = get_active_stocks()
    close = loader.get("close")
    latest_prices = close[active].iloc[-1]
    name_map = _get_stock_name_map()

    preset_params = STRATEGY_PRESETS[strategy_type].get(
        preset, STRATEGY_PRESETS[strategy_type]["standard"]
    )["params"]

    results = []

    if strategy_type == "value":
        pe_df = loader.get("pe_ratio")
        pb_df = loader.get("pb_ratio")
        dy_df = loader.get("dividend_yield")

        strategy = ValueStrategy(params=preset_params)
        data = {"pe_ratio": pe_df, "pb_ratio": pb_df, "dividend_yield": dy_df}
        matched = set(strategy.filter(data))

        for sid in matched:
            try:
                pe = pe_df[sid].dropna().iloc[-1] if sid in pe_df.columns else None
                pb = pb_df[sid].dropna().iloc[-1] if sid in pb_df.columns else None
                dy = dy_df[sid].dropna().iloc[-1] if sid in dy_df.columns else None
                if pe is None or pb is None or dy is None:
                    continue
                results.append({
                    "stock_id": sid,
                    "price": round(float(latest_prices.get(sid, 0)), 2),
                    "pe_ratio": round(float(pe), 2),
                    "pb_ratio": round(float(pb), 2),
                    "dividend_yield": round(float(dy), 2),
                })
            except (IndexError, KeyError):
                continue

        results.sort(key=lambda x: x["dividend_yield"], reverse=True)

    elif strategy_type == "growth":
        yoy_df = loader.get("revenue_yoy")
        mom_df = loader.get("revenue_mom")

        strategy = GrowthStrategy(params=preset_params)
        data = {"revenue_yoy": yoy_df, "revenue_mom": mom_df}
        matched = set(strategy.filter(data))

        for sid in matched:
            try:
                yoy = yoy_df[sid].dropna().iloc[-1] if sid in yoy_df.columns else None
                mom = mom_df[sid].dropna().iloc[-1] if sid in mom_df.columns else None
                if yoy is None or mom is None:
                    continue
                results.append({
                    "stock_id": sid,
                    "price": round(float(latest_prices.get(sid, 0)), 2),
                    "revenue_yoy": round(float(yoy), 2),
                    "revenue_mom": round(float(mom), 2),
                })
            except (IndexError, KeyError):
                continue

        results.sort(key=lambda x: x["revenue_yoy"], reverse=True)

    elif strategy_type == "momentum":
        volume_df = loader.get("volume")

        momentum_params = dict(preset_params)
        if "volume_ratio" in momentum_params and "volume_ratio_min" not in momentum_params:
            momentum_params["volume_ratio_min"] = momentum_params.pop("volume_ratio")

        strategy = MomentumStrategy(params=momentum_params)
        data = {"close": close, "volume": volume_df}
        matched = set(strategy.filter(data))

        breakout_days = momentum_params.get("breakout_days", 20)

        for sid in matched:
            try:
                price_series = close[sid].dropna()
                vol_series = volume_df[sid].dropna()
                if len(price_series) < breakout_days + 1 or len(vol_series) < 21:
                    continue

                latest_price = float(price_series.iloc[-1])
                high_n = float(price_series.tail(breakout_days + 1).iloc[:-1].max())
                avg_vol = float(vol_series.tail(21).iloc[:-1].mean())
                latest_vol = float(vol_series.iloc[-1])
                vol_ratio = latest_vol / avg_vol if avg_vol > 0 else 0

                rsi_series = calculate_rsi(price_series, period=14)
                latest_rsi = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 else 50

                results.append({
                    "stock_id": sid,
                    "price": round(latest_price, 2),
                    "volume_ratio": round(vol_ratio, 2),
                    "rsi": round(latest_rsi, 2),
                    "breakout_high": round(high_n, 2),
                })
            except (IndexError, KeyError):
                continue

        results.sort(key=lambda x: x["volume_ratio"], reverse=True)

    # 補上股票名稱
    for item in results:
        item["name"] = name_map.get(item["stock_id"], "")

    return {
        "strategy": strategy_type,
        "preset": preset,
        "date": close.index[-1].strftime("%Y-%m-%d"),
        "total_matches": len(results),
        "stocks": results[:top_n],
    }


@app.get("/screener", tags=["策略"], dependencies=[Depends(verify_api_key)])
async def screener(
    pe_max: Optional[float] = Query(default=None, description="本益比上限"),
    pe_min: Optional[float] = Query(default=None, description="本益比下限"),
    pb_max: Optional[float] = Query(default=None, description="股價淨值比上限"),
    dy_min: Optional[float] = Query(default=None, description="殖利率下限 (%)"),
    yoy_min: Optional[float] = Query(default=None, description="營收年增率下限 (%)"),
    rsi_max: Optional[float] = Query(default=None, description="RSI 上限"),
    rsi_min: Optional[float] = Query(default=None, description="RSI 下限"),
    top_n: int = Query(default=20, ge=1, le=100),
):
    """
    自訂條件篩選股票。可組合多個條件。
    範例: /screener?pe_max=15&dy_min=5&top_n=10
    """
    active = get_active_stocks()
    close = loader.get("close")
    candidates = set(active)

    if pe_max is not None or pe_min is not None:
        pe_df = loader.get("pe_ratio")
        for sid in list(candidates):
            if sid not in pe_df.columns:
                candidates.discard(sid)
                continue
            val = pe_df[sid].dropna().iloc[-1] if not pe_df[sid].dropna().empty else None
            if val is None or np.isnan(val):
                candidates.discard(sid)
                continue
            if pe_max is not None and val > pe_max:
                candidates.discard(sid)
            if pe_min is not None and val < pe_min:
                candidates.discard(sid)

    if pb_max is not None:
        pb_df = loader.get("pb_ratio")
        for sid in list(candidates):
            if sid not in pb_df.columns:
                candidates.discard(sid)
                continue
            val = pb_df[sid].dropna().iloc[-1] if not pb_df[sid].dropna().empty else None
            if val is None or np.isnan(val) or val > pb_max:
                candidates.discard(sid)

    if dy_min is not None:
        dy_df = loader.get("dividend_yield")
        for sid in list(candidates):
            if sid not in dy_df.columns:
                candidates.discard(sid)
                continue
            val = dy_df[sid].dropna().iloc[-1] if not dy_df[sid].dropna().empty else None
            if val is None or np.isnan(val) or val < dy_min:
                candidates.discard(sid)

    if yoy_min is not None:
        yoy_df = loader.get("revenue_yoy")
        for sid in list(candidates):
            if sid not in yoy_df.columns:
                candidates.discard(sid)
                continue
            val = yoy_df[sid].dropna().iloc[-1] if not yoy_df[sid].dropna().empty else None
            if val is None or np.isnan(val) or val < yoy_min:
                candidates.discard(sid)

    if rsi_max is not None or rsi_min is not None:
        valid_candidates = [sid for sid in candidates if sid in close.columns]
        if valid_candidates:
            rsi_all = calculate_rsi(close[valid_candidates], period=14)
            latest_rsi = rsi_all.iloc[-1]
            for sid in list(candidates):
                if sid not in latest_rsi.index or pd.isna(latest_rsi[sid]):
                    candidates.discard(sid)
                    continue
                val = float(latest_rsi[sid])
                if rsi_max is not None and val > rsi_max:
                    candidates.discard(sid)
                if rsi_min is not None and val < rsi_min:
                    candidates.discard(sid)
        else:
            candidates.clear()

    results = []
    for sid in list(candidates)[:top_n]:
        price = close[sid].dropna().iloc[-1] if sid in close.columns else 0
        results.append({"stock_id": sid, "price": round(float(price), 2)})

    return {
        "date": close.index[-1].strftime("%Y-%m-%d"),
        "filters_applied": {
            k: v for k, v in {
                "pe_max": pe_max, "pe_min": pe_min, "pb_max": pb_max,
                "dy_min": dy_min, "yoy_min": yoy_min,
                "rsi_max": rsi_max, "rsi_min": rsi_min,
            }.items() if v is not None
        },
        "total_matches": len(candidates),
        "stocks": results,
    }


# ════════════════════════════════════════════════════════
# 第三批：策略與回測
# ════════════════════════════════════════════════════════

@app.post("/backtest/run", tags=["回測"], dependencies=[Depends(verify_api_key)])
async def backtest_run(req: BacktestRequest):
    """
    執行策略回測。

    支援 value / growth / momentum 三種策略，可自訂初始資金、換股頻率。
    計算耗時較長（5-30 秒），請勿在高頻場景下呼叫。
    """
    try:
        from config import STRATEGY_PRESETS
        from core.backtest.engine import BacktestEngine
        from core.strategies.value import ValueStrategy
        from core.strategies.growth import GrowthStrategy
        from core.strategies.momentum import MomentumStrategy

        if req.strategy not in ("value", "growth", "momentum"):
            raise HTTPException(status_code=400, detail="策略類型需為 value/growth/momentum")

        preset_params = STRATEGY_PRESETS[req.strategy].get(
            req.preset, STRATEGY_PRESETS[req.strategy]["standard"]
        )["params"]

        close = loader.get("close")
        volume = loader.get("volume")
        benchmark = loader.get_benchmark()

        # 準備策略函數
        def make_strategy_func(stype, params):
            if stype == "value":
                pe_df = loader.get("pe_ratio")
                pb_df = loader.get("pb_ratio")
                dy_df = loader.get("dividend_yield")
                strat = ValueStrategy(params=params)
                def func(data, date):
                    return strat.filter({"pe_ratio": pe_df.loc[:date], "pb_ratio": pb_df.loc[:date], "dividend_yield": dy_df.loc[:date]})
            elif stype == "growth":
                yoy_df = loader.get("revenue_yoy")
                mom_df = loader.get("revenue_mom")
                strat = GrowthStrategy(params=params)
                def func(data, date):
                    return strat.filter({"revenue_yoy": yoy_df.loc[:date], "revenue_mom": mom_df.loc[:date]})
            else:
                mp = dict(params)
                if "volume_ratio" in mp and "volume_ratio_min" not in mp:
                    mp["volume_ratio_min"] = mp.pop("volume_ratio")
                strat = MomentumStrategy(params=mp)
                def func(data, date):
                    return strat.filter({"close": close.loc[:date], "volume": volume.loc[:date]})
            return func

        engine = BacktestEngine(
            initial_capital=req.initial_capital,
        )

        strategy_func = make_strategy_func(req.strategy, preset_params)

        start_date = pd.Timestamp(req.start_date) if req.start_date else None
        end_date = pd.Timestamp(req.end_date) if req.end_date else None

        data = {
            "close": close,
            "volume": volume,
        }
        if req.strategy == "value":
            data["pe_ratio"] = loader.get("pe_ratio")
            data["pb_ratio"] = loader.get("pb_ratio")
            data["dividend_yield"] = loader.get("dividend_yield")
        elif req.strategy == "growth":
            data["revenue_yoy"] = loader.get("revenue_yoy")
            data["revenue_mom"] = loader.get("revenue_mom")

        # 在 executor 中執行耗時計算
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: engine.run(
                    strategy_func=strategy_func,
                    data=data,
                    start_date=start_date,
                    end_date=end_date,
                    rebalance_freq=req.rebalance_freq,
                    max_stocks=req.max_stocks,
                    weight_method=req.weight_method,
                    benchmark=benchmark,
                ),
            ),
            timeout=60,
        )

        m = result.metrics
        pv = result.portfolio_values

        return {
            "strategy": req.strategy,
            "preset": req.preset,
            "config": {
                "initial_capital": req.initial_capital,
                "rebalance_freq": req.rebalance_freq,
                "max_stocks": req.max_stocks,
                "weight_method": req.weight_method,
                "start_date": pv.index[0].strftime("%Y-%m-%d") if len(pv) > 0 else None,
                "end_date": pv.index[-1].strftime("%Y-%m-%d") if len(pv) > 0 else None,
            },
            "metrics": {
                "total_return": _safe_json(m.total_return),
                "annualized_return": _safe_json(m.annualized_return),
                "volatility": _safe_json(m.volatility),
                "sharpe_ratio": _safe_json(m.sharpe_ratio),
                "sortino_ratio": _safe_json(m.sortino_ratio),
                "max_drawdown": _safe_json(m.max_drawdown),
                "win_rate": _safe_json(m.win_rate),
                "total_trades": m.total_trades,
                "profit_factor": _safe_json(m.profit_factor),
                "calmar_ratio": _safe_json(m.calmar_ratio),
            },
            "portfolio_values": [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in pv.items()
            ],
            "benchmark_comparison": result.benchmark_comparison,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="回測計算逾時（>60s），請縮小日期範圍")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def strategy_ai_pick(
    top_n: int = Query(default=10, ge=1, le=30, description="每策略回傳前 N 檔"),
):
    """AI 選股核心邏輯（由前置路由包裝器呼叫）。"""
    try:
        name_map = _get_stock_name_map()
        result = {}
        for stype in ("value", "growth", "momentum"):
            try:
                resp = await run_strategy(stype, preset="standard", top_n=top_n)
                stocks = resp["stocks"]
                for s in stocks:
                    s["name"] = name_map.get(s["stock_id"], "")
                result[stype] = {
                    "total": resp["total_matches"],
                    "stocks": stocks,
                }
            except Exception as e:
                result[stype] = {"total": 0, "stocks": [], "error": str(e)}

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "strategies": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def strategy_composite(
    top_n: int = Query(default=20, ge=1, le=50),
):
    """綜合策略選股核心邏輯（由前置路由包裝器呼叫）。"""
    try:
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()
        score_map: Dict[str, float] = {}

        weights = {"value": 1.0, "growth": 1.0, "momentum": 1.0}
        for stype, weight in weights.items():
            try:
                resp = await run_strategy(stype, preset="standard", top_n=50)
                total = resp["total_matches"] or 1
                for rank, s in enumerate(resp["stocks"]):
                    sid = s["stock_id"]
                    # 線性分數：排名越前分數越高
                    rank_score = (total - rank) / total * 100 * weight
                    score_map[sid] = score_map.get(sid, 0) + rank_score
            except Exception:
                pass

        close = loader.get("close")
        sorted_stocks = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:top_n]

        results = []
        for sid, score in sorted_stocks:
            price = 0.0
            try:
                if sid in close.columns:
                    price = round(float(close[sid].dropna().iloc[-1]), 2)
            except Exception:
                pass
            results.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "industry": industry_map.get(sid, ""),
                "composite_score": round(score, 2),
                "price": price,
            })

        return {
            "date": close.index[-1].strftime("%Y-%m-%d"),
            "total": len(results),
            "stocks": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════
# 第四批：CRUD 端點
# ════════════════════════════════════════════════════════

# ─── 投資組合 ───────────────────────────────────────────

# /portfolios/*, /watchlists/*, /journal/*, /alerts/* 已抽出到 api/routers/


# ─── 參數優化 ──────────────────────────────────────────────

@app.post("/optimizer/run", tags=["策略"], dependencies=[Depends(verify_api_key)])
async def optimizer_run(body: Dict[str, Any] = Body(...)):
    """Grid Search 參數優化 — 暴力窮舉回測找最佳參數組合。"""
    import asyncio as _asyncio
    from core.backtest.engine import BacktestEngine
    from core.backtest.metrics import calculate_metrics

    strategy = body.get("strategy", "ma_crossover")
    stock_code = body.get("stockCode", "2330")
    start_date = body.get("startDate", "2023-01-01")
    end_date = body.get("endDate", "2024-12-31")
    ranges = body.get("ranges", {})

    def _run_grid():
        close = loader.get("close")
        if stock_code not in close.columns:
            return {"error": f"找不到股票 {stock_code}"}

        stock_close = close[stock_code].dropna()
        stock_close = stock_close[start_date:end_date]
        if len(stock_close) < 60:
            return {"error": "資料不足，請選擇更長的時間範圍"}

        # 產生參數組合
        fast_range = range(
            ranges.get("fastPeriod", {}).get("min", 3),
            ranges.get("fastPeriod", {}).get("max", 15) + 1,
            1
        )
        slow_range = range(
            ranges.get("slowPeriod", {}).get("min", 10),
            ranges.get("slowPeriod", {}).get("max", 40) + 1,
            5
        )

        grid_results = []
        best_score = -999
        best_params = {}

        for fast in fast_range:
            for slow in slow_range:
                if fast >= slow:
                    continue
                # 簡易均線交叉回測
                sma_fast = stock_close.rolling(fast).mean()
                sma_slow = stock_close.rolling(slow).mean()
                signal = (sma_fast > sma_slow).astype(int)
                signal_shift = signal.shift(1).fillna(0)
                daily_ret = stock_close.pct_change().fillna(0)
                strat_ret = daily_ret * signal_shift
                cumulative = (1 + strat_ret).cumprod()
                total_return = float((cumulative.iloc[-1] - 1) * 100) if len(cumulative) > 0 else 0
                std = float(strat_ret.std()) if strat_ret.std() > 0 else 0.001
                sharpe = float(strat_ret.mean() / std * (252 ** 0.5))
                max_dd = float(((cumulative / cumulative.cummax()) - 1).min() * 100)
                trades = int(signal.diff().abs().sum() / 2)

                entry = {
                    "params": {"fastPeriod": fast, "slowPeriod": slow},
                    "score": round(sharpe, 4),
                    "totalReturn": round(total_return, 2),
                    "sharpe": round(sharpe, 4),
                }
                grid_results.append(entry)

                if sharpe > best_score:
                    best_score = sharpe
                    best_params = {"fastPeriod": fast, "slowPeriod": slow}
                    best_total_return = total_return
                    best_max_dd = max_dd
                    best_trades = trades

        grid_results.sort(key=lambda x: x["score"], reverse=True)

        return {
            "bestParams": best_params,
            "bestScore": round(best_score, 4),
            "totalReturn": round(best_total_return, 2) if best_params else 0,
            "sharpe": round(best_score, 4),
            "maxDrawdown": round(best_max_dd, 2) if best_params else 0,
            "winRate": 0,
            "tradeCount": best_trades if best_params else 0,
            "grid": grid_results[:50],
        }

    loop = _asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run_grid)
        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"優化失敗: {exc}")


# /predictions/*, /strategies/saved/* 已抽出到 api/routers/


# /settings 已抽出到 api/routers/settings.py


# ════════════════════════════════════════════════════════
# 第五批：即時與社群
# ════════════════════════════════════════════════════════

# /quote/realtime/* 已抽出到 api/routers/quote.py
# /news/latest 與 /social/hot-stocks 已抽出到 api/routers/{news,social}.py


# ════════════════════════════════════════════════════════
# 第六批：風險
# ════════════════════════════════════════════════════════

@app.get("/risk/stock/{stock_id}", tags=["風險"], dependencies=[Depends(verify_api_key)])
async def risk_stock(
    stock_id: str,
    days: int = Query(default=252, ge=60, le=1260, description="計算用歷史天數"),
):
    """
    個股風險指標 - VaR、CVaR、波動率、最大回撤、Beta。

    範例: /risk/stock/2330?days=252
    """
    try:
        from core.risk import RiskAnalyzer
        close = loader.get("close")
        if stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

        series = close[stock_id].dropna().tail(days)
        benchmark = loader.get_benchmark().reindex(series.index).dropna()

        analyzer = RiskAnalyzer()
        metrics = analyzer.analyze(series, benchmark_prices=benchmark if len(benchmark) > 10 else None)

        return {
            "stock_id": stock_id,
            "days": len(series),
            "date_range": {
                "start": series.index[0].strftime("%Y-%m-%d"),
                "end": series.index[-1].strftime("%Y-%m-%d"),
            },
            "risk_metrics": {
                "var_95": _safe_json(metrics.var_95),
                "var_99": _safe_json(metrics.var_99),
                "cvar_95": _safe_json(metrics.cvar_95),
                "cvar_99": _safe_json(metrics.cvar_99),
                "volatility": _safe_json(metrics.volatility),
                "downside_volatility": _safe_json(metrics.downside_volatility),
                "max_drawdown": _safe_json(metrics.max_drawdown),
                "beta": _safe_json(metrics.beta),
                "tracking_error": _safe_json(metrics.tracking_error),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/risk/portfolio", tags=["風險"], dependencies=[Depends(verify_api_key)])
async def risk_portfolio(req: PortfolioRiskRequest):
    """
    投資組合風險分析 - 計算加權 VaR 及組合波動率。

    請求格式:
    ```json
    {
      "holdings": [{"stock_id": "2330", "weight": 0.5}, {"stock_id": "2317", "weight": 0.5}],
      "days": 252
    }
    ```
    """
    try:
        from core.risk import RiskAnalyzer, calculate_portfolio_var

        if not req.holdings:
            raise HTTPException(status_code=400, detail="請提供至少一個持股")

        close = loader.get("close")

        # 正規化權重
        total_weight = sum(h.get("weight", 1) for h in req.holdings)
        weights = {
            h["stock_id"]: h.get("weight", 1) / total_weight
            for h in req.holdings
            if h.get("stock_id") in close.columns
        }

        if not weights:
            raise HTTPException(status_code=400, detail="所有股票代號均找不到")

        # 取報酬率
        valid_ids = list(weights.keys())
        returns_df = close[valid_ids].tail(req.days).pct_change().dropna()

        portfolio_var_95 = calculate_portfolio_var(weights, returns_df, 0.95) * 100
        portfolio_var_99 = calculate_portfolio_var(weights, returns_df, 0.99) * 100

        # 加權波動率
        analyzer = RiskAnalyzer()
        weighted_vol = sum(
            weights[sid] * analyzer.calculate_volatility(returns_df[sid].dropna())
            for sid in valid_ids if sid in returns_df.columns
        )

        # 組合每日報酬
        weighted_returns = sum(
            returns_df[sid] * weights[sid] for sid in valid_ids if sid in returns_df.columns
        )

        portfolio_prices = (1 + weighted_returns).cumprod()
        max_dd, peak_date, trough_date = analyzer.calculate_max_drawdown(portfolio_prices)

        # 個股風險概要
        stock_risks = []
        for sid in valid_ids:
            if sid not in returns_df.columns:
                continue
            m = analyzer.analyze(close[sid].dropna().tail(req.days))
            stock_risks.append({
                "stock_id": sid,
                "weight": round(weights[sid], 4),
                "volatility": _safe_json(m.volatility),
                "var_95": _safe_json(m.var_95),
                "max_drawdown": _safe_json(m.max_drawdown),
            })

        return {
            "days": req.days,
            "holdings": len(weights),
            "portfolio_risk": {
                "var_95": round(float(portfolio_var_95), 4) if portfolio_var_95 is not None else None,
                "var_99": round(float(portfolio_var_99), 4) if portfolio_var_99 is not None else None,
                "weighted_volatility": round(weighted_vol * 100, 4) if weighted_vol is not None else None,
                "max_drawdown": round(float(max_dd) * 100, 4) if max_dd is not None else None,
                "peak_date": peak_date.strftime("%Y-%m-%d") if peak_date else None,
                "trough_date": trough_date.strftime("%Y-%m-%d") if trough_date else None,
            },
            "stock_risks": stock_risks,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/morning-report", tags=["報告"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=600)
async def morning_report():
    """
    產生每日晨報摘要，包含市場概況、漲跌排行、策略選股結果、新聞摘要。
    OpenClaw 可每日早上自動呼叫此端點取得晨報。

    回傳欄位包含前端所需的 summary、keyPoints、marketOutlook。
    """
    close = loader.get("close")
    active = get_active_stocks()

    latest = close[active].iloc[-1]
    prev = close[active].iloc[-2]
    changes = ((latest - prev) / prev * 100).dropna()

    top_gainers = changes.nlargest(5)
    top_losers = changes.nsmallest(5)

    strategies_summary = {}
    for stype in ("value", "growth", "momentum"):
        try:
            resp = await run_strategy(stype, preset="standard", top_n=5)
            strategies_summary[stype] = {
                "total": resp["total_matches"],
                "top5": [s["stock_id"] for s in resp["stocks"][:5]],
            }
        except Exception:
            strategies_summary[stype] = {"total": 0, "top5": []}

    summary = get_data_summary()

    # ── 新聞摘要 ──────────────────────────────────────────
    news_summary = []
    news_key_points = []
    market_outlook = ""

    try:
        from core.news_scanner import NewsScanner
        cache_path = DATA_DIR / "news_cache.json"
        CACHE_TTL_SECONDS = 600

        cache_valid = False
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    news_cache = json.load(f)
                updated_at_str = news_cache.get("updated_at") if isinstance(news_cache, dict) else None
                if updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    if (datetime.now() - updated_at).total_seconds() < CACHE_TTL_SECONDS:
                        cache_valid = True
            except Exception:
                cache_valid = False

        if not cache_valid:
            try:
                scanner = NewsScanner()
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, scanner.fetch_all_feeds),
                    timeout=25.0,
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"晨報新聞掃描失敗: {e}")

        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                news_cache = json.load(f)
            raw_news = news_cache.get("news", []) if isinstance(news_cache, dict) else []

            # 取最新 5 則新聞作為重點
            for item in raw_news[:5]:
                title = item.get("title", "")
                if title:
                    news_key_points.append(title)

            # 統計情緒分佈作為展望
            pos_count = sum(1 for n in raw_news if n.get("sentiment") == "positive")
            neg_count = sum(1 for n in raw_news if n.get("sentiment") == "negative")
            total_news = len(raw_news)

            if total_news > 0:
                if pos_count > neg_count * 1.5:
                    market_outlook = f"今日新聞偏多（{pos_count}/{total_news} 則正面），市場情緒樂觀。"
                elif neg_count > pos_count * 1.5:
                    market_outlook = f"今日新聞偏空（{neg_count}/{total_news} 則負面），留意下行風險。"
                else:
                    market_outlook = f"今日新聞情緒中性（共 {total_news} 則），觀望為宜。"

    except Exception as e:
        logger.error(f"晨報新聞整合失敗: {e}")

    # ── 組合摘要文字 ──────────────────────────────────────
    taiex_index = _safe_json(summary.get("taiex_index"))
    taiex_change = _safe_json(summary.get("taiex_change"))
    up_count = int((changes > 0).sum())
    down_count = int((changes < 0).sum())

    if taiex_index and taiex_change is not None:
        direction = "上漲" if taiex_change >= 0 else "下跌"
        summary_text = (
            f"台股加權指數 {taiex_index:,.0f} 點，{direction} {abs(taiex_change):.2f}%。"
            f"上漲家數 {up_count}，下跌家數 {down_count}。"
        )
    else:
        summary_text = f"上漲家數 {up_count}，下跌家數 {down_count}。"

    return {
        "date": summary.get("latest_date"),
        # 前端晨報摘要區塊所需欄位
        "summary": summary_text,
        "keyPoints": news_key_points,
        "marketOutlook": market_outlook,
        # 市場數據
        "taiex_index": taiex_index,
        "taiex_change": taiex_change,
        "market": {
            "up": up_count,
            "down": down_count,
            "flat": int((changes == 0).sum()),
        },
        "top_gainers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_gainers.items()
        ],
        "top_losers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_losers.items()
        ],
        "strategies": strategies_summary,
    }


# ─── 遺珠掃描器 ─────────────────────────────────────────

@app.get("/scanner/hidden-gems", tags=["策略"], dependencies=[Depends(verify_api_key)])
@cached_response(ttl_seconds=14400)  # 4 小時快取（盤後資料每日更新一次）
async def scanner_hidden_gems():
    """
    遺珠掃描器 — 全盤掃描台股市場，找出被忽略但潛力巨大的股票。

    掃描 6 大面向：低估價值、營收爆發、法人布局、技術反轉、小型成長、籌碼集中。
    計算量大，結果快取 1 小時。
    """
    from core.hidden_gems import HiddenGemsScanner

    loop = asyncio.get_event_loop()

    def _scan():
        scanner = HiddenGemsScanner()
        return scanner.scan(loader)

    result = await loop.run_in_executor(None, _scan)
    return result


# ─── 啟動 ───────────────────────────────────────────────

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
