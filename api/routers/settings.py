"""系統設定 (Settings) 端點"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import verify_api_key
from api.helpers import _load_json_file, _save_json_file
from api.models import SettingsUpdateRequest

logger = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"

_DEFAULTS = {
    "theme": "light",
    "language": "zh-TW",
    "notifications_enabled": True,
    "default_days": 60,
}

router = APIRouter(tags=["設定"], dependencies=[Depends(verify_api_key)])


@router.get("/settings")
async def settings_get():
    """取得系統設定。"""
    try:
        return _load_json_file(SETTINGS_FILE, default=dict(_DEFAULTS))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def settings_update(req: SettingsUpdateRequest):
    """更新系統設定。"""
    try:
        data = _load_json_file(SETTINGS_FILE, default=dict(_DEFAULTS))
        if req.theme is not None:
            data["theme"] = req.theme
        if req.language is not None:
            data["language"] = req.language
        if req.notifications_enabled is not None:
            data["notifications_enabled"] = req.notifications_enabled
        if req.default_days is not None:
            data["default_days"] = req.default_days
        if req.extra:
            data.update(req.extra)
        _save_json_file(SETTINGS_FILE, data)
        return {"message": "更新成功", "settings": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
