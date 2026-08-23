"""交易日誌 (Journal) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_user_id, verify_api_key
from api.helpers import _load_json_file, _save_json_file
from api.models import JournalEntryRequest

logger = logging.getLogger(__name__)

JOURNAL_FILE = "trading_journal.json"

router = APIRouter(tags=["交易日誌"], dependencies=[Depends(verify_api_key)])


@router.get("/journal")
async def journal_list(
    stock_id: Optional[str] = Query(default=None, description="依股票代號篩選"),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_user_id),
):
    """取得交易日誌列表。"""
    try:
        data = _load_json_file(JOURNAL_FILE, default={"entries": []}, user_id=user_id)
        entries = data.get("entries", [])
        if stock_id:
            entries = [e for e in entries if e.get("stock_id") == stock_id]
        entries = sorted(entries, key=lambda x: x.get("date", ""), reverse=True)
        return {"total": len(entries), "entries": entries[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/journal")
async def journal_create(
    req: JournalEntryRequest, user_id: str = Depends(get_user_id)
):
    """新增交易日誌記錄。"""
    try:
        data = _load_json_file(JOURNAL_FILE, default={"entries": []}, user_id=user_id)
        entry = {
            "id": str(uuid.uuid4()),
            "stock_id": req.stock_id,
            "action": req.action,
            "shares": req.shares,
            "price": req.price,
            "note": req.note or "",
            "date": req.date or datetime.now().strftime("%Y-%m-%d"),
            "created_at": datetime.now().isoformat(),
        }
        data["entries"].append(entry)
        _save_json_file(JOURNAL_FILE, data, user_id=user_id)
        return {"message": "新增成功", "entry": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/journal/{entry_id}")
async def journal_update(
    entry_id: str, req: JournalEntryRequest, user_id: str = Depends(get_user_id)
):
    """更新交易日誌記錄。"""
    try:
        data = _load_json_file(JOURNAL_FILE, default={"entries": []}, user_id=user_id)
        entries = data.get("entries", [])
        idx = next((i for i, e in enumerate(entries) if e.get("id") == entry_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"找不到日誌記錄: {entry_id}")
        entries[idx].update({
            "stock_id": req.stock_id,
            "action": req.action,
            "shares": req.shares,
            "price": req.price,
            "note": req.note or "",
            "date": req.date or entries[idx].get("date", ""),
            "updated_at": datetime.now().isoformat(),
        })
        _save_json_file(JOURNAL_FILE, data, user_id=user_id)
        return {"message": "更新成功", "entry": entries[idx]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/journal/{entry_id}")
async def journal_delete(entry_id: str, user_id: str = Depends(get_user_id)):
    """刪除交易日誌記錄。"""
    try:
        data = _load_json_file(JOURNAL_FILE, default={"entries": []}, user_id=user_id)
        entries = data.get("entries", [])
        original_len = len(entries)
        data["entries"] = [e for e in entries if e.get("id") != entry_id]
        if len(data["entries"]) == original_len:
            raise HTTPException(status_code=404, detail=f"找不到日誌記錄: {entry_id}")
        _save_json_file(JOURNAL_FILE, data, user_id=user_id)
        return {"message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
