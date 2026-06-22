"""策略端點：/strategy/*

包含：
- /strategy/ai-claude/{id}     Claude 深度分析
- /strategy/ai-lstm/{id}       LSTM 預測（無 torch 時降級為 EWMA）
- /strategy/ai-xgboost         XGBoost 多股排序
- /strategy/ai-pick            綜合 AI 選股
- /strategy/composite          傳統綜合策略
- /strategy/{type}             單策略選股（value / growth / momentum）+ run_strategy

run_strategy 供其他 router（market/after-hours、morning-report、screener）
以函式呼叫方式重用。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _get_stock_name_map, cached_response
from api.state import loader
from core.data_loader import get_active_stocks
from core.indicators import calculate_rsi
from core.strategies.value import ValueStrategy
from core.strategies.growth import GrowthStrategy
from core.strategies.momentum import MomentumStrategy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略"], dependencies=[Depends(verify_api_key)])


# ─── Claude AI 個股分析（lazy singleton）─────────────────
_claude_analyzer = None


def _get_claude_analyzer():
    """Lazy init ClaudeStockAnalyzer。"""
    global _claude_analyzer
    if _claude_analyzer is None:
        from core.ai_models import ClaudeStockAnalyzer
        _claude_analyzer = ClaudeStockAnalyzer()
    return _claude_analyzer


@router.get("/strategy/ai-claude/{stock_id}")
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


@router.get("/strategy/ai-lstm/{stock_id}")
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


@router.get("/strategy/ai-xgboost")
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

    # 取前 top_n，補上股票名稱與目前股價，清理 NaN/inf
    top_results = all_results[:top_n]
    try:
        close = loader.get("close")
    except Exception:
        close = None
    for item in top_results:
        sid = item["stock_id"]
        item["name"] = name_map.get(sid, "")
        # 補上目前股價（最新收盤）；取不到時為 None
        try:
            series = close[sid].dropna() if (close is not None and sid in close.columns) else None
            item["price"] = round(float(series.iloc[-1]), 2) if series is not None and not series.empty else None
        except Exception:
            item["price"] = None
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


@router.get("/strategy/ai-xgboost/backtest")
async def strategy_ai_xgboost_backtest():
    """XGBoost 選股的 walk-forward 回測結果（命中率 / IC / 超額報酬）。

    讀取最近一次計算結果（由排程或 scripts/backtest_xgboost.py 產生）；
    本端點不即時重算（回測很重），只讀快取結果。
    """
    from core.xgboost_backtest import load_result

    res = load_result()
    if res is None:
        return {
            "status": "not_computed",
            "note": "尚未計算回測。可執行 scripts/backtest_xgboost.py，或啟用排程後等待產生。",
        }
    return {"status": "ok", **res}


@router.get("/strategy/ai-xgboost/live-accuracy")
async def strategy_ai_xgboost_live_accuracy(
    days: int = Query(default=180, ge=1, le=730, description="統計最近 N 天記錄的選股"),
):
    """XGBoost 選股的「前向追蹤」命中率：由排程定期記錄選股、到期後驗證實際報酬。

    與 /backtest（歷史回測）互補，這是即時下注、未來驗證的真實 track record。
    剛上線時資料量少，需累積數週後才有統計意義。
    """
    from core.prediction_tracker import get_tracker

    stats = get_tracker().get_statistics(days=days, prediction_type="stock_pick")
    return {"source": "xgboost", "days": days, "stats": stats}


# ════════════════════════════════════════════════════════
# AI 工具端點
# ════════════════════════════════════════════════════════

@router.get("/strategy/ai-pick")
@cached_response(ttl_seconds=600)
async def strategy_ai_pick_early(
    top_n: int = Query(default=10, ge=1, le=30, description="每策略回傳前 N 檔"),
):
    """AI 選股 - 整合三大策略，取各策略前 N 名並進行綜合評分。(路由前置版)"""
    # Lazy import: backtest.py 已 import strategy.py 的 run_strategy，避免循環
    from api.routers.backtest import strategy_ai_pick
    return await strategy_ai_pick(top_n=top_n)


@router.get("/strategy/composite")
@cached_response(ttl_seconds=600)
async def strategy_composite_early(
    top_n: int = Query(default=20, ge=1, le=50),
):
    """綜合策略選股 - 計算每支股票在三大策略的綜合排名分數。(路由前置版)"""
    from api.routers.backtest import strategy_composite
    return await strategy_composite(top_n=top_n)


class StrategyType(str, Enum):
    value = "value"
    growth = "growth"
    momentum = "momentum"

@router.get("/strategy/{strategy_type}")
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

