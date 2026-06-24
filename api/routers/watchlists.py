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
        from api.helpers import resolve_default_id
        watchlists = load_watchlists()
        resolved, empty_default = resolve_default_id(watchlists, watchlist_id)
        if empty_default:
            # 完全沒有自選股清單時回空結構（200），讓前端顯示空狀態而非吃 404。
            return {"id": "default", "name": "default", "stocks_count": 0, "stocks": []}
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"找不到自選股清單: {watchlist_id}")
        watchlist_id = resolved

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


@router.get("/watchlists/{watchlist_id}/summary")
async def watchlist_summary(watchlist_id: str, days: int = 20, abnormal_pct: float = 5.0):
    """把整張自選股清單當投資組合看的匯總。

    對清單內每檔股票計算：最新價、當日漲跌%、近 N 日報酬；
    組合層（等權重）：平均漲跌、近 N 日報酬、個股貢獻排名、異常波動標記。

    資料缺失安全降級：取不到價的個股標 unavailable，不影響整體匯總；
    空清單也不崩潰。

    參數：
    - days: 近 N 日報酬的回看天數（預設 20）
    - abnormal_pct: 異常波動門檻（|當日漲跌%| 超過即標記，預設 5.0）
    """
    try:
        from app.components.watchlist_utils import get_watchlist_stocks, load_watchlists
        from api.helpers import resolve_default_id
        watchlists = load_watchlists()
        resolved, empty_default = resolve_default_id(watchlists, watchlist_id)
        if resolved is None and not empty_default:
            raise HTTPException(status_code=404, detail=f"找不到自選股清單: {watchlist_id}")
        # empty_default 時 watchlist_id 維持 "default"，下方 stocks 取出為空，匯總自然降級為空。
        watchlist_id = resolved or "default"

        days = max(int(days), 1)
        stocks = get_watchlist_stocks(watchlist_id)
        close = loader.get("close")
        name_map = _get_stock_name_map()
        industry_map = _get_industry_map()

        # 爆量門檻參考：當日量 > 近 N 日均量的倍數
        volume_df = None
        try:
            volume_df = loader.get("volume")
        except Exception:
            volume_df = None

        items = []
        for sid in stocks:
            entry = {
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "industry": industry_map.get(sid, ""),
                "price": None,
                "change_pct": None,
                "return_nd": None,
                "abnormal": False,
                "abnormal_reasons": [],
                "available": False,
            }
            try:
                if close is not None and sid in close.columns:
                    s = close[sid].dropna()
                    if len(s) >= 1:
                        latest = float(s.iloc[-1])
                        entry["price"] = round(latest, 2)
                        entry["available"] = True
                        if len(s) >= 2:
                            prev = float(s.iloc[-2])
                            if prev > 0:
                                entry["change_pct"] = round((latest - prev) / prev * 100, 2)
                        # 近 N 日報酬（以 N+1 筆計算，資料不足則用最早一筆）
                        window = s.tail(days + 1)
                        base = float(window.iloc[0])
                        if base > 0 and len(window) >= 2:
                            entry["return_nd"] = round((latest - base) / base * 100, 2)

                        # 異常：當日漲跌幅超過門檻
                        if entry["change_pct"] is not None and abs(entry["change_pct"]) >= abnormal_pct:
                            entry["abnormal"] = True
                            entry["abnormal_reasons"].append("price_move")

                        # 異常：爆量（當日量 > 近 N 日均量 2 倍）
                        try:
                            if volume_df is not None and sid in volume_df.columns:
                                vs = volume_df[sid].dropna().tail(days + 1)
                                if len(vs) >= 2:
                                    today_vol = float(vs.iloc[-1])
                                    avg_vol = float(vs.iloc[:-1].mean())
                                    if avg_vol > 0 and today_vol >= avg_vol * 2:
                                        entry["abnormal"] = True
                                        entry["abnormal_reasons"].append("volume_spike")
                        except Exception:
                            pass
            except Exception:
                pass
            items.append(entry)

        available_items = [it for it in items if it["available"]]
        unavailable_ids = [it["stock_id"] for it in items if not it["available"]]

        # 組合層（等權重）匯總：只計入有資料且有對應指標的個股
        day_changes = [it["change_pct"] for it in available_items if it["change_pct"] is not None]
        nd_returns = [it["return_nd"] for it in available_items if it["return_nd"] is not None]

        avg_change_pct = round(sum(day_changes) / len(day_changes), 2) if day_changes else None
        avg_return_nd = round(sum(nd_returns) / len(nd_returns), 2) if nd_returns else None

        # 貢獻排名：依當日漲跌幅排序（等權重下漲跌幅即貢獻），取不到者排末
        def _sort_key(it):
            return it["change_pct"] if it["change_pct"] is not None else float("-inf")

        contribution_ranking = [
            {
                "stock_id": it["stock_id"],
                "name": it["name"],
                "change_pct": it["change_pct"],
                "return_nd": it["return_nd"],
            }
            for it in sorted(available_items, key=_sort_key, reverse=True)
        ]

        abnormal_stocks = [
            {
                "stock_id": it["stock_id"],
                "name": it["name"],
                "change_pct": it["change_pct"],
                "reasons": it["abnormal_reasons"],
            }
            for it in items if it["abnormal"]
        ]

        return {
            "id": watchlist_id,
            "name": watchlist_id,
            "days": days,
            "abnormal_pct": abnormal_pct,
            "stocks_count": len(stocks),
            "available_count": len(available_items),
            "unavailable_stocks": unavailable_ids,
            "weighting": "equal",
            "portfolio": {
                "avg_change_pct": avg_change_pct,
                "avg_return_nd": avg_return_nd,
                "abnormal_count": len(abnormal_stocks),
            },
            "contribution_ranking": contribution_ranking,
            "abnormal_stocks": abnormal_stocks,
            "stocks": items,
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
