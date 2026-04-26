"""選股篩選端點：/screener"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.state import loader
from core.data_loader import get_active_stocks
from core.indicators import calculate_rsi
from core.stock_score import calculate_top_scores

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略"], dependencies=[Depends(verify_api_key)])


@router.get("/screener/scores")
async def screener_scores(
    top_n: int = Query(default=50, ge=1, le=200, description="回傳前 N 名量化評分股票"),
):
    """全市場量化評分排行。"""
    try:
        return calculate_top_scores(loader, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screener")
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
