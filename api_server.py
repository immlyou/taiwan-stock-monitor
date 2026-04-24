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

# 讓 /market/after-hours 與 /morning-report（尚未拆分）能呼叫 run_strategy
run_strategy = strategy_router.run_strategy


# ════════════════════════════════════════════════════════
# 第一批：通用 + 市場資料
# ════════════════════════════════════════════════════════


# /stocks/list, /stocks/search, /stocks/active 已抽出到 api/routers/stocks.py


# /market/summary, /heatmap, /money-flow 已抽出到 api/routers/market.py


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


# /market/benchmark 與 /market/industries 已抽出到 api/routers/market.py


# ════════════════════════════════════════════════════════
# 個股查詢（原有端點保持不變）
# /stock/{id}/* 已抽出到 api/routers/stock.py


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


# /strategy/* 與 /ai/* 已抽出到 api/routers/{strategy,ai}.py
# _claude_analyzer singleton 亦搬遷至 api/routers/strategy.py


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


# /risk/stock/{id} 與 /risk/portfolio 已抽出到 api/routers/risk.py


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


# /scanner/hidden-gems 已抽出到 api/routers/scanner.py


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
