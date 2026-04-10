"""
Example: Pure REST API access (no LLM, no MCP).

The simplest way to use taiwan-stock-monitor: just HTTP requests.
Works from any language — this happens to be Python.

Run:
    pip install requests
    python rest_api_direct.py
"""
import os
import sys

import requests

BASE = os.getenv("STOCK_API_URL", "https://taiwan-stock-api-production.up.railway.app")
KEY = os.getenv("STOCK_API_KEY", "").strip()

HEADERS = {"Authorization": f"Bearer {KEY}"} if KEY else {}


def get(path: str, **params) -> dict:
    r = requests.get(f"{BASE}{path}", params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict) -> dict:
    r = requests.post(f"{BASE}{path}", json=body, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> int:
    print(f"Backend: {BASE}\n")

    # 1. Health check
    h = get("/health")
    print(f"✅ Backend healthy — data date {h['latest_data_date']}, "
          f"{h['total_stocks']} stocks tracked")

    # 2. Market summary
    m = get("/market/summary")
    print(f"\n📊 TAIEX: {m['taiex_index']} ({m['taiex_change']:+.2f}%) "
          f"| 上漲 {m['up_count']} 下跌 {m['down_count']}")
    print("   Top 3 gainers:", ", ".join(
        f"{s['stock_id']} +{s['change_pct']}%" for s in m["top_gainers"][:3]
    ))

    # 3. Specific stock
    stock_id = "2330"
    s = get(f"/stock/{stock_id}", days=5)
    print(f"\n🏭 {s['stock_id']} {s['name']} ${s['latest_price']} "
          f"({s['change_pct']:+.2f}%)")
    print(f"   PE {s['pe_ratio']} | PB {s['pb_ratio']} | "
          f"Dividend Yield {s['dividend_yield']}% | Revenue YoY +{s['revenue_yoy']}%")

    # 4. Technical indicators
    t = get(f"/stock/{stock_id}/technical")
    print(f"   RSI(14) {t['rsi_14']:.1f} ({t['rsi_signal']}) | "
          f"MACD {t['macd']:.2f} | trend: {t['trend']}")

    # 5. Custom screener — low PE, high dividend yield
    screen = get("/screener", pe_max=15, dy_min=4, top_n=10)
    print(f"\n🔍 Screener (PE<15, DY>4%): {screen['total_matches']} matches")
    for s in screen["stocks"][:5]:
        print(f"   {s['stock_id']} ${s['price']}")

    # 6. Strategy pick — value investing, conservative preset
    strat = get("/strategy/value", preset="conservative", top_n=5)
    print(f"\n💎 Value strategy (conservative): {strat['total_matches']} matches")
    for s in strat["stocks"]:
        print(f"   {s['stock_id']} {s.get('name', '')} "
              f"PE={s.get('pe_ratio')} DY={s.get('dividend_yield')}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
