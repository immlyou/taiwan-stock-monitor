# Taiwan Stock Monitor — Integration Examples

可直接執行的範例程式，展示如何用不同方式呼叫 taiwan-stock-monitor API。

## 檔案清單

| 檔案 | 用途 | 依賴 |
|---|---|---|
| `rest_api_direct.py` | 最簡單：直接 HTTPS 呼叫 REST API | `requests` |
| `mcp_client.py` | 用 Python MCP client 連接 MCP server | `mcp`, `httpx` |
| `openai_function_calling.py` | OpenAI GPT-4/5 function calling | `openai`, `requests` |
| `anthropic_tool_use.py` | Anthropic Claude tool use | `anthropic`, `requests` |
| `langchain_agent.py` | LangChain agent 包裝 | `langchain-core`, `langchain-openai`, `requests` |

## 快速跑起來

### 1. 最快驗證（無 LLM，純 REST）

```bash
pip install requests
python rest_api_direct.py
```

預期輸出：TAIEX 指數、台積電技術面、篩選結果。

### 2. 跑 MCP client（驗證 MCP 連線）

```bash
pip install mcp httpx
python mcp_client.py
```

### 3. 跑 OpenAI function calling

```bash
pip install openai requests
export OPENAI_API_KEY=sk-...
python openai_function_calling.py
```

### 4. 跑 Anthropic Claude tool use

```bash
pip install anthropic requests
export ANTHROPIC_API_KEY=sk-ant-...
python anthropic_tool_use.py
```

### 5. 跑 LangChain agent

```bash
pip install langchain-core langchain-openai requests
export OPENAI_API_KEY=sk-...
python langchain_agent.py
```

## 共用設定

所有範例都從這個 URL 讀取資料：
```
https://taiwan-stock-api-production.up.railway.app
```

可用環境變數覆蓋：
```bash
export STOCK_API_URL=https://your-custom-backend.com
export STOCK_API_KEY=your-bearer-token   # 目前後端未啟用
```

## 不用 Python？

參考上層的 [`INTEGRATION.md`](../INTEGRATION.md)，有 curl / Node.js 範例。
