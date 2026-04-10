"""
Taiwan Stock Monitor - MCP Server
==================================

A Model Context Protocol (MCP) server that exposes the taiwan-stock-monitor
REST API as MCP tools. Any MCP-compatible client (Claude Desktop, Claude Code,
Cursor, OpenClaw, etc.) can connect via stdio and use these tools.

Quick test:
    python mcp_server.py --test

Environment variables:
    STOCK_API_URL   Backend base URL. Default: Railway production.
    STOCK_API_KEY   Bearer token if the backend enables STOCK_API_KEY protection.
    STOCK_TIMEOUT   HTTP timeout in seconds. Default: 60.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ─── Configuration ──────────────────────────────────────────────────────────
API_URL = os.getenv("STOCK_API_URL", "https://taiwan-stock-api-production.up.railway.app").rstrip("/")
API_KEY = os.getenv("STOCK_API_KEY", "").strip()
TIMEOUT = float(os.getenv("STOCK_TIMEOUT", "60"))

mcp = FastMCP("taiwan-stock-monitor")


# ─── HTTP helpers ───────────────────────────────────────────────────────────
def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


async def _get(path: str, params: Optional[dict[str, Any]] = None) -> dict:
    if params:
        params = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{API_URL}{path}", params=params, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, json_body: Optional[dict[str, Any]] = None) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{API_URL}{path}", json=json_body or {}, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# Market overview tools
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def market_summary() -> dict:
    """
    Get Taiwan stock market summary: TAIEX index, up/down counts, top 10 gainers and losers.
    Use this for daily market overview questions like "how is Taiwan stock market today".
    """
    return await _get("/market/summary")


@mcp.tool()
async def market_heatmap() -> dict:
    """
    Get market heatmap grouped by industry. Returns each active stock with its
    price and percentage change, organized under industry categories.
    Useful for "which industries are hot today".
    """
    return await _get("/market/heatmap")


@mcp.tool()
async def market_money_flow() -> dict:
    """
    Get institutional money flow: net buy/sell from foreign investors, investment
    trust, and dealers. Includes top 10 most-bought and most-sold stocks per group.
    """
    return await _get("/market/money-flow")


@mcp.tool()
async def market_after_hours() -> dict:
    """
    After-hours market summary: TAIEX close, top 5 gainers/losers, institutional net,
    and value/growth/momentum strategy top picks for the day.
    """
    return await _get("/market/after-hours")


@mcp.tool()
async def market_benchmark() -> dict:
    """Get TAIEX benchmark index history."""
    return await _get("/market/benchmark")


@mcp.tool()
async def market_industries() -> dict:
    """Get performance ranking across industry sectors."""
    return await _get("/market/industries")


# ═══════════════════════════════════════════════════════════════════════════
# Stock list / search
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_stocks(query: str, limit: int = 20) -> dict:
    """
    Search stocks by ID or name (fuzzy match).

    Args:
        query: Search keyword — either stock code like "2330" or name like "台積電".
        limit: Max results to return (1-100). Default 20.
    """
    return await _get("/stocks/search", {"q": query, "limit": limit})


@mcp.tool()
async def list_active_stocks() -> dict:
    """
    List all actively trading stocks (traded within last 30 days).
    Includes latest price and daily change percentage for each.
    """
    return await _get("/stocks/active")


# ═══════════════════════════════════════════════════════════════════════════
# Individual stock analysis
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_stock(stock_id: str, days: int = 5) -> dict:
    """
    Get basic info + recent price history for a stock.
    Returns: name, industry, latest price, change%, PE/PB/dividend yield, revenue YoY, price_history.

    Args:
        stock_id: Stock code, e.g. "2330" (TSMC).
        days: Recent N days of price history (1-250). Default 5.
    """
    return await _get(f"/stock/{stock_id}", {"days": days})


@mcp.tool()
async def get_stock_technical(stock_id: str) -> dict:
    """
    Technical indicators for a stock: RSI(14), MACD, SMA 5/20/60, trend, signals.

    Args:
        stock_id: Stock code, e.g. "2330".
    """
    return await _get(f"/stock/{stock_id}/technical")


@mcp.tool()
async def get_stock_chip(stock_id: str, days: int = 5) -> dict:
    """
    Chip analysis for a stock: foreign/trust/dealer buy-sell, margin, foreign holding %.

    Args:
        stock_id: Stock code.
        days: Recent N days (1-60). Default 5.
    """
    return await _get(f"/stock/{stock_id}/chip", {"days": days})


@mcp.tool()
async def get_stock_chip_detail(stock_id: str, days: int = 30) -> dict:
    """
    Detailed chip analysis with daily history of institutional activity.

    Args:
        stock_id: Stock code.
        days: Recent N days. Default 30.
    """
    return await _get(f"/stock/{stock_id}/chip/detail", {"days": days})


@mcp.tool()
async def get_stock_ohlcv(stock_id: str, days: int = 60) -> dict:
    """
    OHLCV price history for a stock — open, high, low, close, volume per day.

    Args:
        stock_id: Stock code.
        days: Recent N days. Default 60.
    """
    return await _get(f"/stock/{stock_id}/ohlcv", {"days": days})


@mcp.tool()
async def get_stock_financials(stock_id: str) -> dict:
    """
    Financial statements summary for a stock: revenue, profit, EPS, growth rates.

    Args:
        stock_id: Stock code.
    """
    return await _get(f"/stock/{stock_id}/financials")


@mcp.tool()
async def compare_stocks(stock_ids: str) -> dict:
    """
    Compare multiple stocks side by side on key metrics.

    Args:
        stock_ids: Comma-separated stock codes, e.g. "2330,2317,2454".
    """
    return await _get("/stocks/compare", {"stock_ids": stock_ids})


@mcp.tool()
async def get_realtime_quote(stock_id: str) -> dict:
    """
    Get realtime (may be ~20 min delayed) quote for a stock.

    Args:
        stock_id: Stock code.
    """
    return await _get(f"/quote/realtime/{stock_id}")


# ═══════════════════════════════════════════════════════════════════════════
# Strategies & screener
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def run_strategy(strategy_type: str, preset: str = "standard", top_n: int = 20) -> dict:
    """
    Run a predefined stock picking strategy.

    Args:
        strategy_type: One of "value" (low PE + high yield), "growth" (revenue YoY),
                       "momentum" (price breakout + volume).
        preset: "conservative" | "standard" | "aggressive". Default "standard".
        top_n: Return top N picks (1-50). Default 20.
    """
    return await _get(f"/strategy/{strategy_type}", {"preset": preset, "top_n": top_n})


@mcp.tool()
async def run_screener(
    pe_max: Optional[float] = None,
    pe_min: Optional[float] = None,
    pb_max: Optional[float] = None,
    dy_min: Optional[float] = None,
    yoy_min: Optional[float] = None,
    rsi_max: Optional[float] = None,
    rsi_min: Optional[float] = None,
    top_n: int = 20,
) -> dict:
    """
    Custom stock screener. Combine any subset of filters (all optional).

    Args:
        pe_max: Max P/E ratio.
        pe_min: Min P/E ratio.
        pb_max: Max P/B ratio.
        dy_min: Min dividend yield (%).
        yoy_min: Min revenue YoY growth (%).
        rsi_max: Max RSI(14).
        rsi_min: Min RSI(14).
        top_n: Max results (1-100). Default 20.
    """
    return await _get(
        "/screener",
        {
            "pe_max": pe_max, "pe_min": pe_min, "pb_max": pb_max,
            "dy_min": dy_min, "yoy_min": yoy_min,
            "rsi_max": rsi_max, "rsi_min": rsi_min,
            "top_n": top_n,
        },
    )


@mcp.tool()
async def ai_pick_stocks() -> dict:
    """Get composite AI-recommended stock picks (combines multiple signals)."""
    return await _get("/strategy/ai-pick")


@mcp.tool()
async def composite_strategy() -> dict:
    """Run composite strategy that aggregates value + growth + momentum signals."""
    return await _get("/strategy/composite")


# ═══════════════════════════════════════════════════════════════════════════
# AI analysis tools
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def ai_claude_analysis(stock_id: str) -> dict:
    """
    Claude AI-powered deep analysis of a stock (fundamentals + technicals + chip).
    Takes ~10-30 seconds.

    Args:
        stock_id: Stock code.
    """
    return await _get(f"/strategy/ai-claude/{stock_id}")


@mcp.tool()
async def ai_lstm_forecast(stock_id: str) -> dict:
    """
    LSTM neural-network price forecast for a stock.

    Args:
        stock_id: Stock code.
    """
    return await _get(f"/strategy/ai-lstm/{stock_id}")


@mcp.tool()
async def ai_xgboost_pick() -> dict:
    """XGBoost ML-based stock picks across the market."""
    return await _get("/strategy/ai-xgboost")


@mcp.tool()
async def ai_stock_chat(stock_id: str, question: str) -> dict:
    """
    Chat with AI about a specific stock — free-form Q&A.

    Args:
        stock_id: Stock code.
        question: User question in natural language.
    """
    return await _post("/ai/stock-chat", {"stock_id": stock_id, "question": question})


@mcp.tool()
async def detect_anomalies(top_n: int = 10) -> dict:
    """
    Detect price/volume anomalies across the market (unusual moves).

    Args:
        top_n: Max anomalies to return. Default 10.
    """
    return await _get("/ai/anomalies", {"top_n": top_n})


@mcp.tool()
async def ai_post_market_summary() -> dict:
    """AI-generated post-market narrative summary for the day."""
    return await _post("/ai/post-market-summary")


# ═══════════════════════════════════════════════════════════════════════════
# Backtest
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def run_backtest(
    strategy: str,
    initial_capital: float = 1000000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rebalance_frequency: str = "monthly",
    preset: str = "standard",
) -> dict:
    """
    Run a strategy backtest. Takes 5-30 seconds.

    Args:
        strategy: "value" | "growth" | "momentum".
        initial_capital: Starting capital. Default 1,000,000 TWD.
        start_date: Start date YYYY-MM-DD (optional, defaults to 3 years ago).
        end_date: End date YYYY-MM-DD (optional, defaults to today).
        rebalance_frequency: "daily" | "weekly" | "monthly" | "quarterly". Default "monthly".
        preset: "conservative" | "standard" | "aggressive". Default "standard".
    """
    body: dict[str, Any] = {
        "strategy": strategy,
        "initial_capital": initial_capital,
        "rebalance_frequency": rebalance_frequency,
        "preset": preset,
    }
    if start_date:
        body["start_date"] = start_date
    if end_date:
        body["end_date"] = end_date
    return await _post("/backtest/run", body)


# ═══════════════════════════════════════════════════════════════════════════
# Portfolios (read-only via MCP to keep things safe)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_portfolios() -> dict:
    """List all saved portfolios (id, name, created_at, total_value)."""
    return await _get("/portfolios")


@mcp.tool()
async def get_portfolio(portfolio_id: str) -> dict:
    """
    Get full portfolio details: holdings, cost basis, current value, P&L.

    Args:
        portfolio_id: Portfolio ID from list_portfolios.
    """
    return await _get(f"/portfolios/{portfolio_id}")


# ═══════════════════════════════════════════════════════════════════════════
# Watchlists
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_watchlists() -> dict:
    """List all saved watchlists."""
    return await _get("/watchlists")


@mcp.tool()
async def get_watchlist(watchlist_id: str) -> dict:
    """
    Get a watchlist with current prices and changes for all stocks in it.

    Args:
        watchlist_id: Watchlist ID from list_watchlists.
    """
    return await _get(f"/watchlists/{watchlist_id}")


# ═══════════════════════════════════════════════════════════════════════════
# Alerts
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_alerts() -> dict:
    """List all configured price/condition alerts."""
    return await _get("/alerts")


@mcp.tool()
async def check_alerts_now() -> dict:
    """Check all alerts against current market data and return triggered ones."""
    return await _get("/alerts/check")


# ═══════════════════════════════════════════════════════════════════════════
# System / health
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def health_check() -> dict:
    """
    Check backend health. Returns status, data date, total stocks, FinLab quota usage.
    Use this as a first call to confirm the connection works.
    """
    return await _get("/health")


# ═══════════════════════════════════════════════════════════════════════════
# Daily briefing (OpenClaw / Claude agents call this on demand)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def generate_daily_briefing() -> dict:
    """
    Generate a complete Taiwan stock market daily briefing in one call.

    One-shot tool that returns everything for a morning/after-hours report:
    TAIEX index + change, up/down counts, top 5 gainers/losers, the day's
    strategy picks (value/growth/momentum), news headlines with sentiment-driven
    market outlook, and a pre-written Traditional Chinese summary sentence.

    Use this when the user asks for "晨報", "今日總結", "台股今天怎麼樣完整一點"
    instead of chaining market_summary + run_strategy + news separately.

    Returns:
        {
            "date": "YYYY-MM-DD",
            "summary": "台股加權指數 ... 點，上漲 ...%。上漲家數 ...，下跌家數 ...",
            "keyPoints": ["新聞標題1", ...],   // up to 5 headlines
            "marketOutlook": "今日新聞偏多/偏空/中性，...",
            "taiex_index": float,
            "taiex_change": float,
            "market": {"up": int, "down": int, "flat": int},
            "top_gainers": [{"stock_id": "...", "change_pct": float}, ...5],
            "top_losers":  [{"stock_id": "...", "change_pct": float}, ...5],
            "strategies":  {
                "value":    {"total": int, "top5": [stock_ids]},
                "growth":   {"total": int, "top5": [stock_ids]},
                "momentum": {"total": int, "top5": [stock_ids]},
            }
        }
    """
    return await _get("/morning-report")


# ═══════════════════════════════════════════════════════════════════════════
# Self-test mode
# ═══════════════════════════════════════════════════════════════════════════

async def _self_test() -> int:
    """Run a quick sanity check against the configured backend."""
    print(f"🧪 Testing MCP server against: {API_URL}")
    print(f"   Auth: {'Bearer token set' if API_KEY else '(no token)'}")
    print(f"   Timeout: {TIMEOUT}s\n")

    try:
        h = await _get("/health")
        print(f"✅ /health: {h.get('status')} | data_date={h.get('latest_data_date')} | stocks={h.get('total_stocks')}")
    except Exception as e:
        print(f"❌ /health failed: {e}")
        return 1

    try:
        m = await _get("/market/summary")
        print(f"✅ /market/summary: TAIEX={m.get('taiex_index')} ({m.get('taiex_change')}%) "
              f"up={m.get('up_count')} down={m.get('down_count')}")
    except Exception as e:
        print(f"⚠️  /market/summary failed: {e}")

    try:
        s = await _get("/stock/2330", {"days": 3})
        print(f"✅ /stock/2330: {s.get('name')} ${s.get('latest_price')} ({s.get('change_pct')}%)")
    except Exception as e:
        print(f"⚠️  /stock/2330 failed: {e}")

    # Count registered tools
    tool_count = len(await mcp.list_tools())
    print(f"\n📦 MCP tools registered: {tool_count}")
    return 0


async def _dump_schema() -> int:
    """Dump the full tool catalog as JSON (stdout). Machine-readable."""
    import json
    tools = await mcp.list_tools()
    catalog = {
        "name": "taiwan-stock-monitor",
        "version": "1.0.0",
        "description": "Taiwan stock market data, analysis, strategies, backtests, AI insights",
        "backend": API_URL,
        "protocol": "mcp-1.0",
        "transport": "stdio",
        "total_tools": len(tools),
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in tools
        ],
    }
    print(json.dumps(catalog, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    if "--test" in sys.argv:
        sys.exit(asyncio.run(_self_test()))
    if "--dump-schema" in sys.argv:
        sys.exit(asyncio.run(_dump_schema()))
    # Default: run as MCP server over stdio
    mcp.run()


if __name__ == "__main__":
    main()
