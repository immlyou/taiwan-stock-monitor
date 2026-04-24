"""預測 (Predictions) 端點"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _load_json_file, _save_json_file
from api.models import PredictionRequest
from api.state import loader
from core.indicators import calculate_sma

logger = logging.getLogger(__name__)

PREDICTIONS_FILE = "predictions.json"

router = APIRouter(tags=["預測"], dependencies=[Depends(verify_api_key)])


@router.get("/predictions")
async def predictions_list(
    stock_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """取得已儲存的預測記錄。"""
    try:
        data = _load_json_file(PREDICTIONS_FILE, default={"predictions": []})
        preds = data.get("predictions", [])
        if stock_id:
            preds = [p for p in preds if p.get("stock_id") == stock_id]
        preds = sorted(preds, key=lambda x: x.get("created_at", ""), reverse=True)
        return {"total": len(preds), "predictions": preds[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predictions")
async def prediction_create(req: PredictionRequest):
    """建立個股價格預測（簡單技術面推估）。

    支援 trend（趨勢延伸）與 mean_reversion（均值回歸）兩種方法。
    注意：此為基礎統計推估，不構成投資建議。
    """
    try:
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
            "created_at": datetime.now().isoformat(),
            "disclaimer": "此為基礎統計推估，不構成任何投資建議。",
        }

        data = _load_json_file(PREDICTIONS_FILE, default={"predictions": []})
        data["predictions"].append(prediction)
        data["predictions"] = data["predictions"][-500:]  # 只保留最近 500 筆
        _save_json_file(PREDICTIONS_FILE, data)

        return prediction
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
