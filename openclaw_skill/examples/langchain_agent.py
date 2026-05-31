"""
Example: LangChain agent wrapping taiwan-stock-monitor tools.

Demonstrates how to turn the REST API into LangChain @tool functions that
any LangChain agent (OpenAI, Anthropic, Ollama...) can use.

Run:
    pip install langchain-core langchain-openai requests
    export OPENAI_API_KEY=sk-...
    python langchain_agent.py
"""
import os
import sys

import requests

try:
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    print("Install with: pip install langchain-core langchain-openai requests")
    sys.exit(1)

BASE = os.getenv("STOCK_API_URL", "https://taiwan-stock-api-production.up.railway.app")
KEY = os.getenv("STOCK_API_KEY", "").strip()
HEADERS = {"Authorization": f"Bearer {KEY}"} if KEY else {}


def _get(path: str, **params) -> dict:
    r = requests.get(f"{BASE}{path}", params={k: v for k, v in params.items() if v is not None},
                     headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{BASE}{path}", json=body, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.json()


# ─── Define a handful of representative tools ───────────────────────────────
# Expand this list by following the pattern — see tool_catalog.json for all 34.

@tool
def market_summary() -> dict:
    """Get Taiwan stock market summary: TAIEX index, up/down counts, top gainers/losers."""
    return _get("/market/summary")


@tool
def get_stock(stock_id: str, days: int = 5) -> dict:
    """Get stock basic info and recent price history.

    Args:
        stock_id: Stock code (e.g. '2330' for TSMC).
        days: Number of past days to include (1-250).
    """
    return _get(f"/stock/{stock_id}", days=days)


@tool
def get_stock_technical(stock_id: str) -> dict:
    """Get technical indicators for a stock: RSI, MACD, SMA 5/20/60, trend."""
    return _get(f"/stock/{stock_id}/technical")


@tool
def get_stock_chip(stock_id: str, days: int = 5) -> dict:
    """Get institutional buy/sell activity for a stock over recent days.

    Args:
        stock_id: Stock code.
        days: Number of days (1-60).
    """
    return _get(f"/stock/{stock_id}/chip", days=days)


@tool
def run_screener(
    pe_max: float | None = None,
    pe_min: float | None = None,
    dy_min: float | None = None,
    yoy_min: float | None = None,
    top_n: int = 20,
) -> dict:
    """Custom stock screener with optional filters.

    Args:
        pe_max: Maximum P/E ratio.
        pe_min: Minimum P/E ratio.
        dy_min: Minimum dividend yield percentage.
        yoy_min: Minimum revenue YoY growth percentage.
        top_n: Max number of results (1-100).
    """
    return _get("/screener", pe_max=pe_max, pe_min=pe_min,
                dy_min=dy_min, yoy_min=yoy_min, top_n=top_n)


@tool
def run_strategy(strategy_type: str, preset: str = "standard", top_n: int = 10) -> dict:
    """Run a predefined stock picking strategy.

    Args:
        strategy_type: One of 'value', 'growth', 'momentum'.
        preset: 'conservative' | 'standard' | 'aggressive'.
        top_n: Number of top picks to return.
    """
    return _get(f"/strategy/{strategy_type}", preset=preset, top_n=top_n)


@tool
def check_alerts_now() -> dict:
    """Check all configured alerts against current market data."""
    return _get("/alerts/check")


TOOLS = [
    market_summary, get_stock, get_stock_technical, get_stock_chip,
    run_screener, run_strategy, check_alerts_now,
]


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Set OPENAI_API_KEY to run this example.")
        return 1

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = [
        SystemMessage(
            "You are a Taiwan stock market assistant. "
            "Use the provided tools to look up real data before answering."
        ),
        HumanMessage(
            "幫我找本益比 < 12、殖利率 > 5%、營收年增率 > 10% 的前 5 檔股票，"
            "並對第一名做技術面快速分析。"
        ),
    ]

    # Manual tool-use loop (keeps example minimal, no langgraph required)
    for _ in range(5):
        resp = llm_with_tools.invoke(messages)
        messages.append(resp)

        if not resp.tool_calls:
            print("=" * 60)
            print(resp.content)
            print("=" * 60)
            return 0

        for call in resp.tool_calls:
            name = call["name"]
            args = call["args"]
            print(f"→ {name}({args})")
            target = next(t for t in TOOLS if t.name == name)
            result = target.invoke(args)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": str(result),
            })

    print("Reached max rounds.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
