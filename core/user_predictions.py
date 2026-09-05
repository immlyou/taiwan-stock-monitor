"""Account prediction records shared by the HTTP API and scheduled verifier.

Keep legacy fields when normalizing: reading or verifying must not discard data.
Dates are calendar deadlines; only completed daily closes within the prediction
window count. Missing/stale market data never becomes a false failed prediction.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from core.json_store import file_lock, save_json_atomic
from core.timeutils import now_taipei


def normalize_prediction(record: dict) -> dict:
    p = dict(record)
    created = p.get("createdAt") or p.get("created_at", "")
    target_date = p.get("targetDate") or p.get("expire_date")
    if not target_date and created:
        target_date = (datetime.fromisoformat(created) + timedelta(
            days=int(p.get("horizon_days", p.get("verify_days", 5)))
        )).date().isoformat()
    current = p.get("currentPrice", p.get("current_price", p.get("created_price", 0)))
    target = p.get("targetPrice", p.get("predicted_price", p.get("target_price")))
    direction = p.get("direction") or p.get("predicted_direction") or (
        "down" if target is not None and target < current else "up"
    )
    status = p.get("status") or "pending"
    status = {"success": "correct", "failed": "wrong"}.get(status, status)
    return {**p, "code": p.get("code", p.get("stock_id", "")),
            "name": p.get("name", p.get("stock_name", "")),
            "createdAt": created, "targetDate": target_date,
            "currentPrice": current, "targetPrice": target, "direction": direction,
            "status": status, "actualPrice": p.get("actualPrice", p.get("verified_price"))}


def load_predictions(path: Path) -> list[dict]:
    if not path.exists():
        return []
    # Do not silently replace corrupt storage with an empty file.
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    records = data if isinstance(data, list) else data["predictions"]
    return [normalize_prediction(p) for p in records]


def save_predictions(path: Path, records: list[dict]) -> None:
    save_json_atomic(path, {"predictions": records})


def verify_user_predictions(path: Path, close: pd.DataFrame, *, as_of=None) -> int:
    now = as_of or now_taipei()
    if close is None or close.empty:
        return 0
    data = close.copy()
    data.index = pd.to_datetime(data.index)
    # Before market close today's daily bar may still be changing.
    completed_day = now.date() if (now.hour, now.minute) >= (13, 30) else now.date() - timedelta(days=1)
    data = data.loc[data.index.date <= completed_day].sort_index()
    if data.empty:
        return 0
    verified = 0
    with file_lock(path):
        records = load_predictions(path)
        for p in records:
            if p["status"] != "pending":
                continue
            start = datetime.fromisoformat(p["createdAt"]).date()
            deadline = datetime.fromisoformat(p["targetDate"]).date()
            if p["code"] not in data.columns:
                continue
            series = data.loc[(data.index.date > start) & (data.index.date <= deadline), p["code"]].dropna()
            # Wait for the market dataset to reach the deadline (weekends settle
            # on the next loaded trading day using only pre-deadline prices).
            due = data.index[-1].date() >= deadline
            if series.empty:
                if due and completed_day > deadline + timedelta(days=7):
                    p.update(status="expired", verifiedAt=now.isoformat())
                    verified += 1
                continue
            target = p["targetPrice"]
            if target is not None:
                matches = series >= target if p["direction"] == "up" else series <= target
                hit = bool(matches.any())
                actual = float(series[matches].iloc[0]) if hit else float(series.iloc[-1])
            else:
                actual = float(series.iloc[-1])
                hit = (actual > p["currentPrice"] if p["direction"] == "up" else actual < p["currentPrice"]) if due else False
            if hit or due:
                p.update(status="correct" if hit else "wrong", actualPrice=actual, verifiedAt=now.isoformat())
                verified += 1
        if verified:
            save_predictions(path, records)
    return verified
