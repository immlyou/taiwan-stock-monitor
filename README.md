# 台股戰情中心

以 FinLab API 為數據核心的台股研究平台，提供選股、回測、籌碼、財報、風險、投資組合與 AI 代理串接功能。

目前專案包含三個主要介面：

- **Next.js 前端**：正式 Web UI，部署在 Vercel
- **FastAPI API**：資料、策略與分析服務，部署在 Railway
- **Streamlit App**：舊版本機研究介面，仍保留可用

## 線上入口

| 服務 | 位址 |
|---|---|
| 前端 (Next.js on Vercel) | https://taiwan-stock-monitor.vercel.app |
| 功能總覽（App 內導覽頁） | https://taiwan-stock-monitor.vercel.app/overview |
| API Server (FastAPI on Railway) | https://taiwan-stock-api-production.up.railway.app |
| API 文件 (Swagger UI) | https://taiwan-stock-api-production.up.railway.app/docs |

## 功能特色

- 台股市場總覽、盤後總覽、熱力圖、資金流向與即時報價
- 個股技術面、籌碼面、財報與比較分析
- 選股篩選、策略管理、回測、參數優化與預測驗證
- 投資組合、交易日誌、自選股與警報設定
- 每日晨報、AI 智慧選股、AI 異常警報
- MCP / REST / Function Calling / Python wrapper 對外整合

近期新增：**AI 投資顧問**、**截圖匯入持股（Claude Vision）**、TanStack 資料表格、全域行情列、後端資料持久化等 —— 完整清單見 [`CHANGELOG.md`](./CHANGELOG.md)。

## 文件導覽

| 文件 | 內容 |
|---|---|
| [`CHANGELOG.md`](./CHANGELOG.md) | **功能總覽 / 近期變更紀錄**（建議從這裡開始） |
| App 內 `/overview` | 功能總覽頁（卡片式導覽；左側欄「✨ 功能總覽」捷徑） |
| [`frontend/ADOPTABLE_FEATURES.md`](./frontend/ADOPTABLE_FEATURES.md) | 前端設計系統建構塊 + 可採用功能盤點 |
| [`frontend/UI_AUDIT.md`](./frontend/UI_AUDIT.md) | 前端 UI/UX 審查清單 |
| [`docs/UI_OPTIMIZATION_PLAN.md`](./docs/UI_OPTIMIZATION_PLAN.md) | Streamlit 版面優化計畫 |
| [`docs/ROADMAP.md`](./docs/ROADMAP.md) | 產品 Roadmap |
| [`openclaw_skill/INTEGRATION.md`](./openclaw_skill/INTEGRATION.md) | AI / 第三方整合指南 |

## 專案結構

```text
taiwan-stock-monitor/
├── api/                    # FastAPI 模組化路由層
│   ├── routers/            # 路由模組（ai, alerts, market, stock …）
│   ├── deps.py             # 依賴注入
│   ├── helpers.py          # 工具函式
│   ├── models.py           # Pydantic 資料模型
│   └── state.py            # 應用程式狀態
├── api_server.py           # FastAPI app 入口
├── app/                    # Streamlit 舊版 UI
├── core/                   # 資料載入、策略、回測、風險、通知等核心邏輯
├── data/                   # JSON 狀態與輸出資料
├── frontend/               # Next.js 前端
├── openclaw_skill/         # MCP / OpenClaw / function calling 整合
├── scripts/                # 每日更新、通知、備份與部署腳本
└── tests/                  # Python 測試
```

## 環境變數

根目錄 `.env` 供 Python / API / Streamlit 使用：

```env
FINLAB_API_TOKEN=your_finlab_token
STOCK_API_KEY=optional_api_key
CORS_ORIGINS=http://localhost:3000,https://taiwan-stock-monitor.vercel.app
```

前端 `frontend/.env.local`：

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

生產環境在 Vercel 必須設定 `NEXT_PUBLIC_API_URL` 指向 Railway API。

## 本機開發

### 1. 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

若只跑 API，可使用較精簡的依賴：

```bash
pip install -r requirements-api.txt
```

### 2. 啟動 FastAPI

```bash
python api_server.py --host 0.0.0.0 --port 8000 --reload
```

API 文件：`http://localhost:8000/docs`

### 3. 啟動 Next.js 前端

```bash
cd frontend
npm install
npm run dev
```

前端網址：`http://localhost:3000`

瀏覽器端會透過 Next.js rewrite 將 `/api/*` 代理到 `NEXT_PUBLIC_API_URL`。

### 4. 啟動 Streamlit 舊版介面

```bash
streamlit run app/main.py
```

預設網址：`http://localhost:8501`

## 資料更新

首次使用或每日資料更新：

```bash
python scripts/daily_update.py
```

macOS launchd 自動更新：

```bash
./scripts/setup_launchd.sh
```

FinLab pickle 快取檔很大，預設不應提交到 Git。根目錄的 `*.pickle`、`*.pkl` 是本機資料快取。

## AI / 第三方整合

整合指南：[`openclaw_skill/INTEGRATION.md`](./openclaw_skill/INTEGRATION.md)

支援方式：

- MCP stdio：Claude Desktop / Claude Code / Cursor / OpenClaw MCP
- REST API：任何可發 HTTPS request 的系統
- Function Calling Catalog：OpenAI / Anthropic / Gemini tool use
- Python skill wrapper：OpenClaw 舊版

工具清單：

- [`openclaw_skill/tool_catalog.json`](./openclaw_skill/tool_catalog.json)
- [`frontend/public/tool_catalog.json`](./frontend/public/tool_catalog.json)

目前工具目錄包含 35 個 tools。

## 產品 Roadmap

後續智能分析功能開發順序見 [`docs/ROADMAP.md`](./docs/ROADMAP.md)。

## 測試與檢查

後端測試：

```bash
pytest
```

前端 lint：

```bash
cd frontend
npm run lint
```

## 部署

- API：Railway，設定見 [`railway.toml`](./railway.toml)、[`Procfile`](./Procfile)
- 前端：Vercel，設定見 [`frontend/vercel.json`](./frontend/vercel.json)、[`.vercelignore`](./.vercelignore)

Vercel 部署只需要 `frontend/` 及必要設定；後端、測試、資料快取與本機工具狀態已由 `.vercelignore` 排除。

## 授權

僅供個人學習研究使用，不提供投資建議或自動交易功能。
