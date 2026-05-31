# 可採用功能盤點與逐頁實作計畫

> 承接 `UI_AUDIT.md`（§3 P2/選配、§4 已良好清單）與 `docs/UI_OPTIMIZATION_PLAN.md`（§4 市面範式）。
> 原則：只列「現在可採用、低/中風險、用既有套件/元件、自包含、不需後端改動、不需新依賴」者進入 auto_implement。
> 高風險/需依賴/需後端欄位者進 deferred。所有路由相對 `src/app/`。

已安裝可用：`@tanstack/react-table`、`recharts`、`lightweight-charts`、`react-hook-form`、`zod`、`zustand`、`swr`、`lucide-react`。
既有共用：`shared/{KpiCard(支援 sparkline),Sparkline,EmptyState,StockInput,StockSearch}`、`ui/{table,tabs,dialog,switch,tooltip,...}`、`layout/MarketTicker`、`lib/utils/format.ts`（已含 `changeArrow`、`formatPercent(withArrow)`、`formatChange(withArrow)`）、`lib/constants/chartColors.ts`（`CHART_SERIES`、`FLOW`、`ratingColor`）。
**react-markdown 未安裝**。

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

## C. deferred（需核准的高風險/高價值大改）

1. **TanStack Table 共用 `<DataTable>` 全面遷移**（value high / effort L / risk high）：抽共用排序/篩選/分頁/匯出 CSV/響應式欄優先級元件，逐頁導入（dashboard、screener、chip、journal、compare、predictions）。影響面最大、需單獨 PR 與互動回歸，**勿與上述自動批次混做**。
2. **dashboard 持股/KPI Sparkline**（value high / effort M / risk medium）：需後端為 holdings 補 `price_history`（近 20-60 日）欄位後，前端套既有 `Sparkline`／KpiCard `sparkline` prop。
3. **morning-report 新聞情緒標籤**（value medium / effort M / risk medium）：需後端把單則 sentiment 併入 `/news/latest`，或前端批次呼叫 `/ai/news-sentiment` 併入列表（額外請求＋成本），故不列入零後端自動批次。
4. **journal AI 報告 react-markdown 化**（value medium / effort M / risk medium）：需 `npm i react-markdown`（新依賴），取代脆弱的本地 `renderMarkdown`。
5. **realtime 成交量/成交金額欄**（value medium / effort M / risk medium）：需後端報價回傳 volume/amount。
6. **morning-report 歷史日期篩選**（value low / effort M / risk medium）：需後端支援日期查詢參數。

> 建議執行序：B 區六頁屬同質低風險，可一次 PR（compare 改動最多需先過視覺回歸）。deferred 全部需先取得核准與（多數）後端/依賴配合。
