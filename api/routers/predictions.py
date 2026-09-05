"""預測 (Predictions) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_user_id, verify_api_key
from api.helpers import _get_stock_name_map, _user_json_path
from api.models import ManualPredictionRequest, PredictionRequest
from api.state import loader
from core.indicators import calculate_sma
from core.json_store import file_lock
from core.timeutils import now_taipei
from core.user_predictions import load_predictions, normalize_prediction, save_predictions

logger = logging.getLogger(__name__)

PREDICTIONS_FILE = "predictions.json"

router = APIRouter(tags=["預測"], dependencies=[Depends(verify_api_key)])


@router.get("/predictions")
def predictions_list(
    stock_id: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=500),
    user_id: str = Depends(get_user_id),
):
    """取得已儲存的預測記錄。"""
    try:
        preds = load_predictions(_user_json_path(PREDICTIONS_FILE, user_id=user_id))
        if stock_id:
            preds = [p for p in preds if p["code"] == stock_id]
        preds = sorted(preds, key=lambda x: x["createdAt"], reverse=True)
        return {"total": len(preds), "predictions": preds[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predictions/stats")
def predictions_stats(user_id: str = Depends(get_user_id)):
    """預測準確率統計：總數、正確 / 錯誤 / 進行中筆數與命中率。

    舊狀態先正規化；僅 pending 計為進行中，expired/cancelled 分開計數。
    accuracy = 正確 /（正確 + 錯誤），尚無已驗證結果時為 0。
    """
    try:
        preds = load_predictions(_user_json_path(PREDICTIONS_FILE, user_id=user_id))

        correct = wrong = pending = 0
        for p in preds:
            status = str(p.get("status", "") or "").lower()
            if status == "correct":
                correct += 1
            elif status == "wrong":
                wrong += 1
            elif status == "pending":
                pending += 1

        resolved = correct + wrong
        accuracy = round(correct / resolved * 100, 1) if resolved else 0.0
        return {
            "total": len(preds),
            "correct": correct,
            "wrong": wrong,
            "pending": pending,
            "expired": sum(p["status"] == "expired" for p in preds),
            "cancelled": sum(p["status"] == "cancelled" for p in preds),
            "accuracy": accuracy,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predictions")
def prediction_create(
    req: ManualPredictionRequest | PredictionRequest, user_id: str = Depends(get_user_id)
):
    """建立手動目標價預測，並相容舊版技術面推估請求。

    支援 trend（趨勢延伸）與 mean_reversion（均值回歸）兩種方法。
    注意：此為基礎統計推估，不構成投資建議。
    """
    try:
        if isinstance(req, ManualPredictionRequest):
            now = now_taipei()
            if not now.date() < req.targetDate <= now.date() + timedelta(days=365):
                raise HTTPException(status_code=422, detail="目標日期須為未來一年內的日期")
            close = loader.get("close")
            if close is None or req.code not in close.columns:
                raise HTTPException(status_code=404, detail="找不到股票")
            series = close[req.code].dropna()
            if series.empty:
                raise HTTPException(status_code=503, detail="暫無可用收盤價，請稍後重試")
            current = float(series.iloc[-1])
            if not np.isfinite(current) or current <= 0:
                raise HTTPException(status_code=503, detail="收盤價暫時不可用，請稍後重試")
            if (req.direction == "up" and req.targetPrice <= current) or (
                req.direction == "down" and req.targetPrice >= current
            ):
                raise HTTPException(status_code=422, detail="目標價須與看漲／看跌方向一致")
            prediction = {
                "id": str(uuid.uuid4()), **req.model_dump(mode="json"),
                "name": _get_stock_name_map().get(req.code, ""),
                "currentPrice": current, "priceDate": str(series.index[-1].date()),
                "createdAt": now.isoformat(), "status": "pending", "source": "manual",
            }
            return _append_prediction(prediction, user_id)

        close = loader.get("close")
        if req.stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {req.stock_id}")

        series = close[req.stock_id].dropna().tail(120)
        current_price = float(series.iloc[-1])

        predicted_price = current_price
        confidence = 0.0
        method_detail = {}

        if req.method == "trend":
            x = np.arange(len(series))
            y = series.values
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            predicted_price = float(coeffs[0] * (len(series) + req.horizon_days - 1) + coeffs[1])
            y_fit = np.polyval(coeffs, x)
            ss_res = np.sum((y - y_fit) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            confidence = round(max(0, min(100, r2 * 100)), 1)
            method_detail = {"slope": round(float(slope), 4), "r_squared": round(r2, 4)}
        elif req.method == "mean_reversion":
            sma20 = float(calculate_sma(series, 20).iloc[-1])
            std20 = float(series.tail(20).std())
            z = (current_price - sma20) / std20 if std20 > 0 else 0
            reversion_speed = 0.1  # 每天回歸 10%
            predicted_price = current_price + (sma20 - current_price) * reversion_speed * req.horizon_days
            confidence = round(min(100, abs(z) * 20), 1)
            method_detail = {"z_score": round(float(z), 4), "sma20": round(sma20, 2)}
        else:
            raise HTTPException(status_code=400, detail="method 需為 trend | mean_reversion")

        predicted_change_pct = (predicted_price - current_price) / current_price * 100

        prediction = {
            "id": str(uuid.uuid4()),
            "stock_id": req.stock_id,
            "method": req.method,
            "horizon_days": req.horizon_days,
            "current_price": round(current_price, 2),
            "predicted_price": round(predicted_price, 2),
            "predicted_change_pct": round(predicted_change_pct, 2),
            "confidence": confidence,
            "method_detail": method_detail,
            "created_at": now_taipei().isoformat(),
            "disclaimer": "此為基礎統計推估，不構成任何投資建議。",
        }

        return _append_prediction(prediction, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _append_prediction(prediction: dict, user_id: str) -> dict:
    path = _user_json_path(PREDICTIONS_FILE, user_id=user_id)
    prediction = normalize_prediction(prediction)
    with file_lock(path):
        records = load_predictions(path)
        records.append(prediction)
        # Never evict an unresolved prediction just because new ones are added.
        save_predictions(path, records)
    return prediction


@router.delete("/predictions/{prediction_id}")
def prediction_delete(prediction_id: str, user_id: str = Depends(get_user_id)):
    path = _user_json_path(PREDICTIONS_FILE, user_id=user_id)
    with file_lock(path):
        records = load_predictions(path)
        kept = [p for p in records if p["id"] != prediction_id]
        if len(kept) == len(records):
            raise HTTPException(status_code=404, detail="找不到預測記錄")
        save_predictions(path, kept)
    return {"message": "預測已刪除"}
