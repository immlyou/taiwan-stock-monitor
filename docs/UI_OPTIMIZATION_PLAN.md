# 台股分析系統 版面優化計畫 (UI/UX Optimization Plan)

> 對象：Streamlit 台股分析系統（25 個頁面 + 共用元件 `theme.py` / `sidebar.py` / `charts.py` / `page_header.py` / `empty_state.py` / `error_handler.py`）
> 風格：深色專業終端機（紅漲綠跌），對標 TradingView / Bloomberg / 富途牛牛 / XQ / CMoney
> 版本：v1.0｜定位為可落地的工程清單，所有建議皆對應實際檔案與函式

---

## 1. 執行摘要

### 1.1 現況最大的 5 個版面問題

| # | 問題 | 嚴重度 | 影響範圍 |
|---|------|--------|----------|
| **P-1 設計系統「定義完整、執行破碎」** | `theme.py` 已備齊 `create_kpi_card` / `create_stock_card` / `create_section_header` / `format_change_value` / `create_mini_sparkline` / `create_data_table_row`，但各頁面大量直接用 `st.metric()`、`st.markdown('---')`、`st.markdown('#####')`、手刻 inline HTML。同一概念全站多種長相。 | High | 全站 25 頁 |
| **P-2 響應式只做半套** | `theme.py` line 377-383 僅有 768px / 480px 兩個斷點，且只調 `flex` 寬度，未處理欄數、圖表高度、表格。多數頁面 `st.columns()` 欄數寫死（首頁 6 欄、盤後 5 欄、財報 6 欄），平板（768-1024px）與手機嚴重擠壓、文字溢位。 | High | 全站，尤以 KPI 列為甚 |
| **P-3 缺少「全域市場脈絡」與「跨頁快速切換」** | 沒有頂部恆駐行情列（大盤/漲跌家數/開收盤狀態/更新時間），也沒有全域股票搜尋與持久 watchlist 側欄。使用者每換一檔股票就得逐頁用 `selectbox` 從 1000+ 檔挑選。 | High | 全站導航體驗 |
| **P-4 高密度頁面資訊組織失序** | 個股分析（6 大 Tab×3 子 Tab）、籌碼分析、財報分析、風險分析把所有內容線性平鋪，無摘要層、無漸進式揭露；資金流向條形圖在 2 欄 170px 內擠壓導致股票名稱截斷。 | High | 高流量分析頁 |
| **P-5 漲跌/狀態色與字體不統一、無障礙不足** | 硬編色（`#ef4444`/`#22c55e`/`#2196F3`/`#FF9800`）散落各頁圖表，未引用 `COLORS`；`text_muted #64748b` 對比不足 WCAG AA；數字非等寬、未右對齊、漲跌僅靠顏色（`create_kpi_card` 已有 ▲▼，但表格與 `st.metric` 未一致）。 | Medium-High | 全站圖表與表格 |

### 1.2 整體優化方向

1. **先收斂設計系統（P0），再改頁面（P1/P2）**：把現有 `theme.py` 元件升級為「唯一正解」，並新增缺口元件（行情列、診斷卡、響應式欄、骨架載入）。一次改 token / 元件即可惠及多頁。
2. **建立全域語意色 token + 雙重編碼**：紅漲綠跌中飽和度防疲勞，所有漲跌一律「顏色 + ▲▼ + 正負號」，次要維度（資金四檔、買賣方強弱）用同色相深淺。
3. **導入旗艦終端機四大版面範式**：頂部全域行情列、持久 watchlist 側欄（master-detail）、個股頁兩層 Tab、高密度表格（sticky/凍結/等寬右對齊）。
4. **以漸進式揭露重整高密度頁**：首屏 ≤5 個關鍵元素 + 摘要卡，細節收進 Tab / expander。
5. **補完響應式**：新增平板（1024px）與超寬（1600px）斷點，並建立 `responsive_columns()` helper 統一欄數邏輯。

---

## 2. 統一設計系統升級建議（對照 `theme.py` 現況）

### 2.1 色彩 Token

**現況**（`theme.py` line 11-38）：`COLORS` 已定義 up/down/flat/primary/secondary/accent/text_*/border/狀態色，方向正確（紅漲綠跌）。
**問題**：飽和度偏高（純 `#ef4444`/`#22c55e`，長時間盯盤刺眼）；`text_muted #64748b` 在 `#1a1f2e` 上對比 < 4.5:1；缺「非價格分類色」（資金外資/投信/主力）；`sidebar.py` 另存 `SIDEBAR_COLORS` 與 `COLORS` 重疊。

**該改什麼**：
- 將 `up`/`down` 改為中飽和（如 `up #e84855` 系、`down #1faa6f` 系），保留語意方向；新增 `up_strong`/`down_strong`（漲停/跌停強調）與 `up_weak`/`down_weak`（同色相淺色承載四檔資金深淺）。
- `text_muted` 提至 `#8b95a6`（對比 ~7:1）。
- 新增**非價格分類色**：`flow_foreign`（藍）、`flow_trust`（橘）、`flow_dealer`（紫）取代各頁硬編 `#2196F3`/`#FF9800`/`#9C27B0`（見 `19_資金流向.py`）。
- 刪除 `sidebar.py` 的 `SIDEBAR_COLORS`，改 `from theme import COLORS` 並以別名引用。
- 在 `inject_professional_theme()` 的 `<style>` 內輸出 CSS 變數（`:root { --up: ...; --text-muted: ...; }`），讓手刻 HTML 與 CSS class 共用單一來源。

### 2.2 字級 / 間距 Token

**現況**：字級散落 inline（KPI 卡 1.75rem、`st.metric` 1.8rem、label 0.7rem vs 0.75rem），間距硬編（`margin-bottom:8px`）。
**該改什麼**：在 `theme.py` 新增 `TYPO` 與 `SPACE` dict（如 `TYPO['kpi_value']='1.75rem'`、`TYPO['label']='0.75rem'`、`SPACE['card_gap']='12px'`），所有元件函式引用；**新增等寬數字字型規範**：價格/漲跌幅/財報數字統一 `font-family: 'IBM Plex Mono','SF Mono',monospace` 並右對齊（透過 `st.dataframe(column_config=...)` 與表格 CSS class）。

### 2.3 KPI 卡片

**現況**：`create_kpi_card()`（line 389）已具頂部漸層線 + ▲▼ + delta；但 label 0.7rem 過小（`23_AI智慧選股.py` 文字被截為「平…」），且全站與 `st.metric()` 混用（`0_持倉總覽`/`8_投資組合`/`24_AI異常警報` 用原生 `st.metric`）。
**該改什麼**：
- 升級 `create_kpi_card()` 為「四件套」：大數字 + 短標籤（提至 0.85rem，`white-space:nowrap;text-overflow:ellipsis`）+ delta（▲▼ %）+ **內嵌 mini sparkline**（已有 `create_mini_sparkline` line 588，把它接進卡片右下）。
- **二擇一全站統一**：建議統一走 `create_kpi_card()`；若保留 `st.metric()`，則在 CSS 為 `[data-testid="metric-container"]` 補上頂部漸層線，使兩者視覺一致（消除 P-1 混搭）。
- 新增 `render_kpi_row(items, cols=None)` 封裝：自動套 `responsive_columns()`，全站 KPI 列改呼叫此函式。

### 2.4 表格

**現況**：`create_data_table_header/row`（line 539/548）存在但少用；各頁混用手刻 HTML 表格（`main.py` ranking、`17_即時報價` quote）、`st.dataframe`、`.style.format()`、lambda。手刻表無 hover、無 `use_container_width`。
**該改什麼**：建立統一表格規範 `render_data_table(df, *, freeze_cols, dense, numeric_cols)`：
- 數字欄右對齊 + 等寬字型；
- sticky 表頭 + 凍結最左識別欄（代號/名稱）；
- 緊湊/標準行高切換（dense 參數）；
- 細分隔線（非斑馬紋）+ 條件式背景色（漲停/爆量）；
- 全站 `st.dataframe()` 一律 `use_container_width=True` + `column_config` 控寬。
（對應研究：Bloomberg/Pencil&Paper 高密度表格範式）

### 2.5 區塊標題

**現況**：`create_section_header()`（line 444）存在；但 `0_持倉總覽`/`8_投資組合`/多頁用 `st.markdown('---')` 或 `#####`，`main.py` line 259-267 手刻 HTML 標題、`render_page_header()` 又是另一套。
**該改什麼**：
- 新增 `create_page_title()` 於 `theme.py`，`main.py` 改用之（取代手刻 HTML），與 `render_page_header()` 對齊同一視覺。
- 全站區塊分隔一律 `create_section_header(title, icon)`，禁用 `markdown('---')` 與裸 `#####`；所有呼叫**必帶 icon**（盤後總覽缺 icon 問題）。

### 2.6 圖表樣式

**現況**：`apply_dark_theme(fig, height=400)`（charts.py line 15）已存在；但高度散落（個股 600/350/300、產業 400/500、財報 350/400）、色板不一（部分硬編、部分 `RdYlGn`）、圖例位置不統一。
**該改什麼**：在 `charts.py` 建立 `CHART_CONFIG`：標準高度（大 500 / 中 400 / 小並排 300）、圖例一律 `legend=dict(orientation='h', yanchor='bottom', y=1.02)`、`hovermode='x unified'`、x 軸 `tickformat='%Y-%m-%d'`；漲跌色板統一引用 `COLORS['up']/['down']`（K 線、長條），分類圖用 `CHART_PALETTE`；漲跌類 colorscale 改 `RdYlGn_r`（紅在上）。`create_sector_bar`/風險圖等硬編色全部替換。

---

## 3. 跨頁面一致性問題與修正原則

| 不一致項目 | 現況 | 修正原則 |
|------------|------|----------|
| **頁面標題** | `main.py` 手刻 HTML vs 其他頁 `render_page_header()` | 全站 → `create_page_title()` / `render_page_header()` 單一函式 |
| **區塊分隔** | `create_section_header` vs `---` vs `#####` 三種 | 全站 → `create_section_header(title, icon)`，必帶 icon |
| **KPI 顯示** | `create_kpi_card` vs `st.metric` 混用 | 統一 `create_kpi_card()`（或補 metric CSS 對齊） |
| **手刻 HTML vs 共用元件** | 個股/即時報價/自選股/警報/AI 頁大量 inline HTML（部分用淺色 `#ddd` 破壞深色主題，見 `10_自選股`） | 一律改用 `create_stock_card` / `render_alert_card`（新增）/ `create_kpi_card`；禁止 inline 色值，改引 `COLORS` |
| **圖表庫混用** | 個股 Plotly、籌碼 `st.line_chart/bar_chart`、技術 Plotly Candlestick | 全站圖表統一 Plotly + `apply_dark_theme`；`13_籌碼分析` 的 `st.line_chart/bar_chart` 改 Plotly `make_subplots` |
| **數值格式化** | `{:.2f}` / `{:,.0f}` / `{:+.2f}%` / lambda / `.style.format` / `_metric_display` 各自為政 | 新增 `format_number(val, kind)`（price/pct/volume/amount）+ 在地化（張/億/萬）全站共用 |
| **錯誤 / 空 / 載入狀態** | `show_error` vs `st.info` vs `st.warning` vs `create_error_boundary`；無統一 loading | 原則：API 失敗→`show_error()`；無資料→`show_empty_state()`（加 CTA）；載入→新增 `show_skeleton()` / `with st.spinner` 統一文案 |
| **按鈕語義** | 有時 `type='primary'`、有時無、有時 `use_container_width` | 規範：主操作 primary（藍）、次操作 secondary（灰）、危險紅（`COLORS['danger']` + 二次確認，見 `4_策略管理` 載入/刪除誤觸） |
| **Tab emoji / 命名** | 動作/名詞 emoji 混用、字數不一 | emoji + 簡潔中文（≤6 字），同類維度全站同一組 emoji |
| **欄數** | 6/5/4/3 寫死、無斷點過渡 | 全站改用 `responsive_columns(base)` |

**核心原則**：*Authoring 用元件，不用手刻*；*顏色用 token，不用 hex*；*格式用 `format_number`，不用 inline f-string*。

---

## 4. 借鏡市面軟體的具體版面模式（導入優先序）

| # | 模式 | 來源 | 套用頁面 | Streamlit 落地方式 |
|---|------|------|----------|--------------------|
| **M1 頂部全域行情列 + 命令列搜尋** | Bloomberg 命令列 / TradingView toolbar | 全站（置於 `page_header.py` 之上的跨頁 container） | 新增 `render_global_ticker_bar()`：加權/櫃買指數、漲跌家數、盤中/盤後 badge、最後更新時間（紅綠 + ▲▼）；右側 `st.text_input` 輸入代號 Enter 即 `set_state(SELECTED_STOCK)` 跳個股分析 |
| **M2 持久 watchlist 側欄（master-detail）** | TradingView Watchlist / CMoney 自選 | `sidebar.py`、`10_自選股`、`0_持倉總覽` | 側欄精簡 watchlist（代號/現價/漲跌幅 + ▲▼ 著色），點選 → 主區聯動更新，不換頁 |
| **M3 個股頁兩層 Tab 結構** | 富途/同花順 F10「頂層大 tab + 次層 segmented」 | `3_個股分析` | 頂層 `st.tabs(['行情','技術','籌碼','財報','消息'])`；層內用 `st.radio(horizontal=True)` 做維度切換，取代現行 6 Tab×3 子 Tab 的深層巢狀 |
| **M4 六宮格多空診斷卡** | 三竹六宮格診斷 | `3_個股分析` 頂部、`main.py` 戰情中心 | 一排診斷卡（技術/籌碼/財務/法人/趨勢/量能 分數，紅綠燈），點卡展開對應 Tab；可串接既有 AI 能力 |
| **M5 高密度表格（sticky/凍結/等寬右對齊/密度切換）** | Bloomberg / Pencil&Paper | `1_選股篩選`、`13_籌碼分析`、`0_持倉總覽`、`23_AI智慧選股` | `render_data_table()`（見 2.4）；欄位多選 `column_order` 模擬同花順欄位橫滑 |
| **M6 資金/籌碼四段縱向遞進** | 富途資金分布 / CMoney 籌碼K線堆疊 | `19_資金流向`、`13_籌碼分析` | 淨流入 KPI 卡 → 法人四類分組長條 → 多日淨流向折線（`hovermode='x unified'` 模擬十字線）→ 可展開逐日明細；買賣超改**單欄全寬**（修正 2 欄 170px 名稱截斷） |
| **M7 漸進式揭露 + 聰明預設** | Bloomberg concealing complexity / TradingView 簡化 alert | `2_回測`、`5_參數優化`、`11_警報設定`、`6_風險分析`、`23_AI` | 首屏給好預設 + 精簡結果，進階參數收 `st.expander`；風險分析「摘要 3 卡 → 詳細 expander → 圖表分 Tab」 |
| **M8 版面預設模板 + 偏好記憶** | 同花順佈局模板 / 富途畫布組件 | `3_個股分析`、`22_技術分析`、`main.py` | `st.radio(['純技術','技術+籌碼','全資訊'])` 控制顯示區塊，用 `session_manager` 記住；盤中/盤後一鍵切換視圖 |

---

## 5. 分頁優化建議

### 5.1 市場總覽 / 儀表板類

| 頁面 | 問題 | 建議 | 優先級 |
|------|------|------|--------|
| `main.py 戰情中心` | 第一行 6 欄 KPI 小屏擠壓溢位 | 改 `responsive_columns(6)`（>1400=6 / >1024=4 / >768=3 / 其餘 2） | P1 |
| `main.py` | row2 `[1,2,2]` 情緒儀表過窄、排行 3 欄文字截斷 | 改 `[1.5,1.5,2]`；排行改 2 欄或全寬 + `text-overflow:ellipsis` | P1 |
| `main.py` | 標題手刻 HTML、KPI 卡與其他頁混搭 | 改 `create_page_title()` + `create_kpi_card()` | P1 |
| `0_持倉總覽` | 用 `st.metric` + `---` + `#####`，與全站不一致 | 改 `create_kpi_card` + `create_section_header`；持股表全寬、高度 450-500 | P1 |
| `16_每日晨報` | 利多/利空並排高度不齊；AI 分析排序錯位 | 改上下堆疊或 Tab + 固定容器高度 180px；重排序（總覽→新聞→熱門→AI→自選） | P2 |
| `17_即時報價` | `[1,3]` 指數區換行；快速鈕 6 欄 vs 卡片 3 欄不一致 | 改 `[1.5,2.5]`；統一 3 欄；批次表加開/高/低/額欄 | P2 |
| `18_市場熱力圖` | 控制+統計混在一行；產業圖硬編紅綠 | 拆兩行（控制 2 / 統計 4）；色彩改 `COLORS['up']/['down']` | P2 |
| `19_資金流向` | 買賣超 2 欄條形圖名稱截斷；硬編分類色 | 改**單欄全寬**圖（M6）；分類色用 `flow_*` token；Tab emoji 統一 | P1 |
| `20_盤後總覽` | 5 欄 KPI 換行；section_header 缺 icon | `responsive_columns(5)`；所有 header 帶 icon；買賣超改單欄全寬 | P2 |

### 5.2 個股 / 產業分析類

| 頁面 | 問題 | 建議 | 優先級 |
|------|------|------|--------|
| `3_個股分析` | 5 欄標題擠壓；6 Tab×3 子 Tab 巢狀過深；手刻 HTML 多 | 改兩層 Tab（M3）+ 頂部診斷卡（M4）；KPI 改 `create_kpi_card`；刪財務 Tab（與頁 14 重複）改跳轉 | P1 |
| `7_產業分析` | 個別產業詳情 3 層巢狀、無快取 | 詳情提為獨立 Tab、改卡片跳轉（最多 2 層）；計算加 `@st.cache_data` | P2 |
| `12_比較分析` | 9 欄表水平捲、雷達圖邏輯脆弱 | sticky 表頭 + 凍結代號欄；雷達缺值填 N/A；高度統一 400 | P2 |
| `13_籌碼分析` | `st.line_chart/bar_chart` 風格不一；說明文字佔 Tab | 改 Plotly `make_subplots`（M6）；說明改 expander；移除說明 Tab | P1 |
| `14_財報分析` | 6 欄 KPI 折行不齊；6 Tab 圖表函式各異 | F10 標準分區 + 操盤必讀摘要卡；`responsive_columns`；`plot_wrapper()` 統一圖表 | P2 |
| `22_技術分析` | 5 checkbox 折行；硬編 `#ef4444/#22c55e` | 副指標按用途分類 selectbox（趨勢/動能/量能）；色改 `COLORS` | P2 |

### 5.3 策略 / 回測 / 風險類

| 頁面 | 問題 | 建議 | 優先級 |
|------|------|------|--------|
| `1_選股篩選` | 條件 5 欄擠壓；手動分頁佔空間 | 條件改卡片式（每條件一卡）；改 `st.dataframe` 內建分頁；四分類 + 即時命中筆數 + 另存策略 | P1 |
| `2_回測分析` | 結果區無「結果開始」標誌；交易表 9 欄密集 | 加 `create_section_header('回測結果')`；簡潔/詳細視圖切換；表高 500 | P2 |
| `4_策略管理` | 載入/刪除按鈕同權重易誤觸 | 載入 primary、刪除 danger + 二次確認 | P2 |
| `5_參數優化` | 缺組合數/耗時預估；range 用 multiselect 高度不齊 | 執行前 info box 顯示組合數 × 預估耗時；range 改 number_input(min,max) + progress bar | P2 |
| `6_風險分析` | 指標線性平鋪、無優先級；圖表用 `blue/gray` | 摘要 3 卡 → 詳細 expander → 圖表分 Tab（M7）；圖表套 `apply_dark_theme` + `COLORS` | P1 |
| `21_預測驗證` | 11 欄表水平捲；待驗證清單過長 | 改預測卡片視圖 + 排序/篩選；分頁或可摺疊卡片組 | P2 |

### 5.4 投組 / AI / 管理類

| 頁面 | 問題 | 建議 | 優先級 |
|------|------|------|--------|
| `8_投資組合` | KPI 4 等欄「總損益」權重不足；標題混用 | 改 2×2，總損益加粗加色；統一 `create_section_header` | P1 |
| `10_自選股` | 卡片硬編淺色 `#ddd` 破壞深色主題；3 欄寫死；操作分散 | 改 `create_stock_card`（深色 token）；`responsive_columns`；內聯操作按鈕（M2 master-detail） | P1 |
| `11_警報設定` | 建立警報 9 種下拉過長；卡片手刻無邊界 | 9 類改 3×3 點擊卡片網格選擇器；新增 `render_alert_card()` 統一樣式 | P2 |
| `15_交易日誌` | 新增表單欄位不均；統計圖無優先級 | 改 3 行佈局；統計 Tab：KPI→月趨勢全寬→類型/標籤並排 | P2 |
| `23_AI智慧選股` | KPI 標籤截斷；11 欄表過寬；說明手刻 HTML | KPI 2×2 + label 0.85rem；主表 6 欄 + 點列展開；說明改 `create_section_header` + 卡片 | P1 |
| `24_AI異常警報` | 異常列表純文字無分組；不可篩選匯出 | 按嚴重度分組摺疊（🔴高/🟡中）；異常改卡片（紅/黃底）；加篩選/排序/匯出 | P2 |
| `9_系統設定` | 三通知方案 + 8 版本 expander 過長（>3000px）；硬編版本色 | 通知改 3 Tab；版本歷史分頁/表格；版本色改 `COLORS` | P2 |

### 5.5 共用元件 / 設計系統

| 元件 | 問題 | 建議 | 優先級 |
|------|------|------|--------|
| `theme.py` | 響應式僅 768/480 + 只調 flex；無 CSS 變數；CSS 重複注入 | 新增 1024/1600 斷點 + 圖表/表格規則；輸出 `:root` CSS 變數；改全域注入一次（session flag） | P0 |
| `theme.py` | KPI 卡 / 表格 / 標題元件未被全站採用 | 升級並新增 `render_kpi_row` / `render_data_table` / `responsive_columns` / `create_page_title` / `format_number` | P0 |
| `sidebar.py` | 27 頁平鋪、`SIDEBAR_COLORS` 重複、快取狀態佔空間 | 收斂 4-5 一級分組（戰情/個股/選股回測/投組自選/AI）；快取改單行 badge + `st.toast`；刪 `SIDEBAR_COLORS` | P1 |
| `charts.py` | 高度/色板/圖例不一 | 建立 `CHART_CONFIG`，統一高度/`legend`/`hovermode`/colorscale | P0 |
| `empty_state.py` | 無 CTA、icon 固定小 | 加 `action_label`/`action_cb` CTA；情境化（首用/無結果/已清空） | P1 |
| `error_handler.py` | 用原生 `st.error/warning/info` 色與 `COLORS` 不符；無載入態 | 改自訂 HTML container 引 `COLORS`；新增 `show_skeleton()` 骨架載入 | P1 |
| `page_header.py` | `[6,2,1]` 固定比例 + 無返回/麵包屑 | 改自適應 + 768px 上下排列；加返回/麵包屑；上方掛 M1 行情列 | P1 |
| `strategy_params.py` | 寫死 `st.columns(3)`；help 預設關閉 | 改 `responsive_columns(3)`；help 常顯淡字；策略類型用 Tab | P2 |

---

## 6. 優先級路線圖

### P0 — 設計系統與全域基礎（先做，惠及全站）

| 項目 | 預估影響 | 工作量 |
|------|----------|--------|
| `theme.py` 色彩/字級/間距 token 化 + 輸出 CSS 變數 + `text_muted` 對比修正 | 全站視覺一致基礎 | M |
| 新增/升級核心元件：`create_kpi_card`(+sparkline)、`render_kpi_row`、`render_data_table`、`responsive_columns`、`create_page_title`、`format_number` | 一次解決 P-1/P-2 多數混搭 | L |
| 補完響應式（1024/1600 斷點 + 圖表/表格 CSS）+ 全域單次注入 | 平板/手機可用性 | M |
| `charts.py` `CHART_CONFIG`：高度/legend/hovermode/colorscale 標準化 + 移除硬編色 | 全站圖表一致 | M |
| `error_handler` / `empty_state` 統一狀態元件 + `show_skeleton()` | 全站狀態體驗一致 | M |

### P1 — 高流量頁面與全域導航

| 項目 | 預估影響 | 工作量 |
|------|----------|--------|
| M1 頂部全域行情列 + 命令列搜尋（`render_global_ticker_bar`） | 全站脈絡與快速切換，高 | M |
| M2 持久 watchlist 側欄 + `sidebar.py` 分組收斂 | 導航體驗大幅提升 | M |
| `main.py` 戰情中心：響應式欄 + 標題/KPI 統一 + 排行佈局 | 首頁第一印象 | M |
| `3_個股分析` 兩層 Tab（M3）+ 診斷卡（M4）+ 去重財務 Tab | 核心分析頁 | L |
| `1_選股篩選` 四分類 + 即時筆數 + 卡片條件 + dataframe 分頁 | 高頻功能 | L |
| `13_籌碼分析` / `19_資金流向` 四段遞進 + Plotly 化 + 單欄全寬 | 籌碼資金可讀性 | M |
| `8_投資組合` / `10_自選股` / `23_AI` KPI 與卡片統一 + 深色修正 | 投組/AI 一致性 | M |
| `6_風險分析` 漸進式揭露重整 | 風險頁減負 | M |

### P2 — 其餘頁面與進階體驗

| 項目 | 預估影響 | 工作量 |
|------|----------|--------|
| `7/12/14/22` 個股產業類：圖表 wrapper、響應式、表格規範套用 | 中 | M |
| `2/4/5/21` 策略回測類：結果分區、按鈕語義、進度預估、卡片視圖 | 中 | M |
| `9/11/15/16/17/18/20/24` 管理與市場類：Tab 化、分組、篩選匯出、事件日曆 | 中 | M-L |
| M8 版面預設模板 + 偏好記憶（個股/技術/戰情） | 進階體驗 | M |
| 盤中/盤後自動切換 + 在地化（張/億/萬、除權息 badge） | 台股使用者貼合度 | M |

> 工作量：S=半天內、M=1-2 天、L=3 天以上。

---

## 7. 快速見效清單（Quick Wins，改共用層即多頁受益）

1. **`COLORS` 加固 + CSS 變數**：修 `text_muted` 對比、降漲跌飽和度、加 `flow_*` 分類色 → 全站圖表/文字一次提升（`theme.py` line 11-38, 41）。
2. **`responsive_columns(base)` helper**：所有寫死 `st.columns(6/5/4/3)` 替換 → 一次解決全站 KPI 列小屏溢位。
3. **`format_number(val, kind)`**：統一 price/pct/volume/amount + 在地化（張/億）→ 取代散落 f-string / lambda / `.style.format`。
4. **`render_kpi_row()`**：封裝 `create_kpi_card` + 響應式欄 → 戰情/盤後/晨報/個股/AI 頂部 KPI 一行改完。
5. **`st.dataframe(use_container_width=True, column_config=...)` 全站套用 + 數字右對齊等寬 CSS**：消除表格截斷與對齊問題。
6. **`create_section_header(必帶 icon)` 取代所有 `---` 與 `#####`**：全站區塊層級瞬間一致。
7. **`charts.py` `apply_dark_theme` 加上 `legend(orientation='h')` + `hovermode='x unified'` + 標準高度**：所有 Plotly 圖一次升級互動與一致性。
8. **`empty_state` 加 CTA、`error_handler` 引 `COLORS`**：空/錯狀態全站統一且更友善。
9. **按鈕語義 CSS 規範**（primary 藍 / secondary 灰 / danger 紅）寫進 `theme.py` 並全站套 `type=` → 解決誤觸與優先級混亂。
10. **`sidebar.py` 快取狀態改單行 badge + `st.toast`**：立即釋放側欄垂直空間。

---

*本計畫對應實際檔案與函式，建議依 P0 → P1 → P2 推進；P0 多為共用層改動，完成後 P1/P2 頁面工作量將顯著降低。*
