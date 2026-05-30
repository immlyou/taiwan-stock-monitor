"""Extended AI trading radar features.

These helpers turn the radar signal into a broader workflow: validation,
tracking, portfolio health, peer comparison, reports, notifications, timelines,
price plans, news/revenue interpretation, and chip proxy analysis.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.data_loader import get_active_stocks
from core.trading_radar import TradingRadar, _pct_change, _safe_float, _sum_tail

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _safe_get(loader: Any, key: str) -> Optional[pd.DataFrame]:
    try:
        return loader.get(key)
    except Exception:
        return None


def _name_industry_maps(loader: Any) -> tuple[Dict[str, str], Dict[str, str]]:
    names: Dict[str, str] = {}
    industries: Dict[str, str] = {}
    try:
        info = loader.get("categories")
        ids = info["stock_id"].astype(str) if "stock_id" in info.columns else info.index.astype(str)
        if "name" in info.columns:
            names = dict(zip(ids, info["name"].astype(str)))
        for col in ("category", "industry", "產業", "類別"):
            if col in info.columns:
                industries = dict(zip(ids, info[col].astype(str)))
                break
    except Exception:
        pass
    return names, industries


def _latest(df: Optional[pd.DataFrame], stock_id: str, date: Optional[pd.Timestamp] = None) -> Optional[float]:
    if df is None or df.empty or stock_id not in df.columns:
        return None
    series = pd.to_numeric(df[stock_id], errors="coerce").dropna()
    if date is not None:
        series = series.loc[series.index <= date]
    if series.empty:
        return None
    return _safe_float(series.iloc[-1])


def _rank_pct(series: pd.Series, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return round(float((clean <= value).sum() / len(clean) * 100), 2)


class RadarPro:
    def __init__(self, loader: Any):
        self.loader = loader
        self.radar = TradingRadar(loader)

    def _historical_score(self, stock_id: str, date: pd.Timestamp) -> Optional[float]:
        close = self.loader.get("close")
        volume = self.loader.get("volume")
        if stock_id not in close.columns:
            return None
        prices = pd.to_numeric(close[stock_id], errors="coerce").dropna().loc[:date]
        if len(prices) < 65:
            return None

        volume_ratio = 1.0
        if stock_id in volume.columns:
            vols = pd.to_numeric(volume[stock_id], errors="coerce").dropna().loc[:date].tail(20)
            if len(vols) >= 5 and float(vols.mean()) > 0:
                volume_ratio = float(vols.iloc[-1] / vols.mean())

        foreign = _safe_get(self.loader, "foreign_investors")
        trust = _safe_get(self.loader, "investment_trust")
        dealer = _safe_get(self.loader, "dealer")
        revenue_yoy = _safe_get(self.loader, "revenue_yoy")
        revenue_mom = _safe_get(self.loader, "revenue_mom")

        institutional_5 = 0.0
        institutional_20 = 0.0
        for df in (foreign, trust, dealer):
            if df is not None and stock_id in df.columns:
                series = pd.to_numeric(df[stock_id], errors="coerce").dropna().loc[:date]
                institutional_5 += float(series.tail(5).sum()) if not series.empty else 0.0
                institutional_20 += float(series.tail(20).sum()) if not series.empty else 0.0

        price_20d = _pct_change(prices, 20) or 0
        ma20 = float(prices.tail(20).mean())
        ma60 = float(prices.tail(60).mean())
        yoy = _latest(revenue_yoy, stock_id, date)
        mom = _latest(revenue_mom, stock_id, date)

        score = 45.0
        if institutional_5 > 0:
            score += 12
        if institutional_20 > 0 and price_20d < 8:
            score += 16
        if yoy is not None and yoy >= 30:
            score += 18
        if mom is not None and mom >= 10:
            score += 10
        if ma20 > ma60 and float(prices.iloc[-1]) >= ma20:
            score += 10
        if 1.15 <= volume_ratio <= 2.2:
            score += 6
        if price_20d > 25:
            score -= 12
        return round(max(0, min(100, score)), 2)

    def backtest(self, days: int = 180, top_n: int = 20) -> Dict[str, Any]:
        close = self.loader.get("close")
        dates = list(pd.to_datetime(close.index).dropna().unique())
        if len(dates) < 80:
            return {"windows": [], "summary": [], "note": "歷史資料不足"}
        start = max(65, len(dates) - days)
        sample_dates = [pd.Timestamp(d) for d in dates[start:-21:5]]
        try:
            stocks = [s for s in get_active_stocks() if s in close.columns and not s.startswith("00")]
        except Exception:
            stocks = [s for s in close.columns if not str(s).startswith("00")]
        stocks = stocks[:350]

        windows = []
        horizon_returns: Dict[int, List[float]] = {5: [], 10: [], 20: []}
        for date in sample_dates:
            scored = []
            for sid in stocks:
                score = self._historical_score(sid, date)
                if score is not None and score >= 62:
                    scored.append((sid, score))
            scored.sort(key=lambda item: item[1], reverse=True)
            picks = scored[:top_n]
            if not picks:
                continue
            date_idx = close.index.get_indexer([date], method="nearest")[0]
            returns_by_horizon: Dict[int, List[float]] = {}
            for horizon in (5, 10, 20):
                if date_idx + horizon >= len(close.index):
                    continue
                vals = []
                for sid, _score in picks:
                    entry = close[sid].iloc[date_idx]
                    exit_ = close[sid].iloc[date_idx + horizon]
                    if pd.notna(entry) and pd.notna(exit_) and float(entry) > 0:
                        ret = (float(exit_) / float(entry) - 1) * 100
                        vals.append(round(ret, 2))
                        horizon_returns[horizon].append(ret)
                returns_by_horizon[horizon] = vals
            windows.append({
                "date": date.strftime("%Y-%m-%d"),
                "pick_count": len(picks),
                "avg_signal_score": round(float(np.mean([p[1] for p in picks])), 2),
                "returns": {
                    f"{horizon}d": {
                        "avg_return_pct": round(float(np.mean(vals)), 2) if vals else None,
                        "hit_rate_pct": round(float(np.mean([v > 0 for v in vals]) * 100), 2) if vals else None,
                    }
                    for horizon, vals in returns_by_horizon.items()
                },
            })

        summary = []
        for horizon, vals in horizon_returns.items():
            summary.append({
                "horizon_days": horizon,
                "sample_count": len(vals),
                "avg_return_pct": round(float(np.mean(vals)), 2) if vals else None,
                "median_return_pct": round(float(np.median(vals)), 2) if vals else None,
                "hit_rate_pct": round(float(np.mean([v > 0 for v in vals]) * 100), 2) if vals else None,
                "worst_return_pct": round(float(np.min(vals)), 2) if vals else None,
            })
        return {
            "days": days,
            "top_n": top_n,
            "windows": windows[-20:],
            "summary": summary,
            "note": "以雷達規則的歷史代理訊號估算，供策略校準使用。",
        }

    def tracking(self) -> Dict[str, Any]:
        latest = self.radar.scan(top_n=40)
        backtest = self.backtest(days=180, top_n=20)
        best = next((row for row in backtest.get("summary", []) if row["horizon_days"] == 10), None)
        action_counts: Dict[str, int] = {}
        for item in latest["stocks"]:
            action_counts[item["action"]] = action_counts.get(item["action"], 0) + 1
        return {
            "date": latest["date"],
            "mode": "historical_proxy",
            "latest_signal_count": len(latest["stocks"]),
            "action_counts": action_counts,
            "estimated_10d_hit_rate_pct": best.get("hit_rate_pct") if best else None,
            "estimated_10d_avg_return_pct": best.get("avg_return_pct") if best else None,
            "watchlist": latest["stocks"][:10],
        }

    def portfolio_health(self, portfolio_id: str = "default") -> Dict[str, Any]:
        from app.components.portfolio_utils import load_portfolios

        portfolios = load_portfolios()
        portfolio = portfolios.get(portfolio_id)
        if portfolio is None:
            raise KeyError(f"找不到投資組合: {portfolio_id}")
        holdings = portfolio.get("holdings", [])
        results = []
        for holding in holdings:
            sid = str(holding.get("stock_id", ""))
            if not sid:
                continue
            try:
                radar = self.radar.analyze_stock(sid)
            except Exception:
                continue
            current_price = radar["latest_price"]
            cost_price = float(holding.get("cost_price", 0) or 0)
            pnl_pct = round((current_price / cost_price - 1) * 100, 2) if cost_price else 0
            results.append({
                "stock_id": sid,
                "name": radar.get("name", ""),
                "action": radar["action"],
                "radar_score": radar["radar_score"],
                "risk_flags": radar["risk_flags"],
                "pnl_pct": pnl_pct,
                "suggestion": self._portfolio_suggestion(radar, pnl_pct),
            })
        risk_count = sum(1 for item in results if item["risk_flags"] or item["action"] in ("減碼觀察", "高風險勿追"))
        return {
            "portfolio_id": portfolio_id,
            "holdings_count": len(results),
            "risk_count": risk_count,
            "health_score": round(max(0, 100 - risk_count * 14 - sum(1 for item in results if item["pnl_pct"] < -8) * 8), 2),
            "holdings": sorted(results, key=lambda item: (item["action"] in ("減碼觀察", "高風險勿追"), -item["radar_score"]), reverse=True),
        }

    def peer_comparison(self, stock_id: str, top_n: int = 12) -> Dict[str, Any]:
        names, industries = _name_industry_maps(self.loader)
        target_industry = industries.get(stock_id, "")
        if not target_industry:
            raise KeyError(f"找不到同業分類: {stock_id}")
        peers = [sid for sid, industry in industries.items() if industry == target_industry]
        radar_rows = []
        close = self.loader.get("close")
        yoy_df = _safe_get(self.loader, "revenue_yoy")
        for sid in peers:
            if sid not in close.columns:
                continue
            try:
                radar = self.radar.analyze_stock(sid)
            except Exception:
                continue
            radar_rows.append({
                "stock_id": sid,
                "name": names.get(sid, ""),
                "radar_score": radar["radar_score"],
                "action": radar["action"],
                "price_change_20d": radar.get("price_change_20d"),
                "revenue_yoy": radar["metrics"].get("revenue_yoy"),
                "institutional_20d": radar["metrics"].get("institutional_20d"),
            })
        radar_rows.sort(key=lambda item: item["radar_score"], reverse=True)
        target = next((row for row in radar_rows if row["stock_id"] == stock_id), None)
        yoy_latest = yoy_df.iloc[-1].reindex(peers) if yoy_df is not None and not yoy_df.empty else pd.Series(dtype=float)
        return {
            "stock_id": stock_id,
            "industry": target_industry,
            "peer_count": len(radar_rows),
            "rank": next((idx + 1 for idx, row in enumerate(radar_rows) if row["stock_id"] == stock_id), None),
            "target": target,
            "percentiles": {
                "revenue_yoy": _rank_pct(yoy_latest, target.get("revenue_yoy") if target else None),
                "radar_score": _rank_pct(pd.Series([row["radar_score"] for row in radar_rows]), target.get("radar_score") if target else None),
            },
            "peers": radar_rows[:top_n],
        }

    def daily_report(self) -> Dict[str, Any]:
        scan = self.radar.scan(top_n=50)
        tracking = self.tracking()
        return {
            "date": scan["date"],
            "title": f"{scan['date']} AI 操盤日報",
            "summary": [
                f"今日雷達掃描 {scan['total_scanned']} 檔，輸出 {len(scan['stocks'])} 檔觀察名單。",
                f"歷史代理 10 日命中率約 {tracking.get('estimated_10d_hit_rate_pct') or 'N/A'}%。",
                f"高風險清單 {len(scan['categories'].get('distribution_risk', []))} 檔。",
            ],
            "sections": {
                "tomorrow_watch": scan["categories"].get("daily_watch", [])[:8],
                "revenue_breakout": scan["categories"].get("revenue_breakout", [])[:8],
                "distribution_risk": scan["categories"].get("distribution_risk", [])[:8],
                "accumulation": scan["categories"].get("accumulation", [])[:8],
            },
        }

    def notification_preview(self, portfolio_id: str = "default") -> Dict[str, Any]:
        messages = []
        try:
            health = self.portfolio_health(portfolio_id)
            for item in health["holdings"]:
                if item["risk_flags"]:
                    messages.append({
                        "level": "high",
                        "stock_id": item["stock_id"],
                        "title": f"{item['stock_id']} 持股出貨風險",
                        "message": item["risk_flags"][0],
                    })
        except Exception:
            pass
        scan = self.radar.scan(top_n=30)
        for item in scan["categories"].get("revenue_breakout", [])[:5]:
            messages.append({
                "level": "medium",
                "stock_id": item["stock_id"],
                "title": f"{item['stock_id']} 營收爆發觀察",
                "message": item["reasons"][0] if item["reasons"] else "營收動能轉強。",
            })
        return {"total": len(messages), "messages": messages[:20]}

    def event_timeline(self, stock_id: str, days: int = 90) -> Dict[str, Any]:
        close = self.loader.get("close")
        if stock_id not in close.columns:
            raise KeyError(f"找不到股票: {stock_id}")
        prices = pd.to_numeric(close[stock_id], errors="coerce").dropna().tail(days)
        events = []
        for date, value in prices.pct_change().dropna().items():
            pct = float(value) * 100
            if abs(pct) >= 5:
                events.append({"date": date.strftime("%Y-%m-%d"), "type": "price", "title": f"股價單日{pct:+.1f}%", "impact": "high" if abs(pct) >= 7 else "medium"})
        revenue_yoy = _safe_get(self.loader, "revenue_yoy")
        revenue_mom = _safe_get(self.loader, "revenue_mom")
        for df, label in ((revenue_yoy, "營收 YoY"), (revenue_mom, "營收 MoM")):
            if df is not None and stock_id in df.columns:
                for date, value in pd.to_numeric(df[stock_id], errors="coerce").dropna().tail(6).items():
                    if abs(float(value)) >= 20:
                        events.append({"date": date.strftime("%Y-%m-%d"), "type": "revenue", "title": f"{label} {float(value):+.1f}%", "impact": "medium"})
        for news in self._stock_news(stock_id)[:8]:
            events.append({"date": str(news.get("published", ""))[:10], "type": "news", "title": news.get("title", ""), "impact": news.get("sentiment", "neutral"), "url": news.get("link")})
        events.sort(key=lambda item: item.get("date", ""), reverse=True)
        return {"stock_id": stock_id, "events": events[:30]}

    def price_plan(self, stock_id: str) -> Dict[str, Any]:
        radar = self.radar.analyze_stock(stock_id)
        entry_low = round(min(radar["watch_price"], radar["support_price"] * 1.03), 2)
        entry_high = round(max(radar["watch_price"] * 1.02, entry_low), 2)
        stop_loss = round(radar["support_price"] * 0.97, 2)
        target_1 = round(radar["resistance_price"] * 1.03, 2)
        target_2 = round(radar["resistance_price"] * 1.10, 2)
        risk = max(entry_high - stop_loss, 0.01)
        reward = max(target_1 - entry_high, 0)
        return {
            "stock_id": stock_id,
            "action": radar["action"],
            "entry_zone": {"low": entry_low, "high": entry_high},
            "stop_loss": stop_loss,
            "targets": [{"label": "第一停利", "price": target_1}, {"label": "第二停利", "price": target_2}],
            "risk_reward_ratio": round(reward / risk, 2),
            "invalidation_conditions": radar["invalidation_conditions"],
        }

    def news_revenue(self, stock_id: str) -> Dict[str, Any]:
        radar = self.radar.analyze_stock(stock_id)
        news = self._stock_news(stock_id)
        sentiment_score = sum(float(item.get("sentiment_score", 0) or 0) for item in news[:10])
        yoy = radar["metrics"].get("revenue_yoy")
        mom = radar["metrics"].get("revenue_mom")
        interpretation = "營收與新聞訊號偏中性。"
        if yoy is not None and yoy >= 30 and sentiment_score >= 0:
            interpretation = "營收動能強，新聞面未明顯背離。"
        elif yoy is not None and yoy < 0:
            interpretation = "營收年增轉弱，需確認題材是否有基本面支撐。"
        elif sentiment_score > 2 and (yoy is None or yoy < 10):
            interpretation = "新聞偏熱但營收支撐不足，需留意題材化。"
        return {
            "stock_id": stock_id,
            "revenue_yoy": yoy,
            "revenue_mom": mom,
            "news_count": len(news),
            "sentiment_score": round(sentiment_score, 2),
            "interpretation": interpretation,
            "news": news[:10],
        }

    def broker_chip_proxy(self, stock_id: str) -> Dict[str, Any]:
        foreign = _safe_get(self.loader, "foreign_investors")
        trust = _safe_get(self.loader, "investment_trust")
        dealer = _safe_get(self.loader, "dealer")
        flows = [
            {"name": "外資", "net_5d": round(_sum_tail(foreign, stock_id, 5), 2), "net_20d": round(_sum_tail(foreign, stock_id, 20), 2)},
            {"name": "投信", "net_5d": round(_sum_tail(trust, stock_id, 5), 2), "net_20d": round(_sum_tail(trust, stock_id, 20), 2)},
            {"name": "自營商", "net_5d": round(_sum_tail(dealer, stock_id, 5), 2), "net_20d": round(_sum_tail(dealer, stock_id, 20), 2)},
        ]
        total_5d = sum(item["net_5d"] for item in flows)
        status = "法人籌碼偏多" if total_5d > 0 else "法人籌碼偏空" if total_5d < 0 else "法人籌碼中性"
        return {
            "stock_id": stock_id,
            "data_status": "broker_branch_unavailable_using_institutional_proxy",
            "status": status,
            "flows": flows,
            "note": "目前資料源未含券商分點，先以三大法人作為籌碼代理訊號。",
        }

    def _portfolio_suggestion(self, radar: Dict[str, Any], pnl_pct: float) -> str:
        if radar["action"] in ("減碼觀察", "高風險勿追"):
            return "優先檢查是否降風險或移出觀察。"
        if pnl_pct < -8 and radar["radar_score"] < 55:
            return "虧損且雷達轉弱，檢查停損條件。"
        if radar["action"] in ("買進觀察", "強勢續抱"):
            return "訊號仍偏正向，可依失效條件續抱。"
        return "維持追蹤。"

    def _stock_news(self, stock_id: str) -> List[Dict[str, Any]]:
        path = DATA_DIR / "news_cache.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        news = data.get("news", []) if isinstance(data, dict) else []
        names, _industries = _name_industry_maps(self.loader)
        name = names.get(stock_id, "")
        result = []
        for item in news:
            text = f"{item.get('title', '')} {item.get('summary', '')}"
            stocks = item.get("stocks", []) or []
            if stock_id in stocks or (name and name in text) or stock_id in text:
                result.append(item)
        return result
