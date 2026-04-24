"""回測端點：POST /backtest/run"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _get_industry_map, _get_stock_name_map, _safe_json
from api.models import BacktestRequest
from api.state import loader
from api.routers.strategy import run_strategy
from core.backtest.engine import BacktestEngine
from core.strategies.growth import GrowthStrategy
from core.strategies.momentum import MomentumStrategy
from core.strategies.value import ValueStrategy

logger = logging.getLogger(__name__)

router = APIRouter(tags=["回測"], dependencies=[Depends(verify_api_key)])


@router.post("/backtest/run")
async def backtest_run(req: BacktestRequest):
    """
    執行策略回測。

    支援 value / growth / momentum 三種策略，可自訂初始資金、換股頻率。
    計算耗時較長（5-30 秒），請勿在高頻場景下呼叫。
    """
    try:
        from config import STRATEGY_PRESETS

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
