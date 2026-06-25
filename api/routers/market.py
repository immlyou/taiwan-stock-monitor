"""市場端點：/market/summary, /market/heatmap, /market/money-flow,
/market/benchmark, /market/industries

/market/after-hours 尚未抽出，因為依賴 api_server.run_strategy。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import (
    _get_industry_map,
    _get_stock_name_map,
    _safe_json,
    cached_response,
)
from api.state import loader
from api.routers.strategy import run_strategy
from core.data_loader import get_active_stocks, get_data_summary
from core.intelligence import calculate_industry_rotation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["市場"], dependencies=[Depends(verify_api_key)])


@router.get("/market/summary")
@cached_response(ttl_seconds=60)
async def market_summary():
    """市場總覽 - 取得大盤指數、上漲/下跌家數等摘要資訊。"""
    from core.data_loader import _finlab_quota_exceeded

    # Fallback: FinLab 額度超限時改用 TWSE 大盤指數
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

    # 大盤指數：用資料集自帶的報酬指數序列（與上面漲跌家數同一份 close 資料、
    # 同一時間軸），不再混用即時 TWSE 價格指數——否則 ticker 會拿不同日期的指數
    # 與漲跌，造成「+0.00% 綠燈」對上「-2.23% 紅盤」的矛盾。
    taiex_index = taiex_change = taiex_change_pct = None
    try:
        benchmark = loader.get_benchmark()
        if benchmark is not None and len(benchmark) >= 2:
            cur = float(benchmark.iloc[-1])
            prev = float(benchmark.iloc[-2])
            taiex_index = round(cur, 2)
            taiex_change = round(cur - prev, 2)
            taiex_change_pct = round((cur - prev) / prev * 100, 2) if prev else None
    except Exception:
        logger.warning("market_summary 取得報酬指數失敗", exc_info=True)

    return {
        "date": summary.get("latest_date"),
        "taiex_index": _safe_json(taiex_index),
        "taiex_change": _safe_json(taiex_change),
        "taiex_change_pct": _safe_json(taiex_change_pct),
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


@router.get("/market/heatmap")
@cached_response(ttl_seconds=300)
async def market_heatmap():
    """市場熱力圖資料 - 依產業分組，顯示各股漲跌幅。"""
    try:
        close = loader.get("close")
        active = get_active_stocks()
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()

        latest = close[active].iloc[-1]
        prev = close[active].iloc[-2]
        changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

        industry_groups: Dict[str, list] = {}
        for sid in active:
            industry = industry_map.get(sid, "其他")
            raw_price = latest.get(sid, 0)
            raw_change = changes.get(sid, 0)
            price = 0.0 if (pd.isna(raw_price) or np.isinf(raw_price)) else float(raw_price)
            change = 0.0 if (pd.isna(raw_change) or np.isinf(raw_change)) else float(raw_change)
            if price <= 0:
                continue
            industry_groups.setdefault(industry, []).append({
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


@router.get("/market/money-flow")
@cached_response(ttl_seconds=300)
async def market_money_flow():
    """市場資金流向 - 三大法人買賣超統計。"""
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


@router.get("/market/benchmark")
async def market_benchmark(
    days: int = Query(default=252, ge=20, le=1260, description="取得最近 N 個交易日"),
):
    """大盤指數時序資料 — 回傳加權股價報酬指數歷史數據。"""
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


@router.get("/market/industries")
@cached_response(ttl_seconds=300)
async def market_industries():
    """產業列表與各產業統計。"""
    try:
        active = get_active_stocks()
        close = loader.get("close")
        industry_map = _get_industry_map()

        latest = close[active].iloc[-1]
        prev = close[active].iloc[-2]
        changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

        industry_stats: Dict[str, Dict] = {}
        for sid in active:
            ind = industry_map.get(sid, "其他")
            if ind not in industry_stats:
                industry_stats[ind] = {"count": 0, "changes": []}
            industry_stats[ind]["count"] += 1
            industry_stats[ind]["changes"].append(float(changes.get(sid, 0) or 0))

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


@router.get("/market/industry-rotation")
@cached_response(ttl_seconds=300)
async def market_industry_rotation(
    top_n: int = Query(default=30, ge=1, le=100, description="回傳產業數量"),
):
    """產業輪動雷達：短中期動能、廣度與領先/改善/轉弱/落後象限。"""
    try:
        return calculate_industry_rotation(loader, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/market/after-hours")
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
