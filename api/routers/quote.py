"""即時報價端點：Fugle → TWSE → FinLab 收盤 fallback。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api.deps import verify_api_key
from api.helpers import _get_stock_name_map
from api.state import quote_service


router = APIRouter(tags=["報價"], dependencies=[Depends(verify_api_key)])


class BatchQuoteRequest(BaseModel):
    stock_ids: List[str] = Field(..., description="股票代號列表", min_length=1, max_length=50)


def _with_names(quotes: List[dict]) -> List[dict]:
    """Fill names only when a live provider did not include one."""
    if all(item.get("name") for item in quotes):
        return quotes
    try:
        name_map = _get_stock_name_map()
    except Exception:
        name_map = {}
    return [
        {**item, "name": item.get("name") or name_map.get(item.get("stock_id", ""), "")}
        for item in quotes
    ]


@router.get("/quote/realtime/{stock_id}")
async def quote_realtime(stock_id: str):
    """取得一檔標準化報價；外部同步 HTTP 工作不阻塞 event loop。"""
    normalized_id = stock_id.strip().upper()
    quote = await run_in_threadpool(quote_service.get_quote, normalized_id)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"找不到股票報價: {normalized_id}")
    return _with_names([quote])[0]


@router.post("/quote/realtime/batch")
async def quote_realtime_batch(req: BatchQuoteRequest):
    """批次取得最多 50 檔標準化報價，允許不同股票由不同 fallback 層補齊。"""
    stock_ids = list(dict.fromkeys(sid.strip().upper() for sid in req.stock_ids if sid.strip()))
    if not stock_ids:
        raise HTTPException(status_code=422, detail="stock_ids 不可為空")

    quotes = await run_in_threadpool(quote_service.get_quotes, stock_ids)
    quotes = _with_names(quotes)
    sources = list(dict.fromkeys(item.get("source", "unknown") for item in quotes))
    has_realtime = any(bool(item.get("is_realtime")) for item in quotes)
    market_state = "trading" if has_realtime else (
        quotes[0].get("market_state", "closed") if quotes else "closed"
    )
    return {
        "total": len(quotes),
        "requested": len(stock_ids),
        "date": quotes[0].get("date") if quotes else None,
        "market_state": market_state,
        "has_realtime": has_realtime,
        "sources": sources,
        "quotes": quotes,
    }
