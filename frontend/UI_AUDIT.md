# 前端 UI/UX 優化清單（證據導向）

> 來源：6 群組 24 頁唯讀審查綜整。原則：**避免 churn** — 只列真正值得改、能集中收斂、低風險的項目。所有路由相對於 `src/app/`。

---

## 1. 執行摘要

### 跨頁最常見的問題類型（按頻次與影響排序）

| # | 問題類型 | 出現頁數 | 根因 | 收斂策略 |
|---|----------|---------|------|----------|
| **1** | **硬編 hex 色彩繞過設計 token** | 12+ 頁 | KpiCard accentColor、圖表 stroke/fill、評級/分數/嚴重度色彩直接寫 `#xxxxxx`，未用 `var(--stock-up/down)`、`var(--flow-*)`、`var(--primary)` | 集中到 token 表；圖表色抽到 `lib/constants/chartColors.ts` |
| **2** | **inline `.toFixed()` 取代 format.ts 工具** | 10+ 頁 | `formatPrice/formatPercent/formatChange` 已存在且大多已 import，但表格/圖表處仍直接 `.toFixed()`，格式漂移 | 全域改用 format.ts；不要為此重寫工具函數 |
| **3** | **手刻 `<table>` 缺排序/篩選/匯出** | 8+ 頁 | TanStack Table 已安裝（package.json）但未用；長列表無分頁/虛擬化、行動版只能水平捲動 | 抽共用 `<DataTable>`，逐頁導入；非全部都需要 |
| **4** | **手刻原生元件取代 shadcn** | 多頁 | `<button>`/`<input>`/toggle/Dialog/Badge 手刻，缺鍵盤導航、focus trap、ARIA | 優先換 Switch、Dialog（a11y 影響最大），Badge/Button 次之 |
| **5** | **漲跌缺雙重編碼（色+符號）** | 多頁 | 僅用紅綠色編碼，無 ▲▼ 箭頭，對色盲不友善 | 由 `formatChange` 統一補符號，一處改全站受益 |

### 整體一致性評分

| 維度 | 評分 | 說明 |
|------|------|------|
| 設計基礎建設（token、format.ts、KpiCard、EmptyState、Sparkline） | **A** | 工具完備、設計精良，這是最大資產 |
| 工具採用率（是否真的用了現有工具） | **C+** | 工具齊全但各頁採用不一，這是主要債務來源 |
| 表格/資料層成熟度 | **C** | 大量手刻 table，TanStack 已裝未用 |
| 無障礙（a11y） | **C** | 手刻 toggle/Dialog/進度條缺 ARIA |
| 響應式 | **B-** | grid 基礎佳，但多欄表格行動版無欄優先級 |

**核心判讀**：這不是設計系統缺失的問題，而是**「好工具未被一致採用」**的收斂問題。最高 ROI 的修正是「把硬編色彩與 inline toFixed 換成既有工具」——低風險、跨頁一致、零新增依賴。

---

## 2. 高價值修正清單（P1）

> 篩選標準：高/中 severity + 低風險 + 對一致性或 a11y 有實質影響。優先做能**集中收斂**的。

| 路由 | 問題 | 建議 | severity | effort |
|------|------|------|----------|--------|
| `lib/utils/format.ts` + 全站 | `formatChange/formatPercent` 缺方向符號，漲跌僅色彩單編碼 | 在 `formatChange` 加 ▲▼ 符號（或加可選 `withArrow` 參數），一處改全站受益（dashboard/realtime/compare/watchlist 等同步消除單編碼問題） | medium | S |
| `(research)/chip/page.tsx` | 三大法人色硬編 `#3b82f6/#8b5cf6/#f59e0b`，但 `--flow-foreign/trust/dealer` 已定義 | kpiItems 與 BarChart Bar 改用 `var(--flow-*)`。**最快可修**，token 已存在 | high | S |
| `(research)/risk/page.tsx` | KpiCard accentColor 混用 token 與硬編（`var(--destructive)` vs `#dc2626` vs `#f97316`） | 全改 token：`var(--stock-down)`/`var(--flow-trust)`/`var(--flow-dealer)`/`var(--primary)` | high | S |
| `(research)/financials/page.tsx` | 圖表線色硬編 `#22c55e/#3b82f6/#f59e0b/#8b5cf6`；本地重複 `formatDate/formatRevenue` | 線色改 token；刪本地格式函數改用 `format.ts` 的 `formatCurrency/formatDate` | high | S |
| `(market)/heatmap/page.tsx` | 全頁硬編 hex（`getHeatColor`/`getTextColor` + `#fff/#444/#1e1e2e`），繞過 token cascade | 抽 `--heat-*` 漸層 token 或由 `--stock-up/down` 衍生；文字/背景改 `var(--foreground/card/background)`；legend 由 threshold 常數派生避免手動同步 | high | M |
| `(research)/stock/[id]/page.tsx` | 多處硬編 hex（KpiCard accentColor `#8b5cf6/#f59e0b`、`getRatingColor` 5 色）+ 大量 inline `.toFixed()`（13+ 處） | accentColor 改 token；評級色納入 `--rating-*` token 或復用 `getChangeColorVar`；toFixed 全改 `formatPrice/formatPercent` | high | M |
| `(research)/technical/page.tsx` | 指標線色硬編 `#3b82f6/#f59e0b/#8b5cf6/#10b981`，無一致視覺階層 | 抽 `lib/constants/chartColors.ts`（`--indicator-ma5/ma20/ma60/rsi`），改 `var()` | high | M |
| `(strategy)/ai-pick/page.tsx` | `RECOMMENDATION_CONFIG/RISK_CONFIG/DIRECTION_CONFIG` 硬編 hex | 改用 token；需透明度變體時在 globals.css 加 `--stock-up-bg/--stock-down-bg`，勿 inline 拼湊 | high | M |
| `(strategy)/screener/page.tsx` | 表格數值全 inline `.toFixed()`（PE/PB/殖利率/YoY/評分） | 改 `formatPrice/formatPercent/formatChange`，集中格式化邏輯 | high | M |
| `(strategy)/ai-anomaly/page.tsx` | 本地重複定義 `KpiCard` 子元件（行 48-69），與共用元件分裂 | 刪本地定義，改 `import { KpiCard } from '@/components/shared/KpiCard'` | high | S |
| `(strategy)/trading-radar/page.tsx` | 4 個 KPI + StockCard 全手刻，未用 KpiCard；多處 inline toFixed | KPI 區改 KpiCard 陣列；數值改 format.ts | high | M |
| `(strategy)/predictions/page.tsx` | 統計卡片手刻 + 動態色邏輯混在頁面層；**useSWR 缺 error 狀態**（API 失敗無法區分載入中 vs 失敗） | 改 KpiCard 陣列；補 `error` 解構並條件渲染錯誤提示（參考 optimizer 模式） | high | M |
| `(market)/morning-report/page.tsx` | AI 情緒色彩三元判式重複（行 380-386、424-429） | 改調用 `getChangeColorVar(aiAvgScore)` / `getChangeColorVar(result.score ?? 0)`，<5 行改動 | high | S |
| `settings/page.tsx` | Telegram/Email/系統參數開關全手刻 button+span，無 focus ring / 鍵盤導航 | 全改 shadcn `Switch`，自動處理 ARIA `role=switch`/`aria-checked`、WCAG AA 對比 | medium | S |
| `(portfolio)/alerts/page.tsx` | 警報開關手刻 toggle，無 ARIA | 改 shadcn `Switch` | medium | S |
| `(portfolio)/portfolio/page.tsx` | 新增/編輯/刪除 Dialog 用 `position:fixed`+inline 手刻，無 `aria-modal`/focus trap/ESC | 改 shadcn `Dialog`（已安裝），自動處理 a11y + scrim | medium | M |
| `(market)/realtime/page.tsx` | 現價欄與漲跌幅欄同用 `getChangeColorVar` 著色，視覺噪音；現價應中立 | 現價改 `var(--foreground)`，僅漲跌幅保留色編碼 | medium | S |
| `(market)/dashboard/page.tsx` | 表格混用 `.toFixed(2)` 與 `formatCurrency`（行 303 vs 317），格式碎裂 | 統一改 `formatPrice/formatCurrency` | low | S |

---

## 3. 次要 / 選配（P2）

> 多為「missing-feature」「進階互動」「圖表增強」，價值真實但非當務之急；建議排入 v2，避免現階段 churn。

| 路由 | 問題 | severity | effort |
|------|------|----------|--------|
| `(market)/dashboard`、`screener`、`predictions` 等多頁 | 多欄表格行動版無欄優先級（responsive column hiding），只能水平捲動 | medium | M |
| `(market)/dashboard`、`(research)/chip`、多列表頁 | 手刻 table 改 TanStack Table（排序/篩選/分頁/匯出 CSV） | medium | M |
| `(market)/realtime` | 報價表缺成交量/成交金額欄（需後端支援） | medium | M |
| `(market)/morning-report` | 新聞清單缺摘要/情緒標籤；缺日期篩選歷史查閱 | low-med | M-L |
| `(market)/heatmap` | grid 格子缺 ▲▼ 雙重編碼；行動版 minmax 過寬可能溢出 | medium | M |
| `(market)/after-hours` | AI 摘要生成缺進度指示；AiPickList top-3 缺視覺強調（🥇🥈🥉） | medium | M |
| `(research)/compare`、`industry`、`risk` | 手刻 `<button>`/`<input>`/Tabs 改 shadcn；表格改 shadcn Table | low-med | S-M |
| `(research)/stock/[id]` | AI 問答區缺 `role=log`/`aria-live`、input 無 label、送出按鈕無 aria-label | medium | S |
| `(strategy)/optimizer`、`hidden-gems` | 進度條缺 `role=progressbar`/`aria-value*` | medium | S-M |
| `(strategy)/backtest`、`optimizer` | 績效/基準指標手刻卡片改 KpiCard；圖表匯出/放大功能 | low-med | S-M |
| `(strategy)` 多頁 | 表格欄頭缺 tooltip 說明；匯出 CSV/Excel | low | M |
| `(portfolio)/journal` | 手刻 `renderMarkdown` 脆弱，改 react-markdown | medium | M |
| `(portfolio)/watchlist` | 卡片可改 KpiCard 風格 + sparkline；name 欄位 undefined | low | S |
| `(portfolio)` 列表頁 | 缺 filter chips（虧損/獲利、買入/賣出、日期範圍） | low | M |
| `settings` | Telegram 測試改 Toast/Sonner 提示；Changelog timeline 色硬編改 token | low-med | S-M |
| 全站 sparkline 機會 | dashboard 持股、stock KPI、compare 表格可加 Sparkline（元件已備） | low | M |
| 各頁 skeleton 細節 | dashboard 骨架欄寬死值、morning-report 骨架寬度規律不自然 | low | S |

---

## 4. 「已經做得好，不要動」清單（勿 churn）

後續執行者請**保留**以下既有實作，不要在重構時順手改壞：

### 設計基礎建設（核心資產，勿動）
- **KpiCard 元件**：設計完整，支援 `sparkline`、`isLoading`、`accentColor`、`change`，架構良好。重構時是「改用它」，不是改它。
- **format.ts 工具庫**：`formatPrice/formatPercent/formatChange/formatCurrency/formatShares/getChangeColorVar` 完備。**唯一允許動 format.ts 的理由是加方向符號（P1 第一項）**。
- **EmptyState / Skeleton / Sparkline 共用元件**：可用且設計良好，目標是提高採用率而非改寫。
- **globals.css 設計 token**：`--stock-up/down/flat`、`--flow-foreign/trust/dealer`、`--primary/secondary`、`--header-height`、`@theme` 配置、響應式 media query 基礎完整。新增 token 用追加方式，勿改既有語義。

### 各頁已正確的實作（保留）
- **money-flow**：正確用 KpiCard（行 146-171）+ `formatShares()`，是好範本。
- **after-hours**：多區塊 h2 標題 + KpiCard grid + shadcn Tabs + 三狀態（button/loading/result）處理完善，**是全站最佳實踐範本**。
- **risk**：8 個風險指標已用 KpiCard（含 isLoading）；表格已用 `tabular-nums`。
- **compare**：圖表已用 `var(--border)`/Tooltip token；已正確檢查 `selectedCodes.length >= 2` 才啟用比較。
- **industry**：Bar 圖表已用 `var(--stock-up/down)` token。
- **portfolio**：多數 KPI 已改 KpiCard（行 182-203）；漲跌色已用 `getChangeColorVar`（行 290/296）；三狀態邏輯完整。
- **backtest / optimizer / hidden-gems**：loading/error/empty 三狀態已正確（useSWR + 條件渲染）；optimizer 已正確整合 StockInput。
- **StockInput 元件**：完整 ARIA combobox、鍵盤導航、防抖、聚焦外關閉。三研究頁與 optimizer 已正確使用，**勿重寫**。
- **predictions / strategies**：Dialog CRUD 流程清晰、表單驗證到位（predictions 僅需補 error 狀態，勿動其餘）。
- **ai-anomaly**：空/載入/錯誤三狀態用 EmptyState + spinner + error 提示完善（僅需換掉本地 KpiCard 定義）。
- **ai-pick**：LSTM 趨勢預測卡片視覺層次分明、方向符號顯眼。
- **hidden-gems**：分數進度條與排名徽章設計精美，已超出基準（僅補 a11y 即可）。
- SWR 資料層、條件式載入（如 stock/[id] 的 `tab === 'chart'` 才載 ohlcv）效率佳，**勿動資料層架構**。

---

## 5. 建議修正批次（PR 分組）

### PR-1：色彩 token 收斂（純樣式，低風險，最高 ROI）
**一個 PR 集中改**，因為改動同質、互不衝突、可一次 review：
- `chip`（flow token，最快）、`risk`、`financials`、`stock/[id]`、`ai-pick`、`backtest`、`hidden-gems`、`portfolio`、`settings`、`morning-report` 的硬編 hex → token
- 圖表線色抽 `lib/constants/chartColors.ts`（`technical`、`financials`、`compare`、`heatmap`）
- 需要時在 globals.css **追加** `--rating-*`、`--score-*`、`--severity-*-bg`、`--stock-up-bg/down-bg`、`--heat-*` token
- ⚠️ heatmap 改動較大可獨立成 **PR-1b**（含 legend 由 threshold 派生）

### PR-2：格式化收斂（純邏輯，低風險）
- `formatChange` 加方向符號（▲▼）→ 連帶消除多頁「漲跌單編碼」問題
- 全站 inline `.toFixed()` → `formatPrice/formatPercent/formatChange`（`screener`、`trading-radar`、`stock/[id]`、`dashboard`、`heatmap` 等）
- 刪 `financials` 本地 `formatDate/formatRevenue`
- ⚠️ 改 `formatChange` 後需全站視覺回歸檢查（符號是否破壞既有對齊/寬度）

### PR-3：KpiCard 採用統一
- `ai-anomaly` 刪本地 KpiCard 定義
- `trading-radar`、`predictions`、`screener`、`backtest`、`optimizer`、`alerts`、`industry` 手刻卡片 → KpiCard
- 與 PR-1 有色彩重疊，建議 **PR-1 先合**再做此批，避免衝突

### PR-4：無障礙 + shadcn 元件（a11y 影響，需互動測試）
- 開關類：`settings`、`alerts` 的 toggle → shadcn `Switch`
- Dialog 類：`portfolio` 手刻 Dialog → shadcn `Dialog`
- 進度條：`optimizer`、`hidden-gems` 補 `role=progressbar`/`aria-*`
- `stock/[id]` AI 問答區 ARIA
- 此批**獨立**，因涉及鍵盤/焦點行為，需單獨手動驗證

### PR-5（v2，獨立）：表格升級
- 抽共用 `<DataTable>`（TanStack Table）→ 逐頁導入排序/篩選/分頁/匯出/響應式欄優先級
- `predictions` 補 error 狀態可**先單獨小 PR**（與 PR-3 一起亦可）
- ⚠️ 影響最大、風險最高，**勿與其他批次混做**

**批次依賴順序建議**：PR-2 → PR-1 → PR-3 →（並行）PR-4 → PR-5。先收斂格式與色彩這兩個跨頁同質債務，後續 KpiCard/表格重構衝突最小。
