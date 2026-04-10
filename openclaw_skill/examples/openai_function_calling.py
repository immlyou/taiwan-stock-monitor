"""
Example: OpenAI GPT-4/5 function calling with taiwan-stock-monitor.

Loads tool_catalog.json, converts to OpenAI function schema, and lets
GPT call the Railway REST API.

Run:
    pip install openai requests
    export OPENAI_API_KEY=sk-...
    python openai_function_calling.py
"""
import json
import os
import sys
from pathlib import Path

import requests

try:
    import openai
except ImportError:
    print("Install with: pip install openai requests")
    sys.exit(1)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "tool_catalog.json"
BASE = os.getenv("STOCK_API_URL", "https://taiwan-stock-api-production.up.railway.app")
KEY = os.getenv("STOCK_API_KEY", "").strip()

HEADERS = {"Authorization": f"Bearer {KEY}"} if KEY else {}


# ─── Tool name → REST endpoint mapping ───────────────────────────────────────
# Each entry returns (http_method, path, params_or_body).
DISPATCH: dict[str, callable] = {
    # market
    "market_summary":       lambda a: ("GET", "/market/summary", None),
    "market_heatmap":       lambda a: ("GET", "/market/heatmap", None),
    "market_money_flow":    lambda a: ("GET", "/market/money-flow", None),
    "market_after_hours":   lambda a: ("GET", "/market/after-hours", None),
    "market_benchmark":     lambda a: ("GET", "/market/benchmark", None),
    "market_industries":    lambda a: ("GET", "/market/industries", None),
    # stocks list
    "search_stocks":        lambda a: ("GET", "/stocks/search", {"q": a["query"], "limit": a.get("limit", 20)}),
    "list_active_stocks":   lambda a: ("GET", "/stocks/active", None),
    # individual stock
    "get_stock":            lambda a: ("GET", f"/stock/{a['stock_id']}", {"days": a.get("days", 5)}),
    "get_stock_technical":  lambda a: ("GET", f"/stock/{a['stock_id']}/technical", None),
    "get_stock_chip":       lambda a: ("GET", f"/stock/{a['stock_id']}/chip", {"days": a.get("days", 5)}),
    "get_stock_chip_detail":lambda a: ("GET", f"/stock/{a['stock_id']}/chip/detail", {"days": a.get("days", 30)}),
    "get_stock_ohlcv":      lambda a: ("GET", f"/stock/{a['stock_id']}/ohlcv", {"days": a.get("days", 60)}),
    "get_stock_financials": lambda a: ("GET", f"/stock/{a['stock_id']}/financials", None),
    "compare_stocks":       lambda a: ("GET", "/stocks/compare", {"stock_ids": a["stock_ids"]}),
    "get_realtime_quote":   lambda a: ("GET", f"/quote/realtime/{a['stock_id']}", None),
    # strategies
    "run_strategy":         lambda a: ("GET", f"/strategy/{a['strategy_type']}", {"preset": a.get("preset", "standard"), "top_n": a.get("top_n", 20)}),
    "run_screener":         lambda a: ("GET", "/screener", {k: v for k, v in a.items() if v is not None}),
    "ai_pick_stocks":       lambda a: ("GET", "/strategy/ai-pick", None),
    "composite_strategy":   lambda a: ("GET", "/strategy/composite", None),
    # AI
    "ai_claude_analysis":   lambda a: ("GET", f"/strategy/ai-claude/{a['stock_id']}", None),
    "ai_lstm_forecast":     lambda a: ("GET", f"/strategy/ai-lstm/{a['stock_id']}", None),
    "ai_xgboost_pick":      lambda a: ("GET", "/strategy/ai-xgboost", None),
    "ai_stock_chat":        lambda a: ("POST", "/ai/stock-chat", {"stock_id": a["stock_id"], "question": a["question"]}),
    "detect_anomalies":     lambda a: ("GET", "/ai/anomalies", {"top_n": a.get("top_n", 10)}),
    "ai_post_market_summary": lambda a: ("POST", "/ai/post-market-summary", {}),
    # backtest
    "run_backtest":         lambda a: ("POST", "/backtest/run", a),
    # portfolios / watchlists / alerts
    "list_portfolios":      lambda a: ("GET", "/portfolios", None),
    "get_portfolio":        lambda a: ("GET", f"/portfolios/{a['portfolio_id']}", None),
    "list_watchlists":      lambda a: ("GET", "/watchlists", None),
    "get_watchlist":        lambda a: ("GET", f"/watchlists/{a['watchlist_id']}", None),
    "list_alerts":          lambda a: ("GET", "/alerts", None),
    "check_alerts_now":     lambda a: ("GET", "/alerts/check", None),
    # system
    "health_check":         lambda a: ("GET", "/health", None),
}


def dispatch(name: str, args: dict) -> dict:
    """Turn a tool call into a REST request and execute it."""
    if name not in DISPATCH:
        return {"error": f"unknown tool: {name}"}
    method, path, payload = DISPATCH[name](args or {})
    try:
        if method == "GET":
            r = requests.get(f"{BASE}{path}", params=payload, headers=HEADERS, timeout=120)
        else:
            r = requests.post(f"{BASE}{path}", json=payload, headers=HEADERS, timeout=120)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        return {"error": str(e), "status": r.status_code, "body": r.text[:500]}


def load_openai_functions() -> list[dict]:
    catalog = json.loads(CATALOG_PATH.read_text())
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"].strip(),
                "parameters": t["input_schema"],
            },
        }
        for t in catalog["tools"]
    ]


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Set OPENAI_API_KEY to run this example.")
        return 1

    client = openai.OpenAI()
    tools = load_openai_functions()
    print(f"Loaded {len(tools)} tools from catalog.\n")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a Taiwan stock market assistant. "
                "Use the provided tools to answer questions with real market data. "
                "Reply in the same language as the user."
            ),
        },
        {
            "role": "user",
            "content": "台積電 (2330) 最近的技術面跟基本面狀況？用繁體中文回答。",
        },
    ]

    # Simple tool-use loop (max 5 rounds)
    for round_num in range(5):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            print("=" * 60)
            print(msg.content)
            print("=" * 60)
            return 0

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            print(f"→ Calling {call.function.name}({args})")
            result = dispatch(call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    print("Reached max rounds without final answer.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
