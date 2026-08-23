"""已儲存的自訂策略 (Saved Strategies) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_user_id, verify_api_key
from api.helpers import _load_json_file, _save_json_file
from api.models import StrategyCreateRequest

logger = logging.getLogger(__name__)

STRATEGIES_FILE = "saved_strategies.json"

router = APIRouter(tags=["策略"], dependencies=[Depends(verify_api_key)])


@router.get("/strategies/saved")
async def strategies_list(user_id: str = Depends(get_user_id)):
    """取得所有已儲存的自訂策略。"""
    try:
        data = _load_json_file(STRATEGIES_FILE, default={"strategies": []}, user_id=user_id)
        return {"total": len(data["strategies"]), "strategies": data["strategies"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategies/saved")
async def strategy_save(
    req: StrategyCreateRequest, user_id: str = Depends(get_user_id)
):
    """儲存自訂策略設定。"""
    try:
        data = _load_json_file(STRATEGIES_FILE, default={"strategies": []}, user_id=user_id)
        strategy = {
            "id": str(uuid.uuid4()),
            "name": req.name,
            "strategy_type": req.strategy_type,
            "preset": req.preset,
            "description": req.description or "",
            "params": req.params or {},
            "created_at": datetime.now().isoformat(),
        }
        data["strategies"].append(strategy)
        _save_json_file(STRATEGIES_FILE, data, user_id=user_id)
        return {"message": "儲存成功", "strategy": strategy}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/strategies/saved/{strategy_id}")
async def strategy_update(
    strategy_id: str,
    req: StrategyCreateRequest,
    user_id: str = Depends(get_user_id),
):
    """更新已儲存的策略。"""
    try:
        data = _load_json_file(STRATEGIES_FILE, default={"strategies": []}, user_id=user_id)
        idx = next((i for i, s in enumerate(data["strategies"]) if s.get("id") == strategy_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"找不到策略: {strategy_id}")
        data["strategies"][idx].update({
            "name": req.name,
            "strategy_type": req.strategy_type,
            "preset": req.preset,
            "description": req.description or "",
            "params": req.params or {},
            "updated_at": datetime.now().isoformat(),
        })
        _save_json_file(STRATEGIES_FILE, data, user_id=user_id)
        return {"message": "更新成功", "strategy": data["strategies"][idx]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/strategies/saved/{strategy_id}")
async def strategy_delete(
    strategy_id: str, user_id: str = Depends(get_user_id)
):
    """刪除已儲存的策略。"""
    try:
        data = _load_json_file(STRATEGIES_FILE, default={"strategies": []}, user_id=user_id)
        original_len = len(data["strategies"])
        data["strategies"] = [s for s in data["strategies"] if s.get("id") != strategy_id]
        if len(data["strategies"]) == original_len:
            raise HTTPException(status_code=404, detail=f"找不到策略: {strategy_id}")
        _save_json_file(STRATEGIES_FILE, data, user_id=user_id)
        return {"message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
