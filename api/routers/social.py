"""社群端點：/social/hot-stocks"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _get_stock_name_map, cached_response
from api.state import loader
from core.data_loader import get_active_stocks

logger = logging.getLogger(__name__)

router = APIRouter(tags=["社群"], dependencies=[Depends(verify_api_key)])


@router.get("/social/hot-stocks")
@cached_response(ttl_seconds=600)
async def social_hot_stocks(
    top_n: int = Query(default=20, ge=1, le=50),
):
    """社群熱門股票 - 結合新聞熱度、成交量異常、價格動能的熱門排行。

    使用 HotStockAnalyzer 計算綜合熱門分數；失敗時降級為成交量倍數排行。
    """
    try:
        from core.hot_stocks import HotStockAnalyzer
        analyzer = HotStockAnalyzer()
        hot_stocks = analyzer.get_hot_stocks(top_n=top_n)
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total": len(hot_stocks),
            "hot_stocks": [
                {
                    "stock_id": s.stock_id,
                    "name": s.name,
                    "industry": s.industry,
                    "total_score": round(s.total_score, 2),
                    "news_score": round(s.news_score, 2),
                    "volume_score": round(s.volume_score, 2),
                    "momentum_score": round(s.momentum_score, 2),
                    "volume_ratio": round(s.volume_ratio, 2),
                    "price_change_5d": round(s.price_change_5d, 2),
                    "current_price": round(s.current_price, 2),
                    "tags": s.tags,
                }
                for s in hot_stocks
            ],
        }
    except Exception:
        # 降級：使用成交量異常排行
        try:
            active = get_active_stocks()
            close = loader.get("close")
            vol_df = loader.get("volume")
            name_map = _get_stock_name_map()

            vol_latest = vol_df[active].iloc[-1]
            vol_avg = vol_df[active].tail(21).iloc[:-1].mean()
            vol_ratio = (vol_latest / vol_avg.replace(0, np.nan)).fillna(0)
            top = vol_ratio.nlargest(top_n)

            latest = close[active].iloc[-1]
            prev = close[active].iloc[-2]
            changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total": len(top),
                "hot_stocks": [
                    {
                        "stock_id": sid,
                        "name": name_map.get(sid, ""),
                        "volume_ratio": round(float(ratio), 2),
                        "change_pct": round(float(changes.get(sid, 0) or 0), 2),
                        "total_score": round(float(ratio) * 10, 2),
                    }
                    for sid, ratio in top.items()
                ],
                "note": "HotStockAnalyzer 不可用，以成交量倍數替代",
            }
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))
