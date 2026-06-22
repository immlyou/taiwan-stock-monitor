"""警報 (Alerts) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _safe_json, cached_response
from api.models import AlertCreateRequest, AlertUpdateRequest
from api.state import loader
from core.alerts import AlertEngine
from core.intelligence import evaluate_smart_alerts
from core.json_store import file_lock

logger = logging.getLogger(__name__)

router = APIRouter(tags=["警報"], dependencies=[Depends(verify_api_key)])

ALERT_TYPES = [
    {"type": "price_above", "label": "價格高於", "unit": "元", "default_value": 600},
    {"type": "price_below", "label": "價格低於", "unit": "元", "default_value": 500},
    {"type": "rsi_above", "label": "RSI 高於", "unit": "", "default_value": 70},
    {"type": "rsi_below", "label": "RSI 低於", "unit": "", "default_value": 30},
    {"type": "volume_spike", "label": "爆量倍數", "unit": "倍", "default_value": 2},
    {"type": "new_high", "label": "創 N 日新高", "unit": "日", "default_value": 20},
    {"type": "new_low", "label": "創 N 日新低", "unit": "日", "default_value": 20},
]


@router.get("/alerts")
async def alerts_list():
    """取得所有警報設定。"""
    try:
        engine = AlertEngine()
        alerts = engine.alerts_data.get("alerts", [])
        return {"total": len(alerts), "alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/types")
async def alert_types():
    """取得後端實際支援的警報類型。"""
    return {"types": ALERT_TYPES}


@router.get("/alerts/smart-preview")
@cached_response(ttl_seconds=1800)
async def alerts_smart_preview(
    stock_id: str | None = Query(default=None, description="指定股票代號，不填則掃描量化評分前段股票"),
    top_n: int = Query(default=30, ge=1, le=100),
):
    """智慧警報建議：評分、突破、跌破、爆量等訊號預覽。

    結果快取 30 分鐘（走 Redis）；底層全市場評分表亦 memoize，
    避免每次重算 ~2300 檔評分（原本 ~23s）。
    """
    try:
        stock_ids = [stock_id] if stock_id else None
        return evaluate_smart_alerts(loader, stock_ids=stock_ids, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts")
async def alert_create(req: AlertCreateRequest):
    """新增警報設定。"""
    try:
        with file_lock(AlertEngine.ALERTS_FILE):
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


@router.patch("/alerts/{alert_id}")
async def alert_update(alert_id: str, req: AlertUpdateRequest):
    """更新警報啟用狀態、觸發值或備註。"""
    try:
        with file_lock(AlertEngine.ALERTS_FILE):
            engine = AlertEngine()
            alerts = engine.alerts_data.get("alerts", [])
            for alert in alerts:
                if alert.get("id") == alert_id:
                    if req.enabled is not None:
                        alert["enabled"] = req.enabled
                    if req.value is not None:
                        alert["value"] = req.value
                        alert["triggered"] = False
                        alert.pop("triggered_at", None)
                    if req.note is not None:
                        alert["note"] = req.note
                    engine._save_alerts()
                    return {"message": "更新成功", "alert": alert}
        raise HTTPException(status_code=404, detail=f"找不到警報: {alert_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/reset")
async def alert_reset(alert_id: str):
    """重設已觸發警報狀態。"""
    try:
        with file_lock(AlertEngine.ALERTS_FILE):
            engine = AlertEngine()
            alerts = engine.alerts_data.get("alerts", [])
            for alert in alerts:
                if alert.get("id") == alert_id:
                    alert["triggered"] = False
                    alert.pop("triggered_at", None)
                    engine._save_alerts()
                    return {"message": "重設成功", "alert": alert}
        raise HTTPException(status_code=404, detail=f"找不到警報: {alert_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/{alert_id}")
async def alert_delete(alert_id: str):
    """刪除警報設定。"""
    try:
        with file_lock(AlertEngine.ALERTS_FILE):
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
