"""Pure metric and condition evaluation for Alerts 2.0 rules."""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from core.indicators import calculate_rsi


_OPERATORS = {
    "gt": lambda actual, expected: actual > expected,
    "gte": lambda actual, expected: actual >= expected,
    "lt": lambda actual, expected: actual < expected,
    "lte": lambda actual, expected: actual <= expected,
    "eq": lambda actual, expected: actual == expected,
}


def stock_metrics(stock_id: str, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    close = data.get("close")
    if close is None or stock_id not in close.columns:
        raise KeyError(f"missing market data for {stock_id}")

    prices = pd.to_numeric(close[stock_id], errors="coerce").dropna()
    if prices.empty:
        raise KeyError(f"missing market data for {stock_id}")

    latest = float(prices.iloc[-1])
    previous = float(prices.iloc[-2]) if len(prices) > 1 else latest
    change_pct = ((latest / previous) - 1) * 100 if previous else 0.0
    rsi_series = calculate_rsi(prices, period=14)
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    volume_ratio = 0.0
    volume = data.get("volume")
    if volume is not None and stock_id in volume.columns:
        volumes = pd.to_numeric(volume[stock_id], errors="coerce").dropna()
        if not volumes.empty:
            baseline = volumes.iloc[-21:-1]
            average = float(baseline.mean()) if not baseline.empty else float(volumes.mean())
            volume_ratio = float(volumes.iloc[-1]) / average if average > 0 else 0.0

    return {
        "price": round(latest, 4),
        "change_pct": round(change_pct, 4),
        "rsi": round(rsi, 4),
        "volume_ratio": round(volume_ratio, 4),
    }


def evaluate_rule_for_stock(
    rule: Dict[str, Any], stock_id: str, data: Dict[str, pd.DataFrame]
) -> tuple[bool, Dict[str, float], list[Dict[str, Any]]]:
    metrics = stock_metrics(stock_id, data)
    condition_results = []
    for condition in rule.get("conditions", []):
        actual = metrics[condition["field"]]
        matched = bool(_OPERATORS[condition["operator"]](actual, condition["value"]))
        condition_results.append({**condition, "actual": actual, "matched": matched})

    matches = [item["matched"] for item in condition_results]
    triggered = any(matches) if rule.get("match") == "any" else all(matches)
    return triggered, metrics, condition_results
