# Taiwan Stock Monitor — MCP Server

A Model Context Protocol (MCP) server that exposes the taiwan-stock-monitor REST API
as tools for any MCP-compatible client.

## What's inside

`mcp_server.py` registers **33 tools** wrapping the Railway-hosted FastAPI backend:

| Category | Tools |
|---|---|
| **Market** | `market_summary`, `market_heatmap`, `market_money_flow`, `market_after_hours`, `market_benchmark`, `market_industries` |
| **Stock list** | `search_stocks`, `list_active_stocks` |
| **Stock detail** | `get_stock`, `get_stock_technical`, `get_stock_chip`, `get_stock_chip_detail`, `get_stock_ohlcv`, `get_stock_financials`, `compare_stocks`, `get_realtime_quote` |
| **Strategy** | `run_strategy`, `run_screener`, `ai_pick_stocks`, `composite_strategy` |
| **AI analysis** | `ai_claude_analysis`, `ai_lstm_forecast`, `ai_xgboost_pick`, `ai_stock_chat`, `detect_anomalies`, `ai_post_market_summary` |
| **Backtest** | `run_backtest` |
| **Portfolios** | `list_portfolios`, `get_portfolio` |
| **Watchlists** | `list_watchlists`, `get_watchlist` |
| **Alerts** | `list_alerts`, `check_alerts_now` |
| **System** | `health_check` |

## Setup

```bash
cd openclaw_skill
pip install -r requirements-mcp.txt
```

## Verify it works

```bash
python mcp_server.py --test
```

Expected output:
```
🧪 Testing MCP server against: https://taiwan-stock-api-production.up.railway.app
   Auth: (no token)
   Timeout: 60.0s

✅ /health: ok | data_date=2026-04-09 | stocks=2721
✅ /market/summary: TAIEX=34861.16 (0.287%) up=885 down=1233
✅ /stock/2330: 台積電 $... (...%)

📦 MCP tools registered: 33
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `STOCK_API_URL` | `https://taiwan-stock-api-production.up.railway.app` | Backend base URL |
| `STOCK_API_KEY` | *(empty)* | Bearer token if backend enables auth |
| `STOCK_TIMEOUT` | `60` | HTTP timeout (seconds) |

## Client integration

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS — Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "taiwan-stock": {
      "command": "python",
      "args": [
        "/Users/imchris/code/1-active/stock/taiwan-stock-monitor/openclaw_skill/mcp_server.py"
      ],
      "env": {
        "STOCK_API_URL": "https://taiwan-stock-api-production.up.railway.app"
      }
    }
  }
}
```

Restart Claude Desktop. The tools should appear in the hammer (🔨) menu.

### Claude Code

```bash
claude mcp add taiwan-stock \
  python /Users/imchris/code/1-active/stock/taiwan-stock-monitor/openclaw_skill/mcp_server.py \
  -e STOCK_API_URL=https://taiwan-stock-api-production.up.railway.app
```

Or add to `.mcp.json` at your project root:

```json
{
  "mcpServers": {
    "taiwan-stock": {
      "command": "python",
      "args": ["./openclaw_skill/mcp_server.py"],
      "env": {
        "STOCK_API_URL": "https://taiwan-stock-api-production.up.railway.app"
      }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "taiwan-stock": {
      "command": "python",
      "args": ["/absolute/path/to/openclaw_skill/mcp_server.py"]
    }
  }
}
```

### OpenClaw / other MCP-capable clients

Any client that supports MCP stdio transport can connect. Use the same pattern:
- Command: `python`
- Args: path to `mcp_server.py`
- Env (optional): `STOCK_API_URL`, `STOCK_API_KEY`

If your OpenClaw build is the older Python-skill format (not MCP), keep using
`taiwan_stock_skill.py` in this same folder — just point `STOCK_API_URL` at the
Railway URL instead of localhost.

## Example prompts (after connecting)

- "What's the Taiwan stock market doing today?" → `market_summary`
- "Show me TSMC's technical indicators" → `get_stock_technical("2330")`
- "Find stocks with PE below 12 and dividend yield above 5%" → `run_screener(pe_max=12, dy_min=5)`
- "Run a momentum strategy backtest for 2024" → `run_backtest("momentum", start_date="2024-01-01", end_date="2024-12-31")`
- "Analyze 聯發科 with AI" → `search_stocks("聯發科")` → `ai_claude_analysis("2454")`
- "Any alerts firing right now?" → `check_alerts_now`

## Architecture

```
MCP Client (Claude Desktop / Code / OpenClaw / Cursor)
  │ stdio (MCP protocol)
  ▼
mcp_server.py (this file)
  │ HTTPS
  ▼
Railway FastAPI  → taiwan-stock-api-production.up.railway.app
  │
  ▼
FinLab / Goodinfo / Yahoo / Claude API / local SQLite
```

All tool calls are stateless HTTP requests — no local state, no caching beyond what
the backend already provides.

## Security note

The backend currently has **no API key protection** (`STOCK_API_KEY` unset in
Railway). Anyone who knows the URL can call it. When you decide to lock it down:

1. Set `STOCK_API_KEY=<random token>` in Railway
2. Add the same `STOCK_API_KEY=<token>` to this MCP server's env in every client config
3. Also add it to Vercel env vars so the frontend rewrite can still reach the API
