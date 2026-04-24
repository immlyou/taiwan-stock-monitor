"""參數優化端點：POST /optimizer/run (Grid Search)"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from api.deps import verify_api_key
from api.state import loader
from core.backtest.engine import BacktestEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略"], dependencies=[Depends(verify_api_key)])


@router.post("/optimizer/run")
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

