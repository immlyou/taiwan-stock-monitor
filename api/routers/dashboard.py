"""Custom dashboard configuration endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_user_id, verify_api_key
from api.helpers import _load_json_file, _save_json_file

router = APIRouter(tags=["Dashboard"], dependencies=[Depends(verify_api_key)])

CONFIG_FILE = "dashboard_config.json"

DEFAULT_WIDGETS = [
    {"id": "market-summary", "type": "market_summary", "enabled": True, "order": 1, "size": "small", "title": "市場摘要", "config": {}},
    {"id": "portfolio-kpi", "type": "portfolio_kpi", "enabled": True, "order": 2, "size": "small", "title": "持倉 KPI", "config": {"portfolio_id": "default"}},
    {"id": "smart-alerts", "type": "smart_alerts", "enabled": True, "order": 3, "size": "medium", "title": "智慧警報", "config": {}},
    {"id": "industry-rotation", "type": "industry_rotation", "enabled": True, "order": 4, "size": "medium", "title": "產業輪動", "config": {}},
    {"id": "score-upgrades", "type": "score_upgrades", "enabled": True, "order": 5, "size": "medium", "title": "評分升降級", "config": {}},
]


class DashboardWidget(BaseModel):
    id: str
    type: str
    enabled: bool = True
    order: int = 0
    size: str = Field(default="medium", description="small | medium | large")
    title: str = ""
    config: dict = Field(default_factory=dict)


class DashboardConfigRequest(BaseModel):
    widgets: list[DashboardWidget]


def _default_config() -> dict:
    now = datetime.now().isoformat()
    return {"updated_at": now, "widgets": DEFAULT_WIDGETS}


@router.get("/dashboard/config")
async def dashboard_config_get(user_id: str = Depends(get_user_id)):
    """取得自訂 Dashboard widget 設定。"""
    config = _load_json_file(CONFIG_FILE, default=_default_config(), user_id=user_id)
    if not config.get("widgets"):
        config = _default_config()
    return config


@router.put("/dashboard/config")
async def dashboard_config_update(
    req: DashboardConfigRequest, user_id: str = Depends(get_user_id)
):
    """儲存自訂 Dashboard widget 設定。"""
    config = {
        "updated_at": datetime.now().isoformat(),
        "widgets": [widget.dict() for widget in sorted(req.widgets, key=lambda item: item.order)],
    }
    _save_json_file(CONFIG_FILE, config, user_id=user_id)
    return config
