# Taiwan Stock Monitor — 第三方整合指南

**Version:** 1.0.0  **Date:** 2026-04-10

這份文件給任何想串接 taiwan-stock-monitor 的 APP / AI 代理 / OpenClaw / 自製系統用。

---

## TL;DR — 三分鐘快速串接

| 你的需求 | 推薦方案 |
|---|---|
| **AI 代理 / LLM client**（Claude Desktop、Claude Code、Cursor、OpenClaw MCP 版、Continue、Cline） | → [方案 A：MCP stdio](#方案-a--mcp-stdio協議) |
| **任何能發 HTTPS 請求的程式**（Python、Node、Go、Rust、curl、Shell、n8n、Zapier） | → [方案 B：REST API 直呼](#方案-b--rest-api-直呼) |
| **OpenAI / Anthropic / Gemini function calling** | → [方案 C：載入 tool_catalog.json](#方案-c--function-calling-catalog) |
| **OpenClaw 舊版 Python skill** | → [方案 D：Python skill wrapper](#方案-d--openclaw-python-skill) |

**後端位址（統一入口）：**
```
https://taiwan-stock-api-production.up.railway.app
```

**目前認證狀態：** 🟡 無金鑰保護，公開讀取即可。未來若啟用 `STOCK_API_KEY`，所有方案都只要加 `Authorization: Bearer <token>` header。

---

## 能力一覽（34 個 tool / endpoint）

| 分類 | Tool 名稱 | REST 端點 | 用途 |
|---|---|---|---|
| **市場** | `market_summary` | `GET /market/summary` | 大盤指數 + 漲跌家數 + Top10 |
| | `market_heatmap` | `GET /market/heatmap` | 產業熱力圖 |
| | `market_money_flow` | `GET /market/money-flow` | 三大法人買賣超 |
| | `market_after_hours` | `GET /market/after-hours` | 盤後總覽 + 策略選股 |
| | `market_benchmark` | `GET /market/benchmark` | 加權指數歷史 |
| | `market_industries` | `GET /market/industries` | 產業績效排名 |
| **搜尋** | `search_stocks` | `GET /stocks/search?q={q}` | 模糊搜尋（代號/名稱） |
| | `list_active_stocks` | `GET /stocks/active` | 活躍股清單 |
| **個股** | `get_stock` | `GET /stock/{id}` | 基本資訊 + 近期價格 |
| | `get_stock_technical` | `GET /stock/{id}/technical` | RSI / MACD / SMA |
| | `get_stock_chip` | `GET /stock/{id}/chip` | 法人買賣超（5天） |
| | `get_stock_chip_detail` | `GET /stock/{id}/chip/detail` | 法人買賣超（30天） |
| | `get_stock_ohlcv` | `GET /stock/{id}/ohlcv` | K 線 OHLCV |
| | `get_stock_financials` | `GET /stock/{id}/financials` | 財報摘要 |
| | `compare_stocks` | `GET /stocks/compare?stock_ids=` | 多檔比較 |
| | `get_realtime_quote` | `GET /quote/realtime/{id}` | 即時報價（~20 分延遲） |
| **策略** | `run_strategy` | `GET /strategy/{type}` | 預設策略（value/growth/momentum） |
| | `run_screener` | `GET /screener` | 自訂篩選條件 |
| | `ai_pick_stocks` | `GET /strategy/ai-pick` | AI 綜合推薦 |
| | `composite_strategy` | `GET /strategy/composite` | 價值+成長+動能複合策略 |
| **AI 分析** | `ai_claude_analysis` | `GET /strategy/ai-claude/{id}` | Claude 深度分析個股 |
| | `ai_lstm_forecast` | `GET /strategy/ai-lstm/{id}` | LSTM 價格預測 |
| | `ai_xgboost_pick` | `GET /strategy/ai-xgboost` | XGBoost 機器學習選股 |
| | `ai_stock_chat` | `POST /ai/stock-chat` | AI 問答（自由格式） |
| | `detect_anomalies` | `GET /ai/anomalies` | 異常行情偵測 |
| | `ai_post_market_summary` | `POST /ai/post-market-summary` | AI 盤後敘事摘要 |
| **回測** | `run_backtest` | `POST /backtest/run` | 策略回測（5-30秒） |
| **投組** | `list_portfolios` | `GET /portfolios` | 列表 |
| | `get_portfolio` | `GET /portfolios/{id}` | 明細 + 損益 |
| **自選股** | `list_watchlists` | `GET /watchlists` | 列表 |
| | `get_watchlist` | `GET /watchlists/{id}` | 明細 + 現價 |
| **警報** | `list_alerts` | `GET /alerts` | 列表 |
| | `check_alerts_now` | `GET /alerts/check` | 立即檢查觸發 |
| **系統** | `health_check` | `GET /health` | 後端健康 + 資料日期 |

完整機器可讀 schema：[`tool_catalog.json`](./tool_catalog.json)（34 個 tool 的 JSON Schema）

---

## 方案 A — MCP stdio（協議）

### 適用對象
支援 Model Context Protocol 的任何 AI client：
- Claude Desktop
- Claude Code CLI
- Cursor
- Continue / Cline
- OpenClaw MCP 版
- LangChain MCP adapter
- 自製 agent

### 安裝一次性依賴
```bash
pip install 'mcp>=1.2.0' httpx>=0.27.0
```

### 連接資訊
```yaml
transport: stdio
command: python
args:
  - /path/to/openclaw_skill/mcp_server.py
env:
  STOCK_API_URL: https://taiwan-stock-api-production.up.railway.app
  # STOCK_API_KEY: <optional bearer token>
  # STOCK_TIMEOUT: "60"
```

### Claude Desktop 設定

編輯 `~/Library/Application Support/Claude/claude_desktop_config.json`
（Windows：`%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "taiwan-stock": {
      "command": "python",
      "args": ["/absolute/path/to/openclaw_skill/mcp_server.py"],
      "env": {
        "STOCK_API_URL": "https://taiwan-stock-api-production.up.railway.app"
      }
    }
  }
}
```

### Claude Code 設定

```bash
claude mcp add taiwan-stock \
  python /absolute/path/to/openclaw_skill/mcp_server.py \
  --scope user \
  --env STOCK_API_URL=https://taiwan-stock-api-production.up.railway.app
```

### Python MCP client 範例

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server = StdioServerParameters(
        command="python",
        args=["/path/to/openclaw_skill/mcp_server.py"],
        env={"STOCK_API_URL": "https://taiwan-stock-api-production.up.railway.app"},
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 列出 tool
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")

            # 呼叫 tool
            result = await session.call_tool("get_stock", {"stock_id": "2330", "days": 5})
            print(result.content[0].text)

asyncio.run(main())
```

---

## 方案 B — REST API 直呼

### 適用對象
任何能發 HTTPS 請求的系統。不需要 Python、不需要 MCP、不需要裝任何 SDK。

### Base URL
```
https://taiwan-stock-api-production.up.railway.app
```

### Python + requests

```python
import requests

BASE = "https://taiwan-stock-api-production.up.railway.app"

# 個股資訊
r = requests.get(f"{BASE}/stock/2330", params={"days": 10})
print(r.json())

# 自訂篩選
r = requests.get(f"{BASE}/screener", params={
    "pe_max": 15, "dy_min": 5, "yoy_min": 10, "top_n": 20
})
print(r.json())

# AI 問答（POST）
r = requests.post(f"{BASE}/ai/stock-chat", json={
    "stock_id": "2330", "question": "最近的主要風險是什麼？"
})
print(r.json())
```

### Node.js + fetch

```javascript
const BASE = 'https://taiwan-stock-api-production.up.railway.app';

// 大盤總覽
const summary = await fetch(`${BASE}/market/summary`).then(r => r.json());
console.log(summary.taiex_index, summary.taiex_change);

// 篩選
const params = new URLSearchParams({ pe_max: 15, dy_min: 5, top_n: 20 });
const picks = await fetch(`${BASE}/screener?${params}`).then(r => r.json());
console.log(picks.stocks);
```

### curl / shell

```bash
BASE=https://taiwan-stock-api-production.up.railway.app

# 健康檢查
curl -s $BASE/health | jq

# 台積電技術指標
curl -s $BASE/stock/2330/technical | jq

# 篩選本益比低殖利率高的股票
curl -s "$BASE/screener?pe_max=12&dy_min=5&top_n=10" | jq

# AI 分析（POST）
curl -s -X POST $BASE/ai/stock-chat \
  -H "Content-Type: application/json" \
  -d '{"stock_id":"2330","question":"中長期展望"}' | jq
```

### OpenAPI 規格

FastAPI 自動生成的 OpenAPI 3 spec：
- Interactive docs: https://taiwan-stock-api-production.up.railway.app/docs
- Raw spec: https://taiwan-stock-api-production.up.railway.app/openapi.json

把 `openapi.json` 丟進 Postman / Insomnia / openapi-generator 就能一鍵產 client。

---

## 方案 C — Function Calling Catalog

### 適用對象
想把這個後端接成 LLM 的 function calling / tool use：
- OpenAI GPT-4/5 Function Calling
- Anthropic Claude Tool Use
- Google Gemini Function Calling
- Ollama Tools
- 任何 LangChain / LlamaIndex agent

### 檔案
`tool_catalog.json` 是機器可讀的 34 個 tool 完整描述。格式：

```json
{
  "name": "taiwan-stock-monitor",
  "version": "1.0.0",
  "backend": "https://taiwan-stock-api-production.up.railway.app",
  "total_tools": 34,
  "tools": [
    {
      "name": "get_stock",
      "description": "Get basic info + recent price history for a stock...",
      "input_schema": {
        "type": "object",
        "properties": {
          "stock_id": { "type": "string" },
          "days": { "type": "integer", "default": 5 }
        },
        "required": ["stock_id"]
      }
    },
    ...
  ]
}
```

### OpenAI function calling

```python
import json, openai, requests

catalog = json.load(open("tool_catalog.json"))
BASE = catalog["backend"]

# 轉換成 OpenAI function schema
functions = [{
    "type": "function",
    "function": {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["input_schema"],
    }
} for t in catalog["tools"]]

# Tool name → REST endpoint mapping（參考本文件表格）
TOOL_TO_ENDPOINT = {
    "get_stock":           lambda a: ("GET", f"/stock/{a['stock_id']}", a),
    "get_stock_technical": lambda a: ("GET", f"/stock/{a['stock_id']}/technical", None),
    "market_summary":      lambda a: ("GET", "/market/summary", None),
    "run_screener":        lambda a: ("GET", "/screener", a),
    # ... 其餘 30 個
}

def dispatch(name, args):
    method, path, payload = TOOL_TO_ENDPOINT[name](args)
    if method == "GET":
        return requests.get(f"{BASE}{path}", params=payload).json()
    return requests.post(f"{BASE}{path}", json=payload).json()

resp = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "台積電最近技術面怎麼樣？"}],
    tools=functions,
)

for call in resp.choices[0].message.tool_calls or []:
    result = dispatch(call.function.name, json.loads(call.function.arguments))
    print(result)
```

### Anthropic Claude Tool Use

```python
import json, anthropic

catalog = json.load(open("tool_catalog.json"))

# Claude 的 tool 格式幾乎一樣，只要 rename
tools = [{
    "name": t["name"],
    "description": t["description"],
    "input_schema": t["input_schema"],
} for t in catalog["tools"]]

client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "台股今天怎麼樣？有沒有警報？"}],
)
# 處理 tool_use 後透過方案 B 的 REST API dispatch
```

### LangChain

```python
from langchain_core.tools import tool
import requests, json

catalog = json.load(open("tool_catalog.json"))
BASE = catalog["backend"]

# 批次生成 LangChain tools
tools = []
for t in catalog["tools"]:
    name = t["name"]
    def make_fn(n):
        def fn(**kwargs):
            # 你自己的 dispatch 邏輯（參考 OpenAI 範例）
            ...
        fn.__name__ = n
        fn.__doc__ = t["description"]
        return fn
    tools.append(tool(make_fn(name)))
```

---

## 方案 D — OpenClaw Python skill

### 舊版（非 MCP）OpenClaw 整合

同目錄下的 `taiwan_stock_skill.py` 是 OpenClaw 原生 Python skill 格式。設定方式：

1. 把 `taiwan_stock_skill.py` 複製到你的 OpenClaw `skills/` 目錄
2. 在 OpenClaw 的 `.env` 加：
   ```env
   STOCK_API_URL=https://taiwan-stock-api-production.up.railway.app
   # STOCK_API_KEY=（若啟用金鑰保護）
   ```
3. 重啟 OpenClaw

### Skill 結構（供你擴充）

`taiwan_stock_skill.py` 裡面的 `SKILL_CONFIG` 是標準 OpenClaw manifest 格式：

```python
SKILL_CONFIG = {
    "name": "taiwan-stock",
    "description": "台股戰情中心",
    "version": "1.0.0",
    "author": "imchris",
    "triggers": ["台股", "股票", "選股", "台積電", ...],
    "commands": {
        "市場總覽": {
            "patterns": ["台股怎麼樣", "大盤", "市場總覽"],
            "handler": market_summary,
        },
        "查詢個股": {
            "patterns": ["查 {stock_id}", "分析 {stock_id}"],
            "handler": stock_query,
        },
        # ... 自己擴充更多 commands
    },
}
```

要接更多功能（例如上面 34 個 tool 全部暴露給 OpenClaw），參考 `mcp_server.py` 裡的 tool 定義，把對應 REST 呼叫寫成 handler function 再加進 `commands` dict。

---

## 通用資訊

### 認證

目前**不需要金鑰**。所有 endpoint 都公開可讀。

如果未來啟用 `STOCK_API_KEY`，加入：
```http
Authorization: Bearer <token>
```

### 錯誤格式

FastAPI 標準錯誤：
```json
{ "detail": "找不到股票: XXXX" }
```

HTTP 狀態碼：
- `200` 成功
- `400` 請求參數錯誤
- `404` 找不到股票 / 資源
- `500` 後端內部錯誤
- `503` 上游資料源（FinLab / Goodinfo）不可用

### 超時建議

| 操作 | 建議 timeout |
|---|---|
| 一般查詢（market / stock / technical） | 10 秒 |
| 策略 / 篩選 | 30 秒 |
| AI 分析（ai_claude_analysis、ai_stock_chat） | 60 秒 |
| 回測（run_backtest） | 120 秒 |

### 資料來源

| 主要資料 | 來源 |
|---|---|
| 收盤價 / OHLCV / 基本面 | FinLab |
| 即時報價 | Yahoo Finance |
| 興櫃 / FinLab 沒有的股票 | Goodinfo |
| 大盤指數 fallback | TWSE 官方 |
| AI 分析 | Anthropic Claude API（後端配置） |

### 更新頻率

- 收盤數據：每日收盤後 1-2 小時
- 即時報價：5 秒快取
- 警報檢查：即時
- 策略選股：1 小時快取

### 架構圖

```
┌─────────────────────────────────────────────────────┐
│              你的 APP / AI 代理 / OpenClaw            │
└─────────────────────────────────────────────────────┘
        │                     │                │
        │ 方案 A              │ 方案 B         │ 方案 C
        │ stdio MCP           │ HTTPS          │ function
        │                     │                │  calling
        ▼                     │                ▼
┌─────────────────┐            │       ┌─────────────────┐
│  mcp_server.py  │            │       │ tool_catalog.   │
│  (this package) │            │       │      json       │
└─────────────────┘            │       └─────────────────┘
        │                     │                │
        │ HTTPS               │                │
        ▼                     ▼                ▼
┌─────────────────────────────────────────────────────┐
│    Railway FastAPI Backend (taiwan-stock-api)        │
│    https://taiwan-stock-api-production.up.railway.app│
│                                                      │
│    · 60+ endpoints                                   │
│    · OpenAPI 3 docs at /docs                         │
│    · Health check at /health                         │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ FinLab · Yahoo · Goodinfo · TWSE · Anthropic Claude │
└─────────────────────────────────────────────────────┘
```

### 聯絡 / 問題回報

- Repo: https://github.com/immlyou/taiwan-stock-monitor
- Backend health: https://taiwan-stock-api-production.up.railway.app/health
- Frontend UI: https://taiwan-stock-monitor.vercel.app

---

## 再生 tool_catalog.json

如果 `mcp_server.py` 新增了 tool，重新生成 catalog：

```bash
cd openclaw_skill
python mcp_server.py --dump-schema > tool_catalog.json
```

## 測試後端連線

```bash
cd openclaw_skill
python mcp_server.py --test
```

預期輸出：
```
✅ /health: ok | data_date=... | stocks=2721
✅ /market/summary: TAIEX=... up=... down=...
✅ /stock/2330: 台積電 $... (...%)
📦 MCP tools registered: 34
```
