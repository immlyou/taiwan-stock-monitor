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

    # 先依 stock_id 合併重複持股（股數相加、成本以股數加權平均），避免賣出/proposed 計算錯誤
    merged_in: Dict[str, Dict[str, float]] = {}
    for h in holdings:
        sid = str(h.get("stock_id", "")).strip()
        if not sid:
            continue
        sh = _num(h.get("shares")) or 0.0
        cp = _num(h.get("cost_price")) or 0.0
        if sid in merged_in:
            m = merged_in[sid]
            tot = m["shares"] + sh
            m["cost_price"] = ((m["shares"] * m["cost_price"]) + (sh * cp)) / tot if tot > 0 else 0.0
            m["shares"] = tot
        else:
            merged_in[sid] = {"shares": sh, "cost_price": cp}

    # ── 持股健檢 ──
    enriched: List[Dict[str, Any]] = []
    total_value = 0.0
    for sid, m in merged_in.items():
        shares = m["shares"]
        r = get_row(sid)
        price = _num(r.get("latest_price")) if r is not None else None
        if price is None:
            price = m["cost_price"]
        value = shares * price
        total_value += value
        score = _num(r.get("total_score")) if r is not None else None
        enriched.append({
            "stock_id": sid,
            "name": name_map.get(sid, "") or (r.get("name") if r is not None else "") or "",
            "shares": shares,
            "cost_price": m["cost_price"],
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
            remaining = deploy
            for sid, r in picks:
                if remaining <= 0:
                    break
                w = float(r["total_score"]) / score_sum
                price = _num(r.get("latest_price")) or 0.0
                if price <= 0:
                    continue
                # 以「分數加權目標」與「剩餘現金」取小者，floor 取整股數 → 不會超買
                budget_for = min(deploy * w, remaining)
                shares = int(budget_for // price)
                if shares <= 0:
                    continue
                amt = shares * price
                if amt > remaining:
                    continue
                remaining -= amt
                sc = round(float(r["total_score"]), 1)
                buys.append({
                    "stock_id": sid, "name": name_map.get(sid, "") or "",
                    "shares": int(shares), "amount": round(amt),
                    "score": sc, "rating": r.get("rating"),
                    "reason": f"量化評分 {round(sc)}（{r.get('rating')}），依分數加權配置",
                })

            # 第二輪：把剩餘現金貪婪投入仍買得起的最高分標的（避免小額資金閒置；仍嚴格不超買）
            by_sid = {b["stock_id"]: b for b in buys}
            progressed = True
            while remaining > 0 and progressed:
                progressed = False
                for sid, r in picks:  # picks 已依分數由高到低排序
                    price = _num(r.get("latest_price")) or 0.0
                    if price <= 0 or price > remaining:
                        continue
                    remaining -= price
                    progressed = True
                    if sid in by_sid:
                        b = by_sid[sid]
                        b["shares"] += 1
                        b["amount"] = round(b["amount"] + price)
                    else:
                        sc = round(float(r["total_score"]), 1)
                        b = {
                            "stock_id": sid, "name": name_map.get(sid, "") or "",
                            "shares": 1, "amount": round(price),
                            "score": sc, "rating": r.get("rating"),
                            "reason": f"量化評分 {round(sc)}（{r.get('rating')}），剩餘資金加碼",
                        }
                        buys.append(b)
                        by_sid[sid] = b
                    if remaining <= 0:
                        break

    deployed = sum(b["amount"] for b in buys)
    # 剩餘現金 = 投入新資金 + 賣出套現 − 已部署買進
    cash_after = round(deploy + freed - deployed)

    # ── 套用用的新 holdings（由合併後 enriched 減去賣出、加上買入）──
    proposed: List[Dict[str, Any]] = []
    sell_map = {s["stock_id"]: s["shares"] for s in sells}
    for e in enriched:
        sid = e["stock_id"]
        shares = int(round(e["shares"]) - sell_map.get(sid, 0))
        if shares > 0:
            proposed.append({"stock_id": sid, "shares": shares, "cost_price": round(e["cost_price"], 2)})
    for b in buys:
        cost = round(b["amount"] / b["shares"], 2) if b["shares"] else 0.0
        proposed.append({"stock_id": b["stock_id"], "shares": b["shares"], "cost_price": cost})

    # ── 達標可行性（以「交易後」投組評分加權推估，含計畫買進）──
    feasibility = None
    if target_roi is not None:
        pw_score = 0.0
        pw_val = 0.0
        for ph in proposed:
            r2 = get_row(ph["stock_id"])
            sc2 = _num(r2.get("total_score")) if r2 is not None else None
            pr2 = _num(r2.get("latest_price")) if r2 is not None else ph.get("cost_price")
            v2 = ph["shares"] * (pr2 or 0)
            if sc2 is not None and v2 > 0:
                pw_score += sc2 * v2
                pw_val += v2
        post_avg = (pw_score / pw_val) if pw_val > 0 else (avg_score if avg_score > 0 else 50.0)
        exp_ret = _expected_annual_return(post_avg, cfg["exp_factor"])
        t = float(target_roi)
        verdict = "可行" if t <= exp_ret else "具挑戰" if t <= exp_ret * 1.5 else "偏高"
        feasibility = {
            "target_roi": t,
            "estimated_annual_return": exp_ret,
            "post_trade_avg_score": round(post_avg, 1),
            "verdict": verdict,
            "note": (
                f"依「交易後」投組量化評分（市值加權平均 {round(post_avg, 1)}）推估年化報酬約 {exp_ret}%（非保證），"
                f"集中度{concentration}、風險偏好「{risk_tolerance}」。目標 {t}% 評為「{verdict}」。"
                + ("　達標需提高持股評分或承擔更高波動。" if verdict != "可行" else "")
            ),
        }

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


def extract_holdings_from_image(image_base64: str, media_type: str = "image/png") -> Dict[str, Any]:
    """用 Claude Vision 從持股截圖擷取持股清單。不碰 FinLab（額度爆也可用）。

    回傳 {"holdings": [{stock_id, name, shares, cost_price}], "error": None|str}。
    """
    global _client
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"holdings": [], "error": "ANTHROPIC_API_KEY 未設定"}
    try:
        if _client is None:
            import anthropic
            _client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return {"holdings": [], "error": "anthropic 套件未安裝"}

    prompt = (
        "這是一張台股券商 App/網頁的持股（庫存）截圖。請逐檔擷取持股並輸出 JSON。\n"
        '格式：{"holdings":[{"stock_id":"2330","name":"台積電","shares":1000,"cost_price":900.0}]}\n'
        "規則：\n"
        "- stock_id：4 位數字代號字串（如 2330）。\n"
        "- shares：股數。若截圖單位是『張』請 ×1000 換成股數；若是『股』直接用。\n"
        "- cost_price：每股成本價（找不到就填 0）。\n"
        "- name：股票名稱，找不到填空字串。\n"
        "只輸出 JSON，不要任何說明文字或 markdown。"
    )
    try:
        msg = _client.messages.create(
            model=_NARRATIVE_MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = (msg.content[0].text or "").strip()
        # 去除可能的 ```json 包裹
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        import json as _json
        data = _json.loads(text)
        raw = data.get("holdings", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        import re as _re
        valid_sid = _re.compile(r"^[0-9]{4,6}[A-Z]?$")  # 台股代號：4-6 位數字 + 可選一位字母（如 0050/00878/2330/2891B）
        by_sid: Dict[str, Dict[str, Any]] = {}
        for h in raw:
            if not isinstance(h, dict):
                continue
            sid = str(h.get("stock_id", "")).strip().upper()
            if not valid_sid.match(sid):
                continue  # 過濾非法/非台股代號
            sh = max(0.0, _num(h.get("shares")) or 0.0)        # 非負
            cp = max(0.0, _num(h.get("cost_price")) or 0.0)    # 非負
            if sid in by_sid:
                by_sid[sid]["shares"] += sh                     # 同代號去重累加
            else:
                by_sid[sid] = {"stock_id": sid, "name": str(h.get("name", "") or ""), "shares": sh, "cost_price": cp}
        clean = list(by_sid.values())
        return {"holdings": clean, "error": None if clean else "未從截圖辨識出持股（或代號格式不符）"}
    except Exception as e:  # noqa: BLE001
        logger.error("持股截圖擷取失敗: %s", e)
        return {"holdings": [], "error": str(e)}
