"""Intelligent analysis helpers shared by API routers.

The functions here are deterministic and data-driven. They provide useful
analysis without depending on an external LLM call, so they are safe for tests,
local development, and production fallbacks.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from core.data_loader import get_active_stocks
from core.stock_score import calculate_score_table, calculate_stock_score, score_record_from_row


def _safe_float(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None or pd.isna(value) or np.isinf(float(value)):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _normalize_stock_id(stock_id: Any) -> str:
    text = str(stock_id)
    return text.split(" ")[0] if " " in text else text


def _latest_name_map(loader: Any) -> Dict[str, str]:
    try:
        info = loader.get("categories")
        if "stock_id" in info.columns and "name" in info.columns:
            return dict(zip(info["stock_id"].astype(str), info["name"].astype(str)))
        if "name" in info.columns:
            return dict(zip(info.index.astype(str), info["name"].astype(str)))
    except Exception:
        pass
    return {}


def _industry_map(loader: Any) -> Dict[str, str]:
    try:
        info = loader.get("categories")
        for column in ("category", "industry", "產業", "類別"):
            if column in info.columns:
                ids = info["stock_id"] if "stock_id" in info.columns else info.index
                return dict(zip(ids.astype(str), info[column].astype(str)))
    except Exception:
        pass
    return {}


def calculate_score_history(loader: Any, stock_id: str, days: int = 20) -> Dict[str, Any]:
    """Return recent quant score history for one stock."""
    normalized_id = _normalize_stock_id(stock_id)
    close = loader.get("close")
    if normalized_id not in [_normalize_stock_id(c) for c in close.columns]:
        raise KeyError(f"找不到股票: {stock_id}")

    dates = list(pd.to_datetime(close.index).dropna().unique())[-max(2, min(days, 30)):]
    records: List[Dict[str, Any]] = []
    previous_score: Optional[float] = None
    previous_rating: Optional[str] = None

    for raw_date in dates:
        table = calculate_score_table(loader, date=pd.Timestamp(raw_date))
        if table.empty:
            continue
        row = table[table["stock_id"].astype(str) == normalized_id]
        if row.empty:
            continue
        record = score_record_from_row(row.iloc[0])
        total_score = record["total_score"]
        rating = str(record["rating"])
        records.append({
            "date": record["date"],
            "total_score": total_score,
            "rating": rating,
            "change": None if previous_score is None or total_score is None else round(total_score - previous_score, 2),
            "rating_changed": previous_rating is not None and previous_rating != rating,
        })
        if total_score is not None:
            previous_score = float(total_score)
        previous_rating = rating

    latest = records[-1] if records else None
    first = records[0] if records else None
    return {
        "stock_id": normalized_id,
        "days": days,
        "history": records,
        "latest": latest,
        "score_change": (
            None
            if not latest or not first or latest["total_score"] is None or first["total_score"] is None
            else round(float(latest["total_score"]) - float(first["total_score"]), 2)
        ),
    }


def calculate_score_upgrades(loader: Any, days: int = 20, top_n: int = 20) -> Dict[str, Any]:
    """Compare latest score table with an earlier date and return largest moves."""
    close = loader.get("close")
    dates = list(pd.to_datetime(close.index).dropna().unique())
    if len(dates) < 2:
        return {"days": days, "upgrades": [], "downgrades": []}

    current_date = pd.Timestamp(dates[-1])
    previous_date = pd.Timestamp(dates[-min(max(days, 2), len(dates))])
    current = calculate_score_table(loader, date=current_date)
    previous = calculate_score_table(loader, date=previous_date)
    if current.empty or previous.empty:
        return {"days": days, "upgrades": [], "downgrades": []}

    merged = current[["stock_id", "total_score", "rating"]].merge(
        previous[["stock_id", "total_score", "rating"]],
        on="stock_id",
        suffixes=("_latest", "_previous"),
    )
    merged["score_change"] = merged["total_score_latest"] - merged["total_score_previous"]
    name_map = _latest_name_map(loader)

    def _record(row: pd.Series) -> Dict[str, Any]:
        stock_id = str(row["stock_id"])
        return {
            "stock_id": stock_id,
            "name": name_map.get(stock_id, ""),
            "score": _safe_float(row["total_score_latest"]),
            "previous_score": _safe_float(row["total_score_previous"]),
            "score_change": _safe_float(row["score_change"]),
            "rating": row["rating_latest"],
            "previous_rating": row["rating_previous"],
        }

    return {
        "days": days,
        "start_date": previous_date.strftime("%Y-%m-%d"),
        "end_date": current_date.strftime("%Y-%m-%d"),
        "upgrades": [_record(row) for _, row in merged.nlargest(top_n, "score_change").iterrows()],
        "downgrades": [_record(row) for _, row in merged.nsmallest(top_n, "score_change").iterrows()],
    }


def generate_stock_summary(loader: Any, stock_id: str) -> Dict[str, Any]:
    """Generate a deterministic stock summary from price, score, and factor data."""
    score = calculate_stock_score(loader, stock_id)
    normalized_id = str(score["stock_id"])
    name_map = _latest_name_map(loader)
    industry_map = _industry_map(loader)
    components = score.get("component_scores", {})
    sorted_components = sorted(
        ((k, v) for k, v in components.items() if v is not None),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    strengths = sorted_components[:2]
    weaknesses = sorted_components[-2:]
    labels = score.get("component_labels", {})
    metrics = score.get("key_metrics", {})
    company_profile: Dict[str, Any] = {}
    try:
        from core.company_profile import get_company_profile
        company_profile = get_company_profile(loader, normalized_id)
    except Exception:
        company_profile = {}

    total = score.get("total_score")
    rating = score.get("rating")
    if total is None:
        stance = "資料不足"
    elif total >= 70:
        stance = "偏強觀察"
    elif total >= 55:
        stance = "中性觀察"
    else:
        stance = "保守觀察"

    points = []
    if strengths:
        points.append("優勢構面：" + "、".join(f"{labels.get(k, k)} {float(v):.1f}" for k, v in strengths))
    if weaknesses:
        points.append("待改善構面：" + "、".join(f"{labels.get(k, k)} {float(v):.1f}" for k, v in weaknesses))
    if metrics.get("revenue_yoy") is not None:
        points.append(f"最新營收年增率 {float(metrics['revenue_yoy']):.2f}%")
    if metrics.get("pe_ratio") is not None:
        points.append(f"本益比 {float(metrics['pe_ratio']):.2f}")
    if company_profile.get("business_scope"):
        points.append(f"主要業務：{company_profile['business_scope']}")

    return {
        "stock_id": normalized_id,
        "name": name_map.get(normalized_id, ""),
        "industry": company_profile.get("industry") or industry_map.get(normalized_id, ""),
        "date": score.get("date"),
        "stance": stance,
        "score": total,
        "rating": rating,
        "summary": f"{normalized_id} {name_map.get(normalized_id, '')} 目前量化評級 {rating}，總分 {total if total is not None else 'N/A'}，判讀為{stance}。",
        "key_points": points,
        "company_profile": company_profile or None,
        "strengths": [{"component": k, "label": labels.get(k, k), "score": _safe_float(v)} for k, v in strengths],
        "weaknesses": [{"component": k, "label": labels.get(k, k), "score": _safe_float(v)} for k, v in weaknesses],
    }


def evaluate_smart_alerts(
    loader: Any,
    stock_ids: Optional[Iterable[str]] = None,
    top_n: int = 30,
) -> Dict[str, Any]:
    """Evaluate suggested smart alerts from scores, price action, and volume."""
    close = loader.get("close")
    volume = loader.get("volume")
    stocks = [_normalize_stock_id(s) for s in (stock_ids or get_active_stocks()) if _normalize_stock_id(s) in close.columns]
    if stock_ids is None:
        scores = calculate_score_table(loader).head(max(top_n * 3, top_n))
        stocks = [str(s) for s in scores["stock_id"].head(max(top_n * 3, top_n)).tolist()]

    name_map = _latest_name_map(loader)
    alerts: List[Dict[str, Any]] = []

    score_table = calculate_score_table(loader)
    score_map = score_table.set_index("stock_id")["total_score"].to_dict() if not score_table.empty else {}
    for sid in stocks:
        prices = close[sid].dropna()
        if len(prices) < 21:
            continue
        latest = float(prices.iloc[-1])
        prev = float(prices.iloc[-2])
        change_pct = (latest / prev - 1) * 100 if prev else 0
        high_20 = float(prices.tail(20).max())
        low_20 = float(prices.tail(20).min())
        score = _safe_float(score_map.get(sid))

        reasons = []
        severity = "medium"
        if score is not None and score >= 80:
            reasons.append("量化評分進入 A 級觀察區")
            severity = "high"
        if latest >= high_20 and change_pct > 0:
            reasons.append("收盤價突破近 20 日高點")
            severity = "high"
        if latest <= low_20:
            reasons.append("收盤價跌破近 20 日低點")
        try:
            vols = volume[sid].dropna().tail(20)
            if len(vols) >= 10 and float(vols.iloc[-1]) > float(vols.mean()) * 1.8:
                reasons.append("成交量高於 20 日均量 1.8 倍")
        except Exception:
            pass

        if reasons:
            alerts.append({
                "stock_id": sid,
                "name": name_map.get(sid, ""),
                "severity": severity,
                "latest_price": round(latest, 2),
                "change_pct": round(change_pct, 2),
                "score": score,
                "reasons": reasons,
            })

    alerts.sort(key=lambda item: (item["severity"] != "high", -(item.get("score") or 0)))
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(alerts[:top_n]),
        "alerts": alerts[:top_n],
    }


def diagnose_portfolio(loader: Any, portfolio_id: str, portfolio: Dict[str, Any]) -> Dict[str, Any]:
    """Build portfolio allocation, risk, and action diagnostics."""
    holdings = portfolio.get("holdings", [])
    close = loader.get("close")
    name_map = _latest_name_map(loader)
    industry_map = _industry_map(loader)

    enriched = []
    total_value = 0.0
    for holding in holdings:
        sid = _normalize_stock_id(holding.get("stock_id", ""))
        if not sid:
            continue
        shares = float(holding.get("shares", 0) or 0)
        cost_price = float(holding.get("cost_price", 0) or 0)
        current_price = cost_price
        if sid in close.columns and not close[sid].dropna().empty:
            current_price = float(close[sid].dropna().iloc[-1])
        value = shares * current_price
        total_value += value
        enriched.append({
            "stock_id": sid,
            "name": name_map.get(sid, ""),
            "industry": industry_map.get(sid, "其他"),
            "shares": shares,
            "cost_price": round(cost_price, 2),
            "current_price": round(current_price, 2),
            "market_value": round(value, 2),
            "pnl_pct": round(((current_price / cost_price) - 1) * 100, 2) if cost_price else 0,
        })

    industry_values: Dict[str, float] = defaultdict(float)
    for item in enriched:
        weight = item["market_value"] / total_value if total_value else 0
        item["weight"] = round(weight * 100, 2)
        industry_values[item["industry"]] += item["market_value"]

    allocation = [
        {"industry": industry, "weight": round(value / total_value * 100, 2), "market_value": round(value, 2)}
        for industry, value in sorted(industry_values.items(), key=lambda item: item[1], reverse=True)
    ] if total_value else []

    returns_frame = pd.DataFrame()
    stock_ids = [item["stock_id"] for item in enriched if item["stock_id"] in close.columns]
    if stock_ids:
        returns_frame = close[stock_ids].dropna(how="all").pct_change().tail(252).dropna(how="all")

    daily_vol = 0.0
    max_drawdown = 0.0
    if not returns_frame.empty and total_value:
        weights = pd.Series({item["stock_id"]: item["weight"] / 100 for item in enriched})
        portfolio_returns = returns_frame.fillna(0).mul(weights.reindex(returns_frame.columns).fillna(0), axis=1).sum(axis=1)
        daily_vol = float(portfolio_returns.std() * np.sqrt(252) * 100)
        cumulative = (1 + portfolio_returns).cumprod()
        drawdown = cumulative / cumulative.cummax() - 1
        max_drawdown = float(drawdown.min() * 100)

    top_weight = max((item["weight"] for item in enriched), default=0)
    suggestions = []
    if top_weight > 40:
        suggestions.append("單一持股權重超過 40%，可檢查集中度風險。")
    if allocation and allocation[0]["weight"] > 60:
        suggestions.append("產業配置偏集中，可補入低相關產業分散波動。")
    if daily_vol > 30:
        suggestions.append("年化波動率偏高，可降低高 beta 或短線波動股比重。")
    if not suggestions and enriched:
        suggestions.append("目前配置沒有明顯集中警訊，後續可加入再平衡目標權重。")

    return {
        "portfolio_id": portfolio_id,
        "total_value": round(total_value, 2),
        "holdings_count": len(enriched),
        "concentration": {
            "top_holding_weight": round(top_weight, 2),
            "top_industry_weight": allocation[0]["weight"] if allocation else 0,
        },
        "risk": {
            "annualized_volatility_pct": round(daily_vol, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
        },
        "allocation": allocation,
        "holdings": sorted(enriched, key=lambda item: item["weight"], reverse=True),
        "suggestions": suggestions,
    }


def calculate_industry_rotation(loader: Any, top_n: int = 30) -> Dict[str, Any]:
    """Rank industries by short and medium-term momentum plus breadth."""
    close = loader.get("close")
    industry_map = _industry_map(loader)
    active = [sid for sid in get_active_stocks() if sid in close.columns]
    rows = []
    for industry in sorted(set(industry_map.get(sid, "其他") for sid in active)):
        members = [sid for sid in active if industry_map.get(sid, "其他") == industry]
        if len(members) < 2:
            continue
        prices = close[members].dropna(how="all")
        if len(prices) < 21:
            continue
        latest = prices.iloc[-1]
        ret_5 = (latest / prices.iloc[-6] - 1) * 100 if len(prices) > 5 else pd.Series(dtype=float)
        ret_20 = (latest / prices.iloc[-21] - 1) * 100
        ret_60 = (latest / prices.iloc[-61] - 1) * 100 if len(prices) > 60 else ret_20
        breadth = float((ret_20 > 0).sum() / len(ret_20.dropna()) * 100) if len(ret_20.dropna()) else 0
        momentum = float(np.nanmean([ret_5.mean(), ret_20.mean(), ret_60.mean()]))
        score = momentum * 0.7 + (breadth - 50) * 0.3
        quadrant = "領先" if ret_20.mean() > 0 and breadth >= 55 else "改善" if ret_20.mean() <= 0 and ret_5.mean() > 0 else "轉弱" if ret_20.mean() > 0 else "落後"
        rows.append({
            "industry": industry,
            "stock_count": len(members),
            "return_5d": round(float(ret_5.mean()), 2),
            "return_20d": round(float(ret_20.mean()), 2),
            "return_60d": round(float(ret_60.mean()), 2),
            "breadth_pct": round(breadth, 2),
            "rotation_score": round(score, 2),
            "quadrant": quadrant,
        })

    rows.sort(key=lambda item: item["rotation_score"], reverse=True)
    return {
        "date": close.index[-1].strftime("%Y-%m-%d"),
        "industries": rows[:top_n],
        "total": len(rows),
    }
