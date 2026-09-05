# 功能總覽 / CHANGELOG

台股戰情中心 —— 近期交付的新功能與重大改動總整理。
架構：**Next.js 前端**（Vercel，使用者產品）+ **Streamlit `app/`**（Railway）+ **FastAPI 後端 `api/`**（Railway，FinLab 雲端模式）。

---

## 🆕 2026-09

### v5.2.1 — 功能流程與可靠性修正（2026-09-05）

- 修正預測 CRUD 契約與帳號隔離；排程依截止日前的完整收盤價驗證，統一舊資料狀態。
- 舊版全域策略追蹤改存 `strategy_predictions.json`，首次載入複製可辨識的舊紀錄，保留原檔，避免覆寫使用者預測。
- Alerts 命中歷史與每頻道送達狀態分離；預覽不消耗通知資格，失敗採 1–15 分鐘退避，成功頻道不隨失敗頻道重送。
- 行情更新間隔接入五個頁面；尚未實作的排程設定停用並由 API 拒絕無效設定。
- Dashboard 投組錯誤不再隱藏其他 widgets。
- 加入真實 Next.js proxy / FastAPI 契約 E2E 與 blocking CI job。

## 🆕 2026-08

### v5.2.0 — 功能一致性與架構收斂（2026-08-28）
- Portfolio、持倉總覽與新增／編輯流程統一以「股」為單位，避免股／張混用造成部位放大或縮小 1,000 倍。
- Alerts 評估加入帳號級 single-flight，完成後只合併評估時間戳與新 hits，不再覆蓋同時發生的規則編輯或刪除。
- 自訂 Dashboard 五種 widget 全面接上實際資料與載入／錯誤／空狀態，並可啟用、停用及排序保存。
- XGBoost 改為 canonical top-50 單一訓練快取；不同 `top_n` 請求只切片結果，不再各自訓練。
- 側欄與功能總覽改用單一導航 catalog，統一功能分類、命名與 active route 規則。
- 新增根目錄 release manifest，前端與 API build 讀取同一版本來源，設定頁分別顯示實際前端與 API 版本。
- 補齊投組單位、Alerts 併發、Dashboard renderer、XGBoost canonical cache、導航與版本契約測試。

### v5.1.1 — XGBoost 韌性（2026-08-26）
- 前端 XGBoost 總運算時限調整為 45 秒，`/strategy/ai-*` 代理層上游預算調整為 65 秒；取消會把等待時間放大成 90 秒的隱性自動 retry。
- 服務啟動時背景預熱 XGBoost top-20，APScheduler 每 45 分鐘強制更新，早於一小時 cache TTL。
- 同一服務進程、同一 cache key 加入 single-flight，並行 cold miss 只訓練一次。
- 錯誤區分為運算逾時、暫時不可用、依賴缺失；失敗時保留帳號快取舊結果，顯示重試中狀態並提供手動重試。
- 新增 timeout、single-flight、預熱、排程與登入後 stale-result E2E 契約。

### v5.1.0 — 即時行情（2026-08-24）
- Fugle / TWSE 即時報價優先，FinLab 收盤資料 fallback。
- 即時報價頁、Portfolio、Watchlist、個股頁全面接入即時優先報價，並標示來源、盤中狀態、freshness 與報價時間。
- 批次報價允許單一 provider 失敗後降級，補齊 provider、API、前端與登入後 E2E 測試。

### v5.0.1 — 登入後流程強化（2026-08-24）
- 修正 API 阻塞、重複 timeout 與 retry storm；新帳號可直接完成 default Portfolio / Watchlist 首次建立。
- SWR localStorage cache 依 Google user id 分帳號保存；各核心頁補齊錯誤、保留舊資料與重新載入狀態。
- settings / notification 秘密遮罩與前後端契約補強，登入後核心功能 Playwright E2E 改為 blocking CI。

### v5.0.0 — Google OAuth 與帳號隔離（2026-08-23）
- 登入改用 Google OAuth 與 owner allowlist，頁面、Next.js proxy、FastAPI 三層共同驗證身分。
- Portfolio、Watchlist、Alerts、Journal、Settings、Predictions、Saved Strategies 與通知狀態全面依帳號隔離。
- Telegram token、SMTP 密碼等只回傳 configured 狀態與遮罩；proxy 僅轉送伺服器驗證的 user id。
- Alerts 2.0 加入規則評估、PATCH、通知節流與多帳號排程；Portfolio 加入 what-if／持股診斷工具。

---

## 🆕 2026-07（含 6/26 hotfix）

### v4.1.0 — API 可靠性與效能（2026-07-16）
- SafeJSONResponse 遞迴清理 NaN / Infinity，市場摘要缺資料安全降級，`/ready` 改為非阻塞。
- DataLoader 加入 per-key download lock；市場 `loader.get` 移至 executor，避免重複下載及 event loop 阻塞。
- 加權指數改取 TWSE 官方價格指數收盤值，補強 FinLab 熔斷器與 API contract 測試。

### v4.0.1 — 大盤資料一致性（2026-06-26）
- 全站統一使用加權股價指數，不再誤用發行量加權報酬指數。
- 盤後總覽、大盤 ticker、摘要與三大法人欄位統一來源、漲跌算法及單位。

---

## 🆕 2026-06

### 後端 / FinLab 額度與快取
- **FinLab 配額熔斷器**（`core/data_loader.py`）：偵測到當日額度超限後，`_load_from_finlab` 直接短路拒絕呼叫，不再送出注定失敗的請求；台灣午夜跨日後自動歸零用量並恢復（額度每日重置）。
- **FinLab 資料 Volume 持久化快取**：雲端模式下載的資料集落地到 `data/finlab_cache/<key>.pkl`（Railway 持久 Volume）。`get()` 查找順序 記憶體 → 磁碟（夠新免打 FinLab）→ 下載。**重啟不再重燒額度**。額度超限時改供應磁碟舊快取（stale fallback）而非整個失敗。`/refresh` 與 `reset_all_caches()` 會一併失效磁碟層以強制重新下載。

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
