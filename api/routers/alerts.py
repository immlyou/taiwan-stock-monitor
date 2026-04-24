"""警報 (Alerts) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.deps import verify_api_key
from api.helpers import _safe_json
from api.models import AlertCreateRequest
from api.state import loader
from core.alerts import AlertEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["警報"], dependencies=[Depends(verify_api_key)])


@router.get("/alerts")
async def alerts_list():
    """取得所有警報設定。"""
    try:
        engine = AlertEngine()
        alerts = engine.alerts_data.get("alerts", [])
        return {"total": len(alerts), "alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts")
async def alert_create(req: AlertCreateRequest):
    """新增警報設定。"""
    try:
        engine = AlertEngine()
        alert = {
            "id": str(uuid.uuid4()),
            "stock_id": req.stock_id,
            "type": req.type,
            "value": req.value,
            "note": req.note or "",
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }
        engine.alerts_data.setdefault("alerts", []).append(alert)
        engine._save_alerts()
        return {"message": "新增成功", "alert": alert}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/{alert_id}")
async def alert_delete(alert_id: str):
    """刪除警報設定。"""
    try:
        engine = AlertEngine()
        alerts = engine.alerts_data.get("alerts", [])
        original_len = len(alerts)
        engine.alerts_data["alerts"] = [a for a in alerts if a.get("id") != alert_id]
        if len(engine.alerts_data["alerts"]) == original_len:
            raise HTTPException(status_code=404, detail=f"找不到警報: {alert_id}")
        engine._save_alerts()
        return {"message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/check")
async def check_alerts():
    """檢查所有已設定的警報，回傳觸發的項目。"""
    try:
        engine = AlertEngine()
        close = loader.get("close")
        volume = loader.get("volume")
        high = loader.get("high")
        low = loader.get("low")
        data = {"close": close, "volume": volume, "high": high, "low": low}
        triggered = engine.check_all_alerts(data)
        return {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_count": len(triggered),
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "stock_id": a.stock_id,
                    "type": a.alert_type,
                    "current_value": _safe_json(a.current_value),
                    "target_value": _safe_json(a.target_value),
                    "message": a.message,
                }
                for a in triggered
            ],
        }
    except Exception as e:
        return {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_count": 0,
            "alerts": [],
            "note": str(e),
        }
