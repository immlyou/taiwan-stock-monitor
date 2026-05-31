"""股票清單端點：/stocks/list, /stocks/search, /stocks/active"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _get_industry_map, _get_stock_name_map, cached_response
from api.state import loader
from core.data_loader import get_active_stocks

logger = logging.getLogger(__name__)

router = APIRouter(tags=["股票"], dependencies=[Depends(verify_api_key)])


@router.get("/stocks/list")
@cached_response(ttl_seconds=3600)
async def stocks_list():
    """取得全部股票清單，包含代號與名稱。

    回傳所有在資料庫中的股票（含已下市），搭配類別資訊。
    """
    try:
        close = loader.get("close")
        all_ids = [col for col in close.columns if col != "date"]
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()

        return {
            "total": len(all_ids),
            "stocks": [
                {
                    "stock_id": sid,
                    "name": name_map.get(sid, ""),
                    "industry": industry_map.get(sid, ""),
                }
                for sid in all_ids
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/search")
async def stocks_search(
    q: str = Query(..., description="搜尋關鍵字（代號或名稱）", min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """搜尋股票（依代號或名稱模糊比對）。"""
    try:
        close = loader.get("close")
        all_ids = [col for col in close.columns if col != "date"]
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()
        q_lower = q.lower()

        results = []
        for sid in all_ids:
            name = name_map.get(sid, "")
            if q_lower in sid.lower() or q_lower in name.lower():
                results.append({
                    "stock_id": sid,
                    "name": name,
                    "industry": industry_map.get(sid, ""),
                })
            if len(results) >= limit:
                break

        return {"query": q, "total": len(results), "stocks": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/active")
@cached_response(ttl_seconds=3600)
async def stocks_active():
    """取得仍在交易的活躍股票清單（排除已下市）。

    以近 30 天內有交易資料為判斷標準。
    """
    try:
        active = get_active_stocks()
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()
        close = loader.get("close")

        latest = close[active].iloc[-1]
        prev = close[active].iloc[-2]
        changes = ((latest - prev) / prev * 100).replace([float('inf'), float('-inf')], 0).fillna(0)

        stocks = []
        for sid in active:
            stocks.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "industry": industry_map.get(sid, ""),
                "latest_price": round(float(latest.get(sid, 0) or 0), 2),
                "change_pct": round(float(changes.get(sid, 0) or 0), 2),
            })

        return {
            "total": len(active),
            "date": close.index[-1].strftime("%Y-%m-%d"),
            "stocks": stocks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/stocks/compare")
async def stocks_compare(
    ids: str = Query(..., description="股票代號，逗號分隔，如 2330,2317"),
    days: int = Query(default=60, ge=10, le=500, description="最近 N 個交易日"),
):
    """
    多股比較 - 回傳多支股票的標準化價格序列（以第一天為基準 = 100）。

    範例: /stocks/compare?ids=2330,2317&days=60
    """
    try:
        stock_ids = [s.strip() for s in ids.split(",") if s.strip()]
        if not stock_ids:
            raise HTTPException(status_code=400, detail="請提供至少一個股票代號")
        if len(stock_ids) > 10:
            raise HTTPException(status_code=400, detail="最多比較 10 支股票")

        close = loader.get("close")
        name_map = _get_stock_name_map()

        result_stocks = []
        for sid in stock_ids:
            if sid not in close.columns:
                continue
            series = close[sid].dropna().tail(days)
            if len(series) == 0:
                continue
            base = float(series.iloc[0])
            normalized = [(float(v) / base * 100) if base > 0 else 100 for v in series]
            result_stocks.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "base_price": round(base, 2),
                "latest_price": round(float(series.iloc[-1]), 2),
                "total_return_pct": round((float(series.iloc[-1]) / base - 1) * 100, 2) if base > 0 else 0,
                "data": [
                    {"date": d.strftime("%Y-%m-%d"), "price": round(float(p), 2), "normalized": round(n, 2)}
                    for (d, p), n in zip(series.items(), normalized)
                ],
            })

        return {
            "days": days,
            "stocks": result_stocks,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# /strategy/* 與 /ai/* 已抽出到 api/routers/{strategy,ai}.py
# _claude_analyzer singleton 亦搬遷至 api/routers/strategy.py

