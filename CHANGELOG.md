# 功能總覽 / CHANGELOG

台股戰情中心 —— 近期交付的新功能與重大改動總整理。
架構：**Next.js 前端**（Vercel，使用者產品）+ **Streamlit `app/`**（Railway）+ **FastAPI 後端 `api/`**（Railway，FinLab 雲端模式）。

---

## 🆕 2026-06

### 後端 / 自動化
- **背景排程器**（`core/scheduler.py`，APScheduler）：API 進程內定時任務，平日 09:00–13:30（台北時區）**自動檢查警報並送通知**，不再只能手動 POST `/alerts/check` 或靠外部 cron。環境開關 `ENABLE_SCHEDULER`（雲端預設開、本地預設關）、`ALERT_CHECK_INTERVAL_MIN`（預設 5 分）。狀態見 `GET /health` 的 `scheduler` 欄位。單一 uvicorn worker 不會重複排程；`max_instances=1`+`coalesce` 防重疊。
- **通知節流**（`core/notification.py` `NotificationThrottle`）：同一警報在冷卻期內只送一次（`ALERT_NOTIFY_COOLDOWN_SEC`，預設 1 小時），是自動排程的安全閥，避免盤中反覆檢查造成 alert fatigue。狀態持久化於 `data/notify_throttle.json`（Railway Volume，跨 redeploy 保留）。`NotificationManager.send()` 新增 `dedup_key`/`cooldown_sec` 參數，可供其他通知重用。

---

## 🆕 2026-05（本批次）

### AI 與智慧分析
- **AI 投資顧問**（`/advisor`）：資深操盤人風格引導式精靈 —— 持股健檢（量化評分卡）→ 資金配置/再平衡建議 → 達標可行性評估 → Claude 專業敘述 → 一鍵套用到投組。後端 `POST /advisor/analyze`（量化 + Claude）。
- **截圖匯入持股**（Claude Vision）：上傳券商持股截圖 → AI 自動辨識 → 多張合併 → 可編輯表格。共用元件 `ScreenshotImportDialog`，已接入：
  - `advisor`（辨識→編輯→存成投組 profile→分析）
  - `portfolio`（合併持股進投組）
  - `watchlist`（代號加入自選）
  - `stock/[id]`（辨識個股→跳轉分析）
  - 後端 `POST /advisor/extract-holdings`（不耗 FinLab 額度）。
- AI XGBoost 選股修復（pandas 2.2+ `fillna(method=)` 相容）。

### 前端 UI / 設計系統（Next.js）
- **全域行情列 MarketTicker**：每頁頂部顯示加權指數＋漲跌（▲▼）＋漲/平/跌家數＋盤中/盤後。
- **TanStack DataTable**：共用表格元件（排序/搜尋/分頁/CSV 匯出），導入 screener / predictions / chip / dashboard。
- **設計系統收斂**：色彩 token（`chartColors`）、`format.ts`（含 ▲▼ 雙重編碼）、KpiCard 全站採用、Sparkline 走勢。
- **無障礙(a11y)**：shadcn Switch / Dialog、progressbar / chat ARIA。
- **持久 watchlist 側欄快捷**、命令列股票搜尋。
- 各頁採用：dashboard 持股走勢 Sparkline、realtime 成交量/成交金額、morning-report 新聞情緒標籤、journal react-markdown 報告、filter chips 等。
- 詳見 `frontend/ADOPTABLE_FEATURES.md`（設計系統建構塊 + 可採用功能）、`frontend/UI_AUDIT.md`。

### Streamlit `app/` UI
- P0 設計系統（theme/charts/元件 token 化、響應式）+ P1/P2 全 26 頁版面優化。詳見 `docs/UI_OPTIMIZATION_PLAN.md`。

### 後端 / 基礎設施
- **API 架構重構**：`api_server.py` 拆分為 `api/routers/*`（20+ router）+ 合約/E2E 測試。
- **資料持久化**：Railway Volume 掛載 `/app/data` —— 投組/自選/日誌等使用者資料跨 redeploy 不再消失。
- 雲端 FinLab 模式修復：scorecard/score-upgrades 欄位去重 + `reindex` 防呆；非阻塞背景預熱 + 輕量 healthcheck。
- 端點 `/portfolios` 持股新增 `price_history`、`/quote/realtime` 新增 `amount`。

---

## 部署
- **前端**：Vercel production（`main` 分支自動部署）。
- **後端**：Railway（`railway up` CLI 上傳部署；GitHub auto-deploy 不可靠）。
- ⚠️ FinLab 每日額度 5000MB，密集查詢全市場運算端點（scorecard/advisor）可能用爆，台灣午夜重置。

> 文件索引：`frontend/ADOPTABLE_FEATURES.md`、`frontend/UI_AUDIT.md`、`docs/UI_OPTIMIZATION_PLAN.md`。
