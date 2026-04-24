"""即時報價端點：/quote/realtime/*"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import verify_api_key
from api.helpers import _get_stock_name_map
from api.state import loader, multi_source

logger = logging.getLogger(__name__)

router = APIRouter(tags=["報價"], dependencies=[Depends(verify_api_key)])


class BatchQuoteRequest(BaseModel):
    stock_ids: List[str] = Field(..., description="股票代號列表", max_items=50)


@router.get("/quote/realtime/{stock_id}")
async def quote_realtime(stock_id: str):
    """個股即時報價（以最新收盤價模擬，無法取得真實盤中資料時的 fallback）。"""
    from core.data_loader import _finlab_quota_exceeded

    # Fallback: FinLab 額度超限時改用 TWSE 即時報價
    if _finlab_quota_exceeded:
        logger.info("[quote] FinLab 額度超限，走 TWSE fallback: %s", stock_id)
        twse = multi_source.get_realtime_quote(stock_id)
        if twse:
            price = twse.get("price") or 0
            prev = twse.get("yesterday_close") or price
            change = price - prev
            change_pct = (change / prev * 100) if prev > 0 else 0
            return {
                "stock_id": stock_id,
                "name": twse.get("name", ""),
                "price": round(price, 2),
                "prev_close": round(prev, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "high": round(twse.get("high") or 0, 2) or None,
                "low": round(twse.get("low") or 0, 2) or None,
                "volume": twse.get("volume"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "is_realtime": True,
                "note": "資料來自 TWSE 即時報價 (fallback)",
                "source": "twse",
            }
        raise HTTPException(status_code=503, detail="FinLab 額度超限且 TWSE 即時報價無資料")

    try:
        close = loader.get("close")
        if stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

        series = close[stock_id].dropna()
        latest = float(series.iloc[-1])
        prev = float(series.iloc[-2]) if len(series) >= 2 else latest
        change = latest - prev
        change_pct = (change / prev * 100) if prev > 0 else 0

        name_map = _get_stock_name_map()

        high_price = low_price = None
        try:
            high_df = loader.get("high")
            low_df = loader.get("low")
            if stock_id in high_df.columns:
                high_price = round(float(high_df[stock_id].dropna().iloc[-1]), 2)
            if stock_id in low_df.columns:
                low_price = round(float(low_df[stock_id].dropna().iloc[-1]), 2)
        except Exception:
            pass

        volume = None
        try:
            vol_df = loader.get("volume")
            if stock_id in vol_df.columns:
                volume = int(vol_df[stock_id].dropna().iloc[-1])
        except Exception:
            pass

        return {
            "stock_id": stock_id,
            "name": name_map.get(stock_id, ""),
            "price": round(latest, 2),
            "prev_close": round(prev, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "high": high_price,
            "low": low_price,
            "volume": volume,
            "date": series.index[-1].strftime("%Y-%m-%d"),
            "is_realtime": False,
            "note": "資料為最新交易日收盤價",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quote/realtime/batch")
async def quote_realtime_batch(req: BatchQuoteRequest):
    """批次取得多股即時報價，一次最多 50 支。"""
    from core.data_loader import _finlab_quota_exceeded

    if _finlab_quota_exceeded:
        logger.info("[batch_quote] FinLab 額度超限，走 TWSE fallback: %d 支", len(req.stock_ids))
        twse_results = multi_source.get_realtime_batch(req.stock_ids)
        quotes = []
        for item in twse_results:
            price = item.get("price") or 0
            prev = item.get("yesterday_close") or price
            change_pct = ((price - prev) / prev * 100) if prev > 0 else 0
            quotes.append({
                "stock_id": item.get("stock_id", ""),
                "name": item.get("name", ""),
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
            })
        return {
            "total": len(quotes),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "quotes": quotes,
            "source": "twse",
        }

    try:
        close = loader.get("close")
        name_map = _get_stock_name_map()
        valid_ids = [sid for sid in req.stock_ids if sid in close.columns]

        if not valid_ids:
            return {"total": 0, "quotes": []}

        latest = close[valid_ids].iloc[-1]
        prev = close[valid_ids].iloc[-2]
        changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

        quotes = []
        for sid in valid_ids:
            quotes.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "price": round(float(latest.get(sid, 0) or 0), 2),
                "change_pct": round(float(changes.get(sid, 0) or 0), 2),
            })

        return {
            "total": len(quotes),
            "date": close.index[-1].strftime("%Y-%m-%d"),
            "quotes": quotes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
