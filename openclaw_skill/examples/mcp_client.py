"""
Example: Connect to taiwan-stock MCP server as a Python MCP client.

Demonstrates the MCP stdio transport — spawns the server as a subprocess,
performs an MCP handshake, lists tools, and calls a few of them.

Run:
    pip install mcp httpx
    python mcp_client.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Locate mcp_server.py (parent directory of examples/)
SERVER = Path(__file__).resolve().parent.parent / "mcp_server.py"

BACKEND = os.getenv(
    "STOCK_API_URL",
    "https://taiwan-stock-api-production.up.railway.app",
)


async def main() -> int:
    if not SERVER.exists():
        print(f"❌ MCP server not found: {SERVER}")
        return 1

    params = StdioServerParameters(
        command=sys.executable,  # same Python that's running this script
        args=[str(SERVER)],
        env={"STOCK_API_URL": BACKEND, **os.environ},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. List tools
            tools_resp = await session.list_tools()
            tools = tools_resp.tools
            print(f"✅ Connected to MCP server. {len(tools)} tools available.\n")

            # 2. Call health_check
            h = await session.call_tool("health_check", {})
            payload = json.loads(h.content[0].text)
            print(f"✅ Backend status: {payload['status']} | "
                  f"data_date {payload['latest_data_date']}")

            # 3. Call market_summary
            m = await session.call_tool("market_summary", {})
            market = json.loads(m.content[0].text)
            print(f"\n📊 TAIEX {market['taiex_index']} "
                  f"({market['taiex_change']:+.2f}%) | "
                  f"up {market['up_count']} / down {market['down_count']}")

            # 4. Call get_stock with args
            s = await session.call_tool("get_stock", {"stock_id": "2330", "days": 5})
            stock = json.loads(s.content[0].text)
            print(f"\n🏭 {stock['name']} ({stock['stock_id']}) "
                  f"${stock['latest_price']} ({stock['change_pct']:+.2f}%)")

            # 5. Call run_screener with multiple optional filters
            scr = await session.call_tool(
                "run_screener",
                {"pe_max": 15, "dy_min": 4, "yoy_min": 10, "top_n": 5},
            )
            result = json.loads(scr.content[0].text)
            print(f"\n🔍 Screener: {result['total_matches']} matches")
            for stock in result["stocks"][:5]:
                print(f"   {stock['stock_id']} ${stock['price']}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
