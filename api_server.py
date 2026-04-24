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
