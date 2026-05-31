# 可採用功能盤點與逐頁實作計畫

> 承接 `UI_AUDIT.md`（§3 P2/選配、§4 已良好清單）與 `docs/UI_OPTIMIZATION_PLAN.md`（§4 市面範式）。
> 原則：只列「現在可採用、低/中風險、用既有套件/元件、自包含、不需後端改動、不需新依賴」者進入 auto_implement。
> 高風險/需依賴/需後端欄位者進 deferred。所有路由相對 `src/app/`。

已安裝可用：`@tanstack/react-table`、`recharts`、`lightweight-charts`、`react-hook-form`、`zod`、`zustand`、`swr`、`lucide-react`、`react-markdown` + `remark-gfm`。
既有共用：`shared/{KpiCard(支援 sparkline),Sparkline,EmptyState,StockInput,StockSearch,DataTable,ScreenshotImportDialog}`、`ui/{table,tabs,dialog,switch,tooltip,...}`、`layout/MarketTicker`、`lib/utils/format.ts`（含 `changeArrow`、`formatPercent(withArrow)`、`formatChange(withArrow)`）、`lib/constants/chartColors.ts`（`CHART_SERIES`、`FLOW`、`ratingColor`）。

---

## 0. 設計系統建構塊 / 已實作能力（更新 2026-05-31）

> 本區為「現成可複用」的共用元件與能力，新頁面優先複用，不要重造輪子。

| 建構塊 | 位置 | 用途 / API 摘要 |
|--------|------|------------------|
| **MarketTicker** | `layout/MarketTicker` | 全域行情列（已掛 Header，全頁顯示，勿重做） |
| **KpiCard** | `shared/KpiCard` | 標準 KPI 卡，支援 `sparkline?: number[]`、`change`、`accentColor`、`isLoading` |
| **Sparkline** | `shared/Sparkline` | `<Sparkline data={number[]} autoColor />` 迷你走勢（紅漲綠跌） |
| **DataTable** | `shared/DataTable` | TanStack 表格：排序/搜尋/分頁/CSV 匯出；`columns: ColumnDef[]`、`data`、`searchable`、`exportable`、`exportFilename`、`pageSize`。已用於 screener/predictions/chip/dashboard |
| **ScreenshotImportDialog** ⭐ | `shared/ScreenshotImportDialog` | **截圖匯入持股**（見下）。已用於 advisor/portfolio/watchlist/stock |
| **format.ts / chartColors.ts** | `lib/...` | 數值格式（含 ▲▼ 雙重編碼）、設計色彩 token；數字/漲跌色一律走這裡 |
| AI 投資顧問 | `(portfolio)/advisor` + 後端 `/advisor/*` | 量化健檢＋配置建議＋可行性＋Claude 敘述＋一鍵套用 |

### ⭐ 截圖匯入能力（ScreenshotImportDialog）

**後端**：`POST /advisor/extract-holdings` — Claude Vision 解析持股截圖（base64）→ `{holdings:[{stock_id,name,shares,cost_price}]}`。**不碰 FinLab**（額度爆也可用）。

**前端共用元件** `shared/ScreenshotImportDialog`：
```tsx
import { ScreenshotImportDialog, type ImportedHolding } from '@/components/shared/ScreenshotImportDialog'
<ScreenshotImportDialog
  open onClose
  mode="holdings" | "codes"          // holdings=可編輯股數/成本表格；codes=代號 chips
  title="📷 截圖匯入"
  onConfirm={(items: ImportedHolding[]) => {...}}  // 批次匯入（投組/自選股）
  confirmLabel="加入投組"
  onPickOne={(stockId) => router.push(`/stock/${stockId}`)}  // 單選跳轉（個股分析）
/>
```
元件自行處理：多張上傳 → 逐張 Vision 辨識 → 同代號合併股數 → 編輯/移除 → 回傳。

**已接入頁面**：
- `(portfolio)/advisor`：上傳→編輯→存成投組(profile)→分析/套用
- `(portfolio)/portfolio`：📷 合併持股進目前投組（PUT）
- `(portfolio)/watchlist`：📷 代號去重加入自選（PUT）
- `(research)/stock/[id]`：📷 辨識個股→跳轉分析（`onPickOne`）

**未來可接**：交易日誌（從成交截圖建立紀錄）、回測/選股（截圖匯入候選清單）。複用同元件即可，後端零改動。

---

## A. adoptable_features（可採用功能盤點）

### auto_implement = true（自包含、零新依賴、無需後端）

| # | 功能 | value | effort | risk | target pages | 說明 |
|---|------|-------|--------|------|--------------|------|
| 1 | compare 圖表/標籤色硬編 hex → `chartColors.CHART_SERIES` | high | S | low | (research)/compare | `COLORS=['#3b82f6',...]` 改用既有 `CHART_SERIES`，line stroke/標籤/表格代號色一併收斂 |
| 2 | compare 表格 inline `.toFixed()` → format.ts | high | S | low | (research)/compare | `base_price/latest_price` 用 `formatPrice`；`total_return_pct` 用 `formatPercent(v,2,true)`（帶 ▲▼） |
| 3 | compare 指標表加 Sparkline（資料已在 `s.data[].normalized`） | medium | S | low | (research)/compare | 每列加 `<Sparkline data={s.data.map(d=>d.normalized)} autoColor />`，零後端需求 |
| 4 | heatmap 個股格 change_pct 加 ▲▼ 雙重編碼 | medium | S | low | (market)/heatmap | cell 與 tooltip 的 `formatPercent` 改 `formatPercent(v,2,true)`；industry 卡已有 ▲n▼n，補齊個股層 |
| 5 | after-hours AiPickList top-3 加 🥇🥈🥉 | medium | S | low | (market)/after-hours | 前 3 名序號徽章改獎牌，其餘維持數字；StockRankTable 同步前 3 名強調 |
| 6 | after-hours AI 摘要進度指示強化 | low | S | low | (market)/after-hours | 已有 skeleton；按鈕 disabled 文案/`aria-busy` 補強，無需新元件 |
| 7 | journal 操作類型 filter chips（買入/賣出/加碼/減碼/全部） | medium | S | low | (portfolio)/journal | 純前端 `useState` 過濾 `data.entries`，chips 用既有 token 樣式 |
| 8 | journal 表格 inline `.toFixed()` → format.ts | medium | S | low | (portfolio)/journal | `e.price.toFixed(2)`→`formatPrice`；金額 `/1e4` 改 `formatCurrency(amount,{compact:true})` |
| 9 | 持股表頭 tooltip 說明（shadcn Tooltip 已裝） | medium | S | low | (market)/dashboard | 損益(%)/市值/成本價等表頭包 `Tooltip`，補欄位定義；TooltipProvider 包表格 |
| 10 | dashboard 骨架寬度自然化 | low | S | low | (market)/dashboard | `PositionRowSkeleton` 固定 `w-16` 改各欄不同寬度（如 `w-12/w-20/w-24`）模擬真實內容 |
| 11 | watchlist change_pct 加 ▲▼ 雙重編碼 | low | S | low | (portfolio)/watchlist | `formatPercent(v,2,true)`，色盲友善，零依賴 |
| 12 | predictions 漲跌/方向數值 ▲▼ 雙重編碼 | low | S | low | (strategy)/predictions | 目標價/現價差用 `formatPercent(...,true)`；KpiCard 已採用、不重做 |

### auto_implement = false（需核准 / 需依賴 / 需後端）

| # | 功能 | value | effort | risk | feasible_now | 原因 |
|---|------|-------|--------|------|--------------|------|
| 13 | dashboard 持股/KPI 內嵌 Sparkline | high | M | medium | false | `Holding`/`PortfolioSummary` 無價格時間序列，需後端補 `price_history` 欄位 |
| 14 | morning-report 新聞清單情緒標籤 | medium | M | medium | false | `/news/latest` 單則新聞無 sentiment 欄位；逐則情緒需 AI 分析（已有 /ai/news-sentiment，但需後端把情緒併入列表或前端批次呼叫＝後端/額外請求） |
| 15 | 全面 DataTable 遷移（TanStack Table：排序/篩選/分頁/匯出 CSV、響應式欄優先級） | high | L | high | false | 跨多頁大改、需抽共用 `<DataTable>`、行為回歸風險高 |
| 16 | journal AI 報告改 react-markdown | medium | M | medium | false | react-markdown 未安裝，需新依賴 |
| 17 | realtime 報價表加成交量/成交金額欄 | medium | M | medium | false | 需後端提供 volume/amount 欄位 |
| 18 | morning-report 歷史日期篩選 | low | M | medium | false | 需後端支援日期查詢參數 |

---

## B. per_page_plan（auto_implement=true 逐頁彙整，同頁合併避免衝突）

### (research)/compare/page.tsx — risk: low
- 移除本地 `const COLORS = ['#3b82f6',...]`，改 `import { CHART_SERIES } from '@/lib/constants/chartColors'`，Line stroke、已選標籤、表格代號色全部換成 `CHART_SERIES[i % CHART_SERIES.length]`。
- `base_price.toFixed(2)`、`latest_price.toFixed(2)` → `formatPrice()`；`total_return_pct` 顯示改 `formatPercent(s.total_return_pct, 2, true)`（帶 ▲▼）。
- 指標對比表新增「走勢」欄，每列 `<Sparkline data={s.data.map(d => d.normalized)} autoColor />`（資料已存在於 `data.stocks[].data`）。

### (market)/heatmap/page.tsx — risk: low
- StockGrid 個股格的 `formatPercent(stock.change_pct)` 與 tooltip 的 `formatPercent(tooltip.stock.change_pct)` 改 `formatPercent(..., 2, true)`，補上 ▲▼（industry 卡層已有 ▲n▼n 計數，補齊個股層雙重編碼）。

### (market)/after-hours/page.tsx — risk: low
- AiPickList 序號徽章：`i < 3` 時改顯示 `['🥇','🥈','🥉'][i]`，其餘維持數字。
- StockRankTable 前 3 名加同樣獎牌前綴（漲幅/跌幅榜）。
- AI 摘要區：生成中按鈕補 `aria-busy={aiLoading}`，文案保留「生成中」；skeleton 已存在不動。

### (portfolio)/journal/page.tsx — risk: low
- 表格上方新增 filter chips：`全部/買入/賣出/加碼/減碼`，以 `useState<action|'all'>` 過濾 `data.entries`；chip 樣式沿用 `ACTION_LABELS` 色與 token。
- `e.price.toFixed(2)` → `formatPrice(e.price)`；預估金額 `(amount/1e4).toFixed(1) 萬` → `formatCurrency(amount, { compact: true })`；新增表單的 `estimatedAmount` 同步用 `formatCurrency`。
- （不改 AI 報告 renderMarkdown — react-markdown 屬 deferred。）

### (market)/dashboard/page.tsx — risk: low
- 持股表頭以 shadcn `Tooltip`（已裝）包裹「成本價/現價/市值/損益(%)」，補欄位定義文字；整表用 `TooltipProvider` 包一次。
- `PositionRowSkeleton` 各 `<td>` 的 `Skeleton` 寬度改為依欄位語意的差異化寬度（如代號 `w-12`、名稱 `w-24`、數值欄 `w-16~w-20`），消除等寬死值。

### (portfolio)/watchlist/page.tsx — risk: low
- 顯示 `change_pct` 處改 `formatPercent(change_pct, 2, true)` 帶 ▲▼（色盲友善）。

### (strategy)/predictions/page.tsx — risk: low
- 目標價 vs 現價的漲跌幅顯示改用 `formatPercent(..., 2, true)`／`formatChange(..., 2, true)` 帶方向符號；KpiCard 已採用、error 已部分解構，不重做資料層。

---

## C. deferred 進度（多數已完成，2026-05-31 更新）

1. ✅ **TanStack `<DataTable>` 全面遷移** — 已建共用元件並導入 screener/predictions/chip/dashboard（排序/搜尋/分頁/CSV 匯出）。
2. ✅ **dashboard 持股/KPI Sparkline** — 後端 `/portfolios/{id}` holdings 已補 `price_history`（近 30 日）；持股表加走勢欄。
3. ✅ **morning-report 新聞情緒標籤** — 新聞已有 `sentiment` 欄位，前端渲染利多/利空/中性 badge。
4. ✅ **journal AI 報告 react-markdown 化** — 已裝 `react-markdown`+`remark-gfm`，取代手刻 renderMarkdown。
5. ✅ **realtime 成交量/成交金額欄** — 後端 quote 已補 `amount`（volume 本有），前端加兩欄。
6. ⏸️ **morning-report 歷史日期篩選**（唯一未做）：需後端建「歷史新聞儲存 + 日期查詢」，屬較大後端工程。

### 新增（本輪交付，不在原 audit）
- ✅ **AI 投資顧問**（quant + Claude 敘述 + 一鍵套用）：`/advisor`。
- ✅ **截圖匯入持股**（Claude Vision）：共用 `ScreenshotImportDialog`，接入 advisor/portfolio/watchlist/stock（見 §0）。
- ✅ **後端資料持久化**：Railway Volume 掛 `/app/data`，投組/自選等跨 redeploy 不消失。

> B 區六頁低風險批次與上述 deferred 主項皆已實作上線。剩餘僅 morning-report 歷史日期（需後端歷史儲存）。
