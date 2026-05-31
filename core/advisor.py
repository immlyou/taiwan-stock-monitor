"""資深操盤人投資顧問 — 量化持股健檢 + 資金配置/再平衡 + 達標可行性 + Claude 專業敘述。

供 api/routers/advisor.py 呼叫。量化部分以 core.stock_score.calculate_score_table 為基礎，
敘述部分用 Claude（無 ANTHROPIC_API_KEY 時優雅降級）。所有報酬估計皆為粗略推估、非保證。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from core.stock_score import calculate_score_table

logger = logging.getLogger(__name__)

# 風險偏好 → 單一持股上限權重、候選檔數、報酬係數
_RISK = {
    "conservative": {"max_positions": 6, "exp_factor": 0.8},
    "moderate": {"max_positions": 8, "exp_factor": 1.0},
    "aggressive": {"max_positions": 10, "exp_factor": 1.3},
}


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if f != f else f  # NaN guard
    except (TypeError, ValueError):
        return None


def _expected_annual_return(avg_score: float, risk_factor: float) -> float:
    """粗略推估年化報酬(%)：score 50 約 6% 基準，每 +10 分約 +2.5%，再乘風險係數。"""
    base = 0.06 + (avg_score - 50) / 10 * 0.025
    return round(max(-0.10, base) * risk_factor * 100, 1)


def analyze_portfolio(
    loader: Any,
    *,
    holdings: List[Dict[str, Any]],
    name_map: Optional[Dict[str, str]] = None,
    capital_to_invest: float = 0.0,
    withdraw_amount: float = 0.0,
    target_roi: Optional[float] = None,
    risk_tolerance: str = "moderate",
    horizon_months: int = 12,
) -> Dict[str, Any]:
    name_map = name_map or {}
    cfg = _RISK.get(risk_tolerance, _RISK["moderate"])

    table = calculate_score_table(loader)
    if table is None or table.empty:
        raise RuntimeError("無法取得量化評分資料（資料尚未就緒）")
    if "stock_id" in table.columns:
        table = table.set_index("stock_id")

    def get_row(sid: str):
        return table.loc[sid] if sid in table.index else None

    # ── 持股健檢 ──
    enriched: List[Dict[str, Any]] = []
    total_value = 0.0
    for h in holdings:
        sid = str(h.get("stock_id", ""))
        shares = _num(h.get("shares")) or 0.0
        r = get_row(sid)
        price = _num(r.get("latest_price")) if r is not None else None
        if price is None:
            price = _num(h.get("cost_price")) or 0.0
        value = shares * price
        total_value += value
        score = _num(r.get("total_score")) if r is not None else None
        enriched.append({
            "stock_id": sid,
            "name": name_map.get(sid, "") or (r.get("name") if r is not None else "") or "",
            "shares": shares,
            "price": round(price, 2),
            "value": round(value, 2),
            "score": round(score, 1) if score is not None else None,
            "rating": (r.get("rating") if r is not None else "N/A") or "N/A",
        })
    for e in enriched:
        e["weight"] = round(e["value"] / total_value * 100, 1) if total_value > 0 else 0.0

    scores = [e["score"] for e in enriched if e["score"] is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    top_weight = max((e["weight"] for e in enriched), default=0.0)
    concentration = "高" if top_weight >= 40 else "中" if top_weight >= 25 else "低"

    # ── 賣出（拿回資金）：由低分往高分賣 ──
    sells: List[Dict[str, Any]] = []
    freed = 0.0
    if withdraw_amount and withdraw_amount > 0:
        for e in sorted(enriched, key=lambda x: (x["score"] if x["score"] is not None else -1)):
            if freed >= withdraw_amount:
                break
            if e["value"] <= 0 or e["price"] <= 0:
                continue
            sell_value = min(e["value"], withdraw_amount - freed)
            sell_shares = round(sell_value / e["price"])
            if sell_shares <= 0:
                continue
            amt = sell_shares * e["price"]
            sells.append({
                "stock_id": e["stock_id"], "name": e["name"], "shares": int(sell_shares),
                "amount": round(amt), "reason": f"評分較低（{e['rating']}），優先減碼套現",
            })
            freed += amt

    # ── 買入（投入資金）：以量化評分加權配置新標的 ──
    buys: List[Dict[str, Any]] = []
    deploy = _num(capital_to_invest) or 0.0
    if deploy > 0:
        held = {e["stock_id"] for e in enriched}
        ranked = table[table["total_score"].notna()].sort_values("total_score", ascending=False)
        picks = []
        for sid, r in ranked.iterrows():
            if sid in held:
                continue
            picks.append((str(sid), r))
            if len(picks) >= cfg["max_positions"]:
                break
        if picks:
            score_sum = sum(float(r["total_score"]) for _, r in picks) or 1.0
            for sid, r in picks:
                w = float(r["total_score"]) / score_sum
                price = _num(r.get("latest_price")) or 0.0
                if price <= 0:
                    continue
                shares = round(deploy * w / price)
                if shares <= 0:
                    continue
                amt = shares * price
                sc = round(float(r["total_score"]), 1)
                buys.append({
                    "stock_id": sid, "name": name_map.get(sid, "") or "",
                    "shares": int(shares), "amount": round(amt),
                    "score": sc, "rating": r.get("rating"),
                    "reason": f"量化評分 {round(sc)}（{r.get('rating')}），依分數加權配置",
                })

    deployed = sum(b["amount"] for b in buys)
    cash_after = round(freed - deployed)

    # ── 達標可行性 ──
    feasibility = None
    exp_ret = _expected_annual_return(avg_score if avg_score > 0 else 50.0, cfg["exp_factor"])
    if target_roi is not None:
        t = float(target_roi)
        if t <= exp_ret:
            verdict = "可行"
        elif t <= exp_ret * 1.5:
            verdict = "具挑戰"
        else:
            verdict = "偏高"
        feasibility = {
            "target_roi": t,
            "estimated_annual_return": exp_ret,
            "verdict": verdict,
            "note": (
                f"依目前持股量化評分推估年化報酬約 {exp_ret}%（非保證），"
                f"集中度{concentration}、風險偏好「{risk_tolerance}」。"
                f"目標 {t}% 評為「{verdict}」。"
                + ("　達標需提高持股評分或承擔更高波動。" if verdict != "可行" else "")
            ),
        }

    # ── 套用用的新 holdings（賣出減股、買入新增）──
    proposed: List[Dict[str, Any]] = []
    sell_map = {s["stock_id"]: s["shares"] for s in sells}
    for h in holdings:
        sid = str(h.get("stock_id", ""))
        shares = int((_num(h.get("shares")) or 0) - sell_map.get(sid, 0))
        if shares > 0:
            proposed.append({"stock_id": sid, "shares": shares, "cost_price": _num(h.get("cost_price")) or 0.0})
    for b in buys:
        cost = round(b["amount"] / b["shares"], 2) if b["shares"] else 0.0
        proposed.append({"stock_id": b["stock_id"], "shares": b["shares"], "cost_price": cost})

    return {
        "health": {
            "holdings": enriched, "avg_score": avg_score,
            "total_value": round(total_value), "top_weight": top_weight,
            "concentration": concentration,
        },
        "plan": {
            "buys": buys, "sells": sells, "freed_cash": round(freed),
            "deployed": round(deployed), "cash_after": cash_after,
        },
        "feasibility": feasibility,
        "proposed_holdings": proposed,
        "params": {
            "capital_to_invest": deploy, "withdraw_amount": _num(withdraw_amount) or 0.0,
            "target_roi": target_roi, "risk_tolerance": risk_tolerance,
            "horizon_months": horizon_months,
        },
    }


_client = None
_NARRATIVE_MODEL = "claude-sonnet-4-20250514"


def advisor_narrative(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """用 Claude 把量化結果寫成資深操盤人口吻的專業敘述。無金鑰時優雅降級。"""
    global _client
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"narrative": "", "error": "ANTHROPIC_API_KEY 未設定，僅提供量化分析。"}
    try:
        if _client is None:
            import anthropic
            _client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return {"narrative": "", "error": "anthropic 套件未安裝。"}

    h = analysis.get("health", {})
    p = analysis.get("plan", {})
    f = analysis.get("feasibility") or {}
    params = analysis.get("params", {})

    holdings_txt = "\n".join(
        f"- {e['stock_id']} {e['name']} 權重{e['weight']}% 評分{e['score']}({e['rating']})"
        for e in h.get("holdings", [])[:20]
    ) or "（無持股）"
    buys_txt = "\n".join(f"- 買 {b['stock_id']} {b['name']} 約 {b['amount']:,} 元（評分{b['score']}）" for b in p.get("buys", [])) or "（無）"
    sells_txt = "\n".join(f"- 賣 {s['stock_id']} {s['name']} 約 {s['amount']:,} 元" for s in p.get("sells", [])) or "（無）"

    prompt = (
        "你是一位資深台股操盤人/投資顧問。根據以下量化分析，給出專業、務實的操盤建議。\n\n"
        f"【現有持股】平均評分 {h.get('avg_score')}、集中度 {h.get('concentration')}（最大單一權重 {h.get('top_weight')}%）、總市值 {h.get('total_value'):,} 元\n{holdings_txt}\n\n"
        f"【資金】可投入 {params.get('capital_to_invest', 0):,.0f} 元、想拿回 {params.get('withdraw_amount', 0):,.0f} 元；風險偏好 {params.get('risk_tolerance')}、期限 {params.get('horizon_months')} 個月\n"
        f"【建議買進】\n{buys_txt}\n【建議賣出】\n{sells_txt}\n"
        f"【達標評估】{f.get('note', '（未設定目標報酬）')}\n\n"
        "請用繁體中文，以資深操盤人口吻提供：\n"
        "1. **持股健檢點評**（80字內）：集中度、評分結構、主要風險\n"
        "2. **配置/再平衡理由**（100字內）：為何這樣買/賣\n"
        "3. **達標可行性與風險提醒**（80字內）\n"
        "4. **操盤紀律提醒**（2-3條，每條30字內）：停損/加碼/分批等\n"
        "語氣專業直接、務實，務必提醒投資有風險、此為參考非投資建議。"
    )
    try:
        msg = _client.messages.create(
            model=_NARRATIVE_MODEL, max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"narrative": msg.content[0].text, "error": None}
    except Exception as e:  # noqa: BLE001
        logger.error("顧問敘述生成失敗: %s", e)
        return {"narrative": "", "error": str(e)}
