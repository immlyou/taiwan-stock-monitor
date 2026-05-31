"""Quantitative stock scoring for the Taiwan stock monitor.

The scorer intentionally uses transparent percentile ranks instead of a black-box
model. Each component can be inspected independently and missing inputs simply
reduce the available component set for that stock.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import numpy as np
import pandas as pd


SCORE_COMPONENTS = ["value", "growth", "momentum", "chip", "quality", "risk"]

COMPONENT_LABELS = {
    "value": "價值",
    "growth": "成長",
    "momentum": "動能",
    "chip": "籌碼",
    "quality": "品質",
    "risk": "風險",
}

COMPONENT_WEIGHTS = {
    "value": 0.18,
    "growth": 0.18,
    "momentum": 0.18,
    "chip": 0.16,
    "quality": 0.15,
    "risk": 0.15,
}


@dataclass(frozen=True)
class ScoreResult:
    stock_id: str
    total_score: Optional[float]
    rating: str
    component_scores: Dict[str, Optional[float]]
    key_metrics: Dict[str, Optional[float]]
    available_components: int
    date: Optional[str]


def _stock_id(column: Any) -> str:
    text = str(column)
    return text.split(" ")[0] if " " in text else text


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    result.columns = [_stock_id(c) for c in result.columns]
    # 正規化後可能產生重複欄位（如 "2330 台積電" 與 "2330"），或原始雲端資料本身含重複代號；
    # 去重以避免後續 reindex/選欄報「cannot reindex on an axis with duplicate labels」。
    if result.columns.duplicated().any():
        result = result.loc[:, ~result.columns.duplicated()]
    return result


def _latest_row(df: pd.DataFrame, date: Optional[pd.Timestamp] = None) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    normalized = _normalize_columns(df)
    if date is not None:
        eligible = normalized.loc[normalized.index <= date]
        if eligible.empty:
            return pd.Series(dtype=float)
        return eligible.iloc[-1]
    return normalized.iloc[-1]


def _last_valid(series: pd.Series, stock_id: str) -> Optional[float]:
    if series is None or series.empty or stock_id not in series.index:
        return None
    value = series.get(stock_id)
    try:
        if pd.isna(value) or np.isinf(float(value)):
            return None
        return round(float(value), 4)
    except Exception:
        return None


def _percentile_score(
    series: pd.Series,
    *,
    higher_is_better: bool = True,
    positive_only: bool = False,
) -> pd.Series:
    if series is None or series.empty:
        return pd.Series(dtype=float)
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if positive_only:
        values = values.where(values > 0)
    values = values.dropna()
    if values.empty:
        return pd.Series(dtype=float)

    ranked = values.rank(pct=True) * 100
    if not higher_is_better:
        ranked = 101 - ranked
    return ranked.clip(lower=0, upper=100)


def _mean_components(components: Iterable[pd.Series]) -> pd.Series:
    valid = [c for c in components if c is not None and not c.empty]
    if not valid:
        return pd.Series(dtype=float)
    return pd.concat(valid, axis=1).mean(axis=1).clip(lower=0, upper=100)


def _max_drawdown(window: pd.DataFrame) -> pd.Series:
    if window.empty:
        return pd.Series(dtype=float)
    running_max = window.cummax()
    drawdown = window / running_max - 1
    return drawdown.min()


def _rating(score: Optional[float]) -> str:
    if score is None:
        return "N/A"
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _safe_loader_get(loader: Any, key: str) -> Optional[pd.DataFrame]:
    try:
        return loader.get(key)
    except Exception:
        return None


def _load_inputs(loader: Any) -> Dict[str, pd.DataFrame]:
    keys = [
        "close", "volume", "market_value", "is_flagged",
        "pe_ratio", "pb_ratio", "dividend_yield",
        "revenue_yoy", "revenue_mom",
        "foreign_investors", "investment_trust", "dealer", "foreign_holding",
        "inventory_over_1000_ratio", "inventory_under_10_ratio",
    ]
    return {key: df for key in keys if (df := _safe_loader_get(loader, key)) is not None}


def calculate_score_table(
    loader: Any,
    stock_ids: Optional[Iterable[str]] = None,
    date: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Calculate score table for all stocks or a provided stock subset."""
    data = _load_inputs(loader)
    close = _normalize_columns(data.get("close", pd.DataFrame()))
    if close.empty:
        return pd.DataFrame()

    latest_date = date or close.index.max()
    stocks = list(stock_ids) if stock_ids is not None else list(close.columns)
    stocks = [_stock_id(s) for s in stocks if _stock_id(s) in close.columns]
    if not stocks:
        return pd.DataFrame()

    latest_close = _latest_row(close, latest_date).reindex(stocks)
    pe = _latest_row(data.get("pe_ratio", pd.DataFrame()), latest_date).reindex(stocks)
    pb = _latest_row(data.get("pb_ratio", pd.DataFrame()), latest_date).reindex(stocks)
    dy = _latest_row(data.get("dividend_yield", pd.DataFrame()), latest_date).reindex(stocks)
    revenue_yoy = _latest_row(data.get("revenue_yoy", pd.DataFrame()), latest_date).reindex(stocks)
    revenue_mom = _latest_row(data.get("revenue_mom", pd.DataFrame()), latest_date).reindex(stocks)

    value_score = _mean_components([
        _percentile_score(pe, higher_is_better=False, positive_only=True),
        _percentile_score(pb, higher_is_better=False, positive_only=True),
        _percentile_score(dy, higher_is_better=True),
    ])

    growth_score = _mean_components([
        _percentile_score(revenue_yoy, higher_is_better=True),
        _percentile_score(revenue_mom, higher_is_better=True),
    ])

    returns_20 = close[stocks].pct_change(20).loc[:latest_date].iloc[-1] if len(close.loc[:latest_date]) > 20 else pd.Series(dtype=float)
    returns_60 = close[stocks].pct_change(60).loc[:latest_date].iloc[-1] if len(close.loc[:latest_date]) > 60 else pd.Series(dtype=float)
    returns_120 = close[stocks].pct_change(120).loc[:latest_date].iloc[-1] if len(close.loc[:latest_date]) > 120 else pd.Series(dtype=float)

    volume = _normalize_columns(data.get("volume", pd.DataFrame()))
    volume_score = pd.Series(dtype=float)
    if not volume.empty:
        recent_volume = volume.reindex(columns=stocks).loc[:latest_date].tail(20)
        if len(recent_volume) >= 2:
            volume_ratio = recent_volume.iloc[-1] / recent_volume.mean()
            volume_score = _percentile_score(volume_ratio, higher_is_better=True, positive_only=True)

    momentum_score = _mean_components([
        _percentile_score(returns_20, higher_is_better=True),
        _percentile_score(returns_60, higher_is_better=True),
        _percentile_score(returns_120, higher_is_better=True),
        volume_score,
    ])

    chip_components = []
    for key in ["foreign_investors", "investment_trust", "dealer"]:
        df = _normalize_columns(data.get(key, pd.DataFrame()))
        if not df.empty:
            flow = df.reindex(columns=stocks).loc[:latest_date].tail(5).sum()
            chip_components.append(_percentile_score(flow, higher_is_better=True))
    foreign_holding = _latest_row(data.get("foreign_holding", pd.DataFrame()), latest_date).reindex(stocks)
    chip_components.append(_percentile_score(foreign_holding, higher_is_better=True))
    chip_score = _mean_components(chip_components)

    market_value = _latest_row(data.get("market_value", pd.DataFrame()), latest_date).reindex(stocks)
    big_holder_ratio = _latest_row(data.get("inventory_over_1000_ratio", pd.DataFrame()), latest_date).reindex(stocks)
    small_holder_ratio = _latest_row(data.get("inventory_under_10_ratio", pd.DataFrame()), latest_date).reindex(stocks)
    flagged = _latest_row(data.get("is_flagged", pd.DataFrame()), latest_date).reindex(stocks)
    flagged_score = pd.Series(dtype=float)
    if not flagged.empty:
        numeric_flagged = pd.to_numeric(flagged, errors="coerce").fillna(0)
        flagged_score = numeric_flagged.map(lambda v: 0.0 if v else 100.0)
    quality_score = _mean_components([
        _percentile_score(market_value, higher_is_better=True, positive_only=True),
        _percentile_score(big_holder_ratio, higher_is_better=True),
        _percentile_score(small_holder_ratio, higher_is_better=False),
        flagged_score,
    ])

    price_window = close[stocks].loc[:latest_date].tail(60)
    returns = price_window.pct_change().dropna()
    volatility = returns.std() if not returns.empty else pd.Series(dtype=float)
    drawdown = _max_drawdown(price_window)

    liquidity_score = pd.Series(dtype=float)
    if not volume.empty:
        turnover = volume.reindex(columns=stocks).loc[:latest_date].tail(20).mean() * latest_close
        liquidity_score = _percentile_score(turnover, higher_is_better=True, positive_only=True)

    risk_score = _mean_components([
        _percentile_score(volatility, higher_is_better=False),
        _percentile_score(drawdown.abs(), higher_is_better=False),
        liquidity_score,
    ])

    components = {
        "value": value_score,
        "growth": growth_score,
        "momentum": momentum_score,
        "chip": chip_score,
        "quality": quality_score,
        "risk": risk_score,
    }

    component_df = pd.DataFrame({key: score.reindex(stocks) for key, score in components.items()})
    weighted = component_df.mul(pd.Series(COMPONENT_WEIGHTS), axis=1)
    available_weights = component_df.notna().mul(pd.Series(COMPONENT_WEIGHTS), axis=1).sum(axis=1)
    total_score = weighted.sum(axis=1) / available_weights.replace(0, np.nan)

    table = component_df.copy()
    table["stock_id"] = table.index
    table["total_score"] = total_score.clip(lower=0, upper=100)
    table["rating"] = table["total_score"].map(lambda x: _rating(None if pd.isna(x) else float(x)))
    table["available_components"] = component_df.notna().sum(axis=1)
    table["date"] = latest_date.strftime("%Y-%m-%d") if isinstance(latest_date, pd.Timestamp) else str(latest_date)
    table["latest_price"] = latest_close
    table["pe_ratio"] = pe
    table["pb_ratio"] = pb
    table["dividend_yield"] = dy
    table["revenue_yoy"] = revenue_yoy
    table["revenue_mom"] = revenue_mom

    return table.sort_values("total_score", ascending=False, na_position="last")


def score_record_from_row(row: pd.Series) -> Dict[str, Any]:
    stock_id = str(row["stock_id"])
    total = None if pd.isna(row.get("total_score")) else round(float(row["total_score"]), 2)
    component_scores = {
        key: None if pd.isna(row.get(key)) else round(float(row[key]), 2)
        for key in SCORE_COMPONENTS
    }
    key_metrics = {
        key: None if pd.isna(row.get(key)) else round(float(row[key]), 4)
        for key in ["latest_price", "pe_ratio", "pb_ratio", "dividend_yield", "revenue_yoy", "revenue_mom"]
    }
    return {
        "stock_id": stock_id,
        "total_score": total,
        "rating": row.get("rating") or _rating(total),
        "component_scores": component_scores,
        "scores": component_scores,
        "component_labels": COMPONENT_LABELS,
        "weights": COMPONENT_WEIGHTS,
        "key_metrics": key_metrics,
        "available_components": int(row.get("available_components") or 0),
        "date": row.get("date"),
    }


def calculate_stock_score(loader: Any, stock_id: str) -> Dict[str, Any]:
    normalized_id = _stock_id(stock_id)
    table = calculate_score_table(loader)
    if table.empty or normalized_id not in set(table["stock_id"].astype(str)):
        raise KeyError(f"找不到股票: {stock_id}")
    row = table[table["stock_id"].astype(str) == normalized_id].iloc[0]
    return score_record_from_row(row)


def calculate_top_scores(loader: Any, top_n: int = 50) -> Dict[str, Any]:
    table = calculate_score_table(loader)
    records = [score_record_from_row(row) for _, row in table.head(top_n).iterrows()]
    date = records[0]["date"] if records else None
    return {
        "date": date,
        "total": int(len(table)),
        "stocks": records,
    }
