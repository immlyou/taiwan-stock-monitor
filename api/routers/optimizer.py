"""參數優化端點：POST /optimizer/run (Grid Search)"""
from __future__ import annotations

import logging
import numpy as np
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from api.deps import verify_api_key
from api.state import loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略"], dependencies=[Depends(verify_api_key)])


@router.post("/optimizer/run")
async def optimizer_run(body: Dict[str, Any] = Body(...)):
    """Grid Search 參數優化 — 暴力窮舉回測找最佳參數組合。"""
    import asyncio as _asyncio

    strategy = body.get("strategy", "ma_crossover")
    if strategy != "ma_crossover":
        raise HTTPException(status_code=422, detail="目前僅實作均線交叉優化，不支援此策略")
    stock_code = body.get("stockCode", "2330")
    start_date = body.get("startDate", "2023-01-01")
    end_date = body.get("endDate", "2024-12-31")
    ranges = body.get("ranges", {})
    if not isinstance(ranges, dict) or set(ranges) - {"fastPeriod", "slowPeriod"}:
        raise HTTPException(status_code=422, detail="僅支援快線與慢線週期，其他參數尚未實作")
    for key, default_min, default_max in (("fastPeriod", 3, 15), ("slowPeriod", 10, 40)):
        value = ranges.get(key, {})
        if not isinstance(value, dict):
            raise HTTPException(status_code=422, detail="參數範圍格式不正確")
        low, high = value.get("min", default_min), value.get("max", default_max)
        if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 252:
            raise HTTPException(status_code=422, detail="週期必須為 1–252 的整數且最小值不大於最大值")
    grid_size = (ranges.get("fastPeriod", {}).get("max", 15) - ranges.get("fastPeriod", {}).get("min", 3) + 1) * ((ranges.get("slowPeriod", {}).get("max", 40) - ranges.get("slowPeriod", {}).get("min", 10)) // 5 + 1)
    if grid_size > 2000:
        raise HTTPException(status_code=422, detail="參數組合上限為 2000，請縮小範圍")

    def _run_grid():
        close = loader.get("close")
        if stock_code not in close.columns:
            return {"error": f"找不到股票 {stock_code}"}

        stock_close = close[stock_code].sort_index().loc[start_date:end_date]
        if not np.isfinite(stock_close.to_numpy()).all() or (stock_close <= 0).any():
            return {"error": "此區間包含缺漏或無效股價，請調整日期；不以補值或壓縮交易日回測"}
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
                # T-close signal -> T+1-close execution -> returns earned from T+2.
                position = signal.shift(1).fillna(0)
                signal_shift = position.shift(1).fillna(0)
                daily_ret = stock_close.pct_change(fill_method=None).fillna(0)
                changes = position.diff().fillna(position)
                costs = changes.clip(lower=0) * .002425 + (-changes.clip(upper=0)) * .005425
                strat_ret = (1 + daily_ret * signal_shift) * (1 - costs) - 1
                cumulative = (1 + strat_ret).cumprod()
                total_return = float((cumulative.iloc[-1] - 1) * 100) if len(cumulative) > 0 else 0
                std = float(strat_ret.std()) if strat_ret.std() > 0 else 0.001
                sharpe = float(strat_ret.mean() / std * (252 ** 0.5))
                max_dd = float(((cumulative / cumulative.cummax()) - 1).min() * 100)
                trades = int((changes < 0).sum())

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
        if not grid_results:
            return {"error": "沒有快線小於慢線的有效參數組合"}

        return {
            "bestParams": best_params,
            "bestScore": round(best_score, 4),
            "totalReturn": round(best_total_return, 2) if best_params else 0,
            "sharpe": round(best_score, 4),
            "maxDrawdown": round(best_max_dd, 2) if best_params else 0,
            "winRate": None,
            "validation_status": "in_sample_only",
            "note": "樣本內參數搜尋，非樣本外績效。次日收盤成交；費用含買方 0.1425%／賣方 0.4425% 及每邊 10bps 滑價情境，未模擬最低手續費與成交限制。",
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
