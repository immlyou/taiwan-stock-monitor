"""自選股 (Watchlist) 端點"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.deps import verify_api_key
from api.helpers import _get_industry_map, _get_stock_name_map
from api.models import WatchlistCreateRequest, WatchlistUpdateRequest
from api.state import loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["自選股"], dependencies=[Depends(verify_api_key)])


@router.get("/watchlists")
async def watchlists_list():
    """取得所有自選股清單。"""
    try:
        from app.components.watchlist_utils import get_watchlist_stocks, load_watchlists
        watchlists = load_watchlists()
        result = []
        for name in watchlists.keys():
            stocks = get_watchlist_stocks(name)
            result.append({
                "id": name,
                "name": name,
                "stocks_count": len(stocks),
            })
        return {"total": len(result), "watchlists": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlists")
async def watchlist_create(req: WatchlistCreateRequest):
    """建立新自選股清單。"""
    try:
        from app.components.watchlist_utils import (
            WATCHLIST_FILE, load_watchlists, save_watchlists,
        )
        from core.json_store import file_lock
        with file_lock(WATCHLIST_FILE):
            watchlists = load_watchlists()
            if req.name in watchlists:
                raise HTTPException(status_code=409, detail=f"自選股清單 '{req.name}' 已存在")
            watchlists[req.name] = {
                "stocks": req.stocks or [],
                "created_at": datetime.now().isoformat(),
            }
            save_watchlists(watchlists)
        return {"message": "建立成功", "id": req.name, "name": req.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watchlists/{watchlist_id}")
async def watchlist_get(watchlist_id: str):
    """取得指定自選股清單，含各股當前報價。"""
    try:
        from app.components.watchlist_utils import get_watchlist_stocks, load_watchlists
        watchlists = load_watchlists()
        if watchlist_id not in watchlists:
            raise HTTPException(status_code=404, detail=f"找不到自選股清單: {watchlist_id}")

        stocks = get_watchlist_stocks(watchlist_id)
        close = loader.get("close")
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()

        result_stocks = []
        for sid in stocks:
            price = change_pct = None
            try:
                if sid in close.columns:
                    s = close[sid].dropna()
                    price = round(float(s.iloc[-1]), 2)
                    if len(s) >= 2:
                        change_pct = round((float(s.iloc[-1]) - float(s.iloc[-2])) / float(s.iloc[-2]) * 100, 2)
            except Exception:
                pass
            result_stocks.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "industry": industry_map.get(sid, ""),
                "price": price,
                "change_pct": change_pct,
            })

        return {
            "id": watchlist_id,
            "name": watchlist_id,
            "stocks_count": len(stocks),
            "stocks": result_stocks,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/watchlists/{watchlist_id}")
async def watchlist_update(watchlist_id: str, req: WatchlistUpdateRequest):
    """更新自選股清單（可追加或覆蓋股票清單）。"""
    try:
        from app.components.watchlist_utils import (
            WATCHLIST_FILE, load_watchlists, save_watchlists,
        )
        from core.json_store import file_lock
        with file_lock(WATCHLIST_FILE):
            watchlists = load_watchlists()
            if watchlist_id not in watchlists:
                raise HTTPException(status_code=404, detail=f"找不到自選股清單: {watchlist_id}")

            entry = watchlists[watchlist_id]
            if isinstance(entry, list):
                entry = {"stocks": entry}
                watchlists[watchlist_id] = entry

            if req.stocks is not None:
                entry["stocks"] = req.stocks
            if req.name is not None and req.name != watchlist_id:
                if req.name in watchlists:
                    raise HTTPException(
                        status_code=409, detail=f"自選股清單 '{req.name}' 已存在"
                    )
                watchlists[req.name] = watchlists.pop(watchlist_id)
                watchlist_id = req.name

            save_watchlists(watchlists)
        return {"message": "更新成功", "id": watchlist_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/watchlists/{watchlist_id}")
async def watchlist_delete(watchlist_id: str):
    """刪除自選股清單。"""
    try:
        from app.components.watchlist_utils import (
            WATCHLIST_FILE, load_watchlists, save_watchlists,
        )
        from core.json_store import file_lock
        with file_lock(WATCHLIST_FILE):
            watchlists = load_watchlists()
            if watchlist_id not in watchlists:
                raise HTTPException(status_code=404, detail=f"找不到自選股清單: {watchlist_id}")
            del watchlists[watchlist_id]
            save_watchlists(watchlists)
        return {"message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
