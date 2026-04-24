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
from api.routers import risk as risk_router
from api.routers import scanner as scanner_router
from api.routers import market as market_router
from api.routers import stock as stock_router
from api.routers import strategy as strategy_router
from api.routers import ai as ai_router
from api.routers import screener as screener_router
from api.routers import backtest as backtest_router
from api.routers import optimizer as optimizer_router
from api.routers import reports as reports_router

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
app.include_router(risk_router.router)
app.include_router(scanner_router.router)
app.include_router(market_router.router)
app.include_router(stock_router.router)
app.include_router(strategy_router.router)
app.include_router(ai_router.router)
app.include_router(screener_router.router)
app.include_router(backtest_router.router)
app.include_router(optimizer_router.router)
app.include_router(reports_router.router)


# ════════════════════════════════════════════════════════
# 第一批：通用 + 市場資料
# ════════════════════════════════════════════════════════


# /stocks/list, /stocks/search, /stocks/active 已抽出到 api/routers/stocks.py


# /market/summary, /heatmap, /money-flow 已抽出到 api/routers/market.py


# /market/after-hours, /stocks/compare, /screener, /backtest/run,
# /optimizer/run, /morning-report 已抽出到 api/routers/
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
