"""Trading radar signals built from chip, revenue, price, and risk data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from core.data_loader import get_active_stocks
from core.stock_score import calculate_score_table


def _safe_float(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None or pd.isna(value) or np.isinf(float(value)):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _latest(df: Optional[pd.DataFrame], stock_id: str) -> Optional[float]:
    if df is None or df.empty or stock_id not in df.columns:
        return None
    series = df[stock_id].dropna()
    if series.empty:
        return None
    return _safe_float(series.iloc[-1])


def _sum_tail(df: Optional[pd.DataFrame], stock_id: str, days: int) -> float:
    if df is None or df.empty or stock_id not in df.columns:
        return 0.0
    series = pd.to_numeric(df[stock_id], errors="coerce").dropna().tail(days)
    return float(series.sum()) if not series.empty else 0.0


def _pct_change(series: pd.Series, days: int) -> Optional[float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) <= days:
        return None
    base = float(clean.iloc[-days - 1])
    if base <= 0:
        return None
    return round((float(clean.iloc[-1]) / base - 1) * 100, 2)


def _score_clip(value: float) -> float:
    return round(float(max(0, min(100, value))), 2)


@dataclass
class RadarContext:
    close: pd.DataFrame
    volume: pd.DataFrame
    open_: Optional[pd.DataFrame]
    high: Optional[pd.DataFrame]
    low: Optional[pd.DataFrame]
    revenue_yoy: Optional[pd.DataFrame]
    revenue_mom: Optional[pd.DataFrame]
    foreign: Optional[pd.DataFrame]
    trust: Optional[pd.DataFrame]
    dealer: Optional[pd.DataFrame]
    margin_buy: Optional[pd.DataFrame]
    score_map: Dict[str, float]
    name_map: Dict[str, str]
    industry_map: Dict[str, str]


class TradingRadar:
    """Generate explainable, probability-style trading radar signals."""

    def __init__(self, loader: Any):
        self.loader = loader

    def _safe_get(self, key: str) -> Optional[pd.DataFrame]:
        try:
            return self.loader.get(key)
        except Exception:
            return None

    def _name_map(self) -> Dict[str, str]:
        try:
            info = self.loader.get("categories")
            if "stock_id" in info.columns and "name" in info.columns:
                return dict(zip(info["stock_id"].astype(str), info["name"].astype(str)))
            if "name" in info.columns:
                return dict(zip(info.index.astype(str), info["name"].astype(str)))
        except Exception:
            pass
        return {}

    def _industry_map(self) -> Dict[str, str]:
        try:
            info = self.loader.get("categories")
            for column in ("category", "industry", "產業", "類別"):
                if column in info.columns:
                    ids = info["stock_id"] if "stock_id" in info.columns else info.index
                    return dict(zip(ids.astype(str), info[column].astype(str)))
        except Exception:
            pass
        return {}

    def _context(self) -> RadarContext:
        close = self.loader.get("close")
        volume = self.loader.get("volume")
        score_table = calculate_score_table(self.loader)
        score_map = {}
        if not score_table.empty:
            score_map = {
                str(row["stock_id"]): float(row["total_score"])
                for _, row in score_table.dropna(subset=["total_score"]).iterrows()
            }
        return RadarContext(
            close=close,
            volume=volume,
            open_=self._safe_get("open"),
            high=self._safe_get("high"),
            low=self._safe_get("low"),
            revenue_yoy=self._safe_get("revenue_yoy"),
            revenue_mom=self._safe_get("revenue_mom"),
            foreign=self._safe_get("foreign_investors"),
            trust=self._safe_get("investment_trust"),
            dealer=self._safe_get("dealer"),
            margin_buy=self._safe_get("margin_buy"),
            score_map=score_map,
            name_map=self._name_map(),
            industry_map=self._industry_map(),
        )

    def analyze_stock(self, stock_id: str) -> Dict[str, Any]:
        ctx = self._context()
        normalized_id = str(stock_id).strip()
        if normalized_id not in ctx.close.columns:
            raise KeyError(f"找不到股票: {stock_id}")
        return self._analyze_one(ctx, normalized_id)

    def scan(self, stock_ids: Optional[Iterable[str]] = None, top_n: int = 50) -> Dict[str, Any]:
        ctx = self._context()
        if stock_ids is None:
            try:
                stocks = [sid for sid in get_active_stocks() if sid in ctx.close.columns]
            except Exception:
                stocks = list(ctx.close.columns)
        else:
            stocks = [str(s).strip() for s in stock_ids if str(s).strip() in ctx.close.columns]
        stocks = [sid for sid in stocks if not sid.startswith("00")]

        records = []
        for sid in stocks:
            try:
                record = self._analyze_one(ctx, sid)
            except Exception:
                continue
            if record["radar_score"] >= 45 or record["risk_flags"]:
                records.append(record)

        records.sort(key=lambda item: (item["action_rank"], -item["radar_score"]))
        top_records = records[:top_n]

        return {
            "date": ctx.close.index[-1].strftime("%Y-%m-%d"),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_scanned": len(stocks),
            "stocks": top_records,
            "categories": {
                "accumulation": [r for r in records if r["signals"]["accumulation"]["score"] >= 65][:10],
                "revenue_breakout": [r for r in records if r["signals"]["revenue_momentum"]["score"] >= 65 and (r["price_change_20d"] or 0) <= 8][:10],
                "distribution_risk": [r for r in records if r["signals"]["distribution_risk"]["score"] >= 60][:10],
                "entry_watch": [r for r in records if r["signals"]["entry_zone"]["score"] >= 65][:10],
                "daily_watch": [r for r in records if r["action"] in ("買進觀察", "等回檔")][:10],
            },
        }

    def _analyze_one(self, ctx: RadarContext, stock_id: str) -> Dict[str, Any]:
        prices = pd.to_numeric(ctx.close[stock_id], errors="coerce").dropna()
        if len(prices) < 30:
            raise ValueError("price history too short")

        latest_price = float(prices.iloc[-1])
        ma20 = float(prices.tail(20).mean())
        ma60 = float(prices.tail(min(60, len(prices))).mean())
        high20 = float(prices.tail(20).max())
        low20 = float(prices.tail(20).min())
        support_price = round(max(low20, ma20 * 0.97), 2)
        resistance_price = round(high20, 2)
        price_change_5d = _pct_change(prices, 5)
        price_change_20d = _pct_change(prices, 20)

        volume_ratio = 1.0
        if stock_id in ctx.volume.columns:
            vols = pd.to_numeric(ctx.volume[stock_id], errors="coerce").dropna().tail(20)
            if len(vols) >= 5 and float(vols.mean()) > 0:
                volume_ratio = float(vols.iloc[-1] / vols.mean())

        foreign_5 = _sum_tail(ctx.foreign, stock_id, 5)
        trust_5 = _sum_tail(ctx.trust, stock_id, 5)
        dealer_5 = _sum_tail(ctx.dealer, stock_id, 5)
        institutional_5 = foreign_5 + trust_5 + dealer_5
        institutional_20 = _sum_tail(ctx.foreign, stock_id, 20) + _sum_tail(ctx.trust, stock_id, 20) + _sum_tail(ctx.dealer, stock_id, 20)

        yoy = _latest(ctx.revenue_yoy, stock_id)
        mom = _latest(ctx.revenue_mom, stock_id)
        quant_score = _safe_float(ctx.score_map.get(stock_id)) or 50.0

        accumulation = self._accumulation_signal(institutional_5, institutional_20, price_change_20d, volume_ratio)
        revenue = self._revenue_signal(yoy, mom, price_change_20d)
        distribution = self._distribution_signal(prices, ctx.open_, stock_id, institutional_5, volume_ratio)
        entry_zone = self._entry_signal(latest_price, ma20, ma60, high20, low20, quant_score, distribution["score"])

        radar_score = _score_clip(
            accumulation["score"] * 0.27
            + revenue["score"] * 0.26
            + entry_zone["score"] * 0.22
            + quant_score * 0.15
            + (100 - distribution["score"]) * 0.10
        )
        probability_score = _score_clip(radar_score - max(0, distribution["score"] - 55) * 0.35)
        action, action_rank = self._action(radar_score, accumulation["score"], revenue["score"], entry_zone["score"], distribution["score"], price_change_20d)

        reasons = accumulation["reasons"] + revenue["reasons"] + entry_zone["reasons"]
        risk_flags = distribution["reasons"]
        if not reasons:
            reasons = ["目前沒有明顯強訊號，維持觀察。"]

        return {
            "stock_id": stock_id,
            "name": ctx.name_map.get(stock_id, ""),
            "industry": ctx.industry_map.get(stock_id, ""),
            "latest_price": round(latest_price, 2),
            "radar_score": radar_score,
            "probability_score": probability_score,
            "action": action,
            "action_rank": action_rank,
            "watch_price": round(ma20, 2),
            "support_price": support_price,
            "resistance_price": resistance_price,
            "invalidation_conditions": self._invalidation_conditions(latest_price, ma20, ma60, distribution["score"]),
            "reasons": reasons[:6],
            "risk_flags": risk_flags[:4],
            "signal_tags": self._signal_tags(accumulation, revenue, distribution, entry_zone),
            "price_change_5d": price_change_5d,
            "price_change_20d": price_change_20d,
            "volume_ratio": round(volume_ratio, 2),
            "metrics": {
                "quant_score": quant_score,
                "revenue_yoy": yoy,
                "revenue_mom": mom,
                "institutional_5d": round(institutional_5, 2),
                "institutional_20d": round(institutional_20, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2),
            },
            "signals": {
                "accumulation": accumulation,
                "revenue_momentum": revenue,
                "distribution_risk": distribution,
                "entry_zone": entry_zone,
            },
        }

    def _accumulation_signal(self, institutional_5: float, institutional_20: float, price_change_20d: Optional[float], volume_ratio: float) -> Dict[str, Any]:
        price_move = price_change_20d or 0
        score = 45.0
        reasons = []
        if institutional_5 > 0:
            score += 16
            reasons.append("近 5 日法人合計偏買。")
        if institutional_20 > 0:
            score += 14
            reasons.append("近 20 日法人籌碼累積為正。")
        if institutional_20 > 0 and price_move < 8:
            score += 18
            reasons.append("法人買超但 20 日漲幅尚未過熱，具吸籌型態。")
        if 1.15 <= volume_ratio <= 2.2:
            score += 8
            reasons.append("成交量溫和放大。")
        if institutional_5 < 0 and institutional_20 < 0:
            score -= 22
        return {"score": _score_clip(score), "reasons": reasons}

    def _revenue_signal(self, yoy: Optional[float], mom: Optional[float], price_change_20d: Optional[float]) -> Dict[str, Any]:
        score = 45.0
        reasons = []
        if yoy is not None:
            if yoy >= 30:
                score += 24
                reasons.append(f"月營收年增率 {yoy:.1f}%，基本面動能強。")
            elif yoy >= 10:
                score += 12
                reasons.append(f"月營收年增率 {yoy:.1f}%，維持成長。")
            elif yoy < 0:
                score -= 18
        if mom is not None:
            if mom >= 10:
                score += 14
                reasons.append(f"月營收月增率 {mom:.1f}%，短期動能轉強。")
            elif mom < -10:
                score -= 10
        if yoy is not None and yoy >= 30 and (price_change_20d or 0) < 8:
            score += 15
            reasons.append("營收轉強但 20 日股價反應有限。")
        return {"score": _score_clip(score), "reasons": reasons}

    def _distribution_signal(self, prices: pd.Series, open_df: Optional[pd.DataFrame], stock_id: str, institutional_5: float, volume_ratio: float) -> Dict[str, Any]:
        latest = float(prices.iloc[-1])
        high20 = float(prices.tail(20).max())
        score = 25.0
        reasons = []
        near_high = latest >= high20 * 0.97
        if near_high and institutional_5 < 0:
            score += 25
            reasons.append("股價接近 20 日高位但法人近 5 日轉賣。")
        if volume_ratio >= 2.2:
            score += 18
            reasons.append("成交量異常放大，需留意換手或出貨風險。")
        if open_df is not None and stock_id in open_df.columns:
            opens = pd.to_numeric(open_df[stock_id], errors="coerce").dropna()
            if not opens.empty:
                today_open = float(opens.iloc[-1])
                if today_open > 0 and latest < today_open and volume_ratio > 1.5:
                    score += 16
                    reasons.append("放量收低，短線籌碼轉弱。")
        if _pct_change(prices, 20) and (_pct_change(prices, 20) or 0) > 25:
            score += 12
            reasons.append("20 日漲幅偏大，追價風險升高。")
        return {"score": _score_clip(score), "reasons": reasons}

    def _entry_signal(self, latest: float, ma20: float, ma60: float, high20: float, low20: float, quant_score: float, distribution_score: float) -> Dict[str, Any]:
        score = 42.0
        reasons = []
        if ma20 > ma60 and latest >= ma20:
            score += 18
            reasons.append("價格站上 20 日線且中期均線偏多。")
        if latest <= ma20 * 1.05 and latest >= ma20 * 0.97:
            score += 16
            reasons.append("價格接近 20 日均線，屬較可控觀察區。")
        if latest > high20 * 0.995:
            score += 10
            reasons.append("接近 20 日突破位置。")
        if quant_score >= 70:
            score += 12
            reasons.append("量化評分位於 B 級以上。")
        if distribution_score >= 65:
            score -= 28
        if latest < low20 * 1.03:
            score -= 10
        return {"score": _score_clip(score), "reasons": reasons}

    def _action(
        self,
        radar_score: float,
        accumulation_score: float,
        revenue_score: float,
        entry_score: float,
        distribution_score: float,
        price_change_20d: Optional[float],
    ) -> tuple[str, int]:
        if distribution_score >= 70:
            return "減碼觀察", 4
        if distribution_score >= 58 and (price_change_20d or 0) > 15:
            return "高風險勿追", 5
        if radar_score >= 72 and entry_score >= 62 and (accumulation_score >= 62 or revenue_score >= 65):
            return "買進觀察", 1
        if radar_score >= 66 and (price_change_20d or 0) > 12:
            return "等回檔", 2
        if radar_score >= 58:
            return "強勢續抱", 3
        return "觀察", 6

    def _invalidation_conditions(self, latest: float, ma20: float, ma60: float, distribution_score: float) -> List[str]:
        conditions = [f"收盤跌破 20 日線 {ma20:.2f}", f"收盤跌破 60 日線 {ma60:.2f}"]
        if distribution_score >= 55:
            conditions.append("爆量轉弱且法人連續賣超")
        if latest > ma20 * 1.12:
            conditions.append("短線漲幅過大時不追價")
        return conditions

    def _signal_tags(self, accumulation: Dict[str, Any], revenue: Dict[str, Any], distribution: Dict[str, Any], entry: Dict[str, Any]) -> List[str]:
        tags = []
        if accumulation["score"] >= 65:
            tags.append("主力吸籌")
        if revenue["score"] >= 65:
            tags.append("營收爆發")
        if distribution["score"] >= 60:
            tags.append("出貨風險")
        if entry["score"] >= 65:
            tags.append("進場等待區")
        if not tags:
            tags.append("中性觀察")
        return tags
