"""警報 (Alerts) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_user_id, verify_api_key
from api.helpers import (
    _load_json_file,
    _safe_json,
    _save_json_file,
    _user_json_path,
    cached_response,
)
from api.models import (
    AlertCreateRequest,
    AlertEvaluateRequest,
    AlertRuleCreateRequest,
    AlertRuleUpdateRequest,
    AlertUpdateRequest,
)
from api.state import loader
from core.alerts import AlertEngine
from core.intelligence import evaluate_smart_alerts
from core.json_store import file_lock
from core.timeutils import now_taipei

logger = logging.getLogger(__name__)

router = APIRouter(tags=["警報"], dependencies=[Depends(verify_api_key)])

ALERT_RULES_FILE = "alert_rules.json"
ALERT_HITS_FILE = "alert_hits.json"

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
async def alerts_list(user_id: str = Depends(get_user_id)):
    """取得所有警報設定。"""
    try:
        engine = AlertEngine(user_id)
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


def _load_rules(user_id: str) -> dict:
    return _load_json_file(ALERT_RULES_FILE, {"rules": []}, user_id=user_id)


def _load_hits(user_id: str) -> dict:
    return _load_json_file(ALERT_HITS_FILE, {"hits": []}, user_id=user_id)


def _target_stock_ids(rule: dict, user_id: str) -> list[str]:
    target = rule.get("target", {})
    stock_ids = {str(item) for item in target.get("stockIds", []) if item}
    watchlist_id = target.get("watchlistId")
    if watchlist_id:
        from app.components.watchlist_utils import get_watchlist_stocks

        stock_ids.update(get_watchlist_stocks(watchlist_id, user_id))
    return sorted(stock_ids)


def _is_hit_suppressed(rule: dict, stock_id: str, hits: list[dict], now: datetime) -> bool:
    previous = [
        hit for hit in hits
        if hit.get("ruleId") == rule.get("id") and hit.get("stockId") == stock_id
    ]
    if not previous:
        return False
    if rule.get("frequency") == "once":
        return True

    latest_raw = max(hit.get("triggeredAt", "") for hit in previous)
    try:
        latest = datetime.fromisoformat(latest_raw)
    except ValueError:
        return False
    return now - latest < timedelta(minutes=int(rule.get("cooldownMinutes", 60)))


@router.get("/alerts/rules")
async def alert_rules_list(user_id: str = Depends(get_user_id)):
    rules = _load_rules(user_id).get("rules", [])
    return {"total": len(rules), "rules": rules}


@router.post("/alerts/rules")
async def alert_rule_create(
    req: AlertRuleCreateRequest, user_id: str = Depends(get_user_id)
):
    path = _user_json_path(ALERT_RULES_FILE, user_id=user_id)
    with file_lock(path):
        data = _load_rules(user_id)
        rule = {
            "id": str(uuid.uuid4()),
            **req.model_dump(),
            "createdAt": now_taipei().isoformat(),
        }
        data.setdefault("rules", []).append(rule)
        _save_json_file(ALERT_RULES_FILE, data, user_id=user_id)
    return {"message": "規則已建立", "rule": rule}


@router.patch("/alerts/rules/{rule_id}")
async def alert_rule_update(
    rule_id: str,
    req: AlertRuleUpdateRequest,
    user_id: str = Depends(get_user_id),
):
    path = _user_json_path(ALERT_RULES_FILE, user_id=user_id)
    with file_lock(path):
        data = _load_rules(user_id)
        rule = next(
            (item for item in data.get("rules", []) if item.get("id") == rule_id),
            None,
        )
        if rule is None:
            raise HTTPException(status_code=404, detail=f"找不到警報規則: {rule_id}")
        rule.update(req.model_dump(exclude_none=True))
        rule["updatedAt"] = now_taipei().isoformat()
        _save_json_file(ALERT_RULES_FILE, data, user_id=user_id)
    return {"message": "規則已更新", "rule": rule}


@router.delete("/alerts/rules/{rule_id}")
async def alert_rule_delete(
    rule_id: str, user_id: str = Depends(get_user_id)
):
    path = _user_json_path(ALERT_RULES_FILE, user_id=user_id)
    with file_lock(path):
        data = _load_rules(user_id)
        rules = data.get("rules", [])
        data["rules"] = [item for item in rules if item.get("id") != rule_id]
        if len(data["rules"]) == len(rules):
            raise HTTPException(status_code=404, detail=f"找不到警報規則: {rule_id}")
        _save_json_file(ALERT_RULES_FILE, data, user_id=user_id)
    return {"message": "規則已刪除"}


@router.get("/alerts/hits")
async def alert_hits_list(
    rule_id: str | None = Query(default=None, alias="ruleId"),
    limit: int = Query(default=100, ge=1, le=500),
    user_id: str = Depends(get_user_id),
):
    hits = _load_hits(user_id).get("hits", [])
    if rule_id:
        hits = [hit for hit in hits if hit.get("ruleId") == rule_id]
    hits = sorted(hits, key=lambda item: item.get("triggeredAt", ""), reverse=True)
    return {"total": len(hits), "hits": hits[:limit]}


@router.post("/alerts/evaluate")
async def alert_rules_evaluate(
    req: AlertEvaluateRequest, user_id: str = Depends(get_user_id)
):
    from core.alert_rules import evaluate_rule_for_stock

    rules_data = _load_rules(user_id)
    hits_data = _load_hits(user_id)
    rule_ids = set(req.ruleIds or [])
    rules = [
        rule for rule in rules_data.get("rules", [])
        if rule.get("enabled", True) and (not rule_ids or rule.get("id") in rule_ids)
    ]
    now = now_taipei()
    market_data = {
        "close": loader.get("close"),
        "volume": loader.get("volume"),
        "high": loader.get("high"),
        "low": loader.get("low"),
    }
    new_hits = []
    suppressed_count = 0

    for rule in rules:
        rule["lastEvaluatedAt"] = now.isoformat()
        for stock_id in _target_stock_ids(rule, user_id):
            try:
                triggered, metrics, condition_results = evaluate_rule_for_stock(
                    rule, stock_id, market_data
                )
            except (KeyError, IndexError, ValueError):
                continue
            if not triggered:
                continue
            if _is_hit_suppressed(
                rule, stock_id, hits_data.get("hits", []), now
            ):
                suppressed_count += 1
                continue

            hit = {
                "id": str(uuid.uuid4()),
                "ruleId": rule["id"],
                "ruleName": rule["name"],
                "stockId": stock_id,
                "triggeredAt": now.isoformat(),
                "metrics": metrics,
                "conditions": condition_results,
                "channels": rule.get("channels", []),
            }
            if req.sendNotifications and hit["channels"]:
                from core.notification import NotificationManager

                hit["notificationResults"] = NotificationManager(user_id).send(
                    title=f"警報：{rule['name']}",
                    message=f"{stock_id} 已符合 Alerts 2.0 規則。",
                    channels=hit["channels"],
                )
            new_hits.append(hit)
            hits_data.setdefault("hits", []).append(hit)
            rule["lastTriggeredAt"] = now.isoformat()

    rules_path = _user_json_path(ALERT_RULES_FILE, user_id=user_id)
    hits_path = _user_json_path(ALERT_HITS_FILE, user_id=user_id)
    with file_lock(rules_path):
        _save_json_file(ALERT_RULES_FILE, rules_data, user_id=user_id)
    if new_hits:
        hits_data["hits"] = hits_data["hits"][-1000:]
        with file_lock(hits_path):
            _save_json_file(ALERT_HITS_FILE, hits_data, user_id=user_id)

    return {
        "evaluatedRules": len(rules),
        "triggeredCount": len(new_hits),
        "suppressedCount": suppressed_count,
        "hits": new_hits,
        "evaluatedAt": now.isoformat(),
    }


@router.post("/alerts")
async def alert_create(
    req: AlertCreateRequest, user_id: str = Depends(get_user_id)
):
    """新增警報設定。"""
    try:
        with file_lock(AlertEngine.alerts_file(user_id)):
            engine = AlertEngine(user_id)
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
async def alert_update(
    alert_id: str,
    req: AlertUpdateRequest,
    user_id: str = Depends(get_user_id),
):
    """更新警報啟用狀態、觸發值或備註。"""
    try:
        with file_lock(AlertEngine.alerts_file(user_id)):
            engine = AlertEngine(user_id)
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
async def alert_reset(alert_id: str, user_id: str = Depends(get_user_id)):
    """重設已觸發警報狀態。"""
    try:
        with file_lock(AlertEngine.alerts_file(user_id)):
            engine = AlertEngine(user_id)
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
async def alert_delete(alert_id: str, user_id: str = Depends(get_user_id)):
    """刪除警報設定。"""
    try:
        with file_lock(AlertEngine.alerts_file(user_id)):
            engine = AlertEngine(user_id)
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
async def check_alerts(user_id: str = Depends(get_user_id)):
    """檢查所有已設定的警報，回傳觸發的項目。"""
    try:
        engine = AlertEngine(user_id)
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
