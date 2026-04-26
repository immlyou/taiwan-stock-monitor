"""AI trading radar endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import cached_response
from api.state import loader
from core.trading_radar import TradingRadar

router = APIRouter(tags=["操盤雷達"], dependencies=[Depends(verify_api_key)])


@router.get("/radar/stocks")
@cached_response(ttl_seconds=1800)
async def radar_stocks(
    top_n: int = Query(default=50, ge=1, le=200, description="回傳前 N 筆操盤雷達訊號"),
):
    """AI 操盤雷達清單：主力吸籌、營收爆發、出貨風險、進場等待區與每日觀察。"""
    loop = asyncio.get_event_loop()

    def _scan():
        return TradingRadar(loader).scan(top_n=top_n)

    try:
        return await loop.run_in_executor(None, _scan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/stock/{stock_id}")
async def radar_stock(stock_id: str):
    """單一個股 AI 操盤雷達。"""
    try:
        return TradingRadar(loader).analyze_stock(stock_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
