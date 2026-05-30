# -*- coding: utf-8 -*-
"""
專業金融風格主題

提供類似 Bloomberg / Reuters 終端機的專業視覺設計
"""
import streamlit as st


# 專業金融配色
COLORS = {
    # 主色調
    'primary': '#1a1f2e',      # 深藍黑 (背景)
    'secondary': '#252b3d',    # 次深藍 (卡片)
    'accent': '#3b82f6',       # 亮藍 (強調)

    # 漲跌色（紅漲綠跌，中飽和防盯盤疲勞）
    'up': '#f6465d',           # 紅色 (上漲)
    'up_bg': 'rgba(246, 70, 93, 0.12)',
    'up_strong': '#ff2d4b',    # 漲停強調
    'up_weak': 'rgba(246, 70, 93, 0.45)',  # 同色相淺色（承載強弱深淺）
    'down': '#2ebd85',         # 綠色 (下跌)
    'down_bg': 'rgba(46, 189, 133, 0.12)',
    'down_strong': '#0ecb81',  # 跌停強調
    'down_weak': 'rgba(46, 189, 133, 0.45)',
    'flat': '#7a8699',         # 灰色 (平盤)

    # 非價格分類色（三大法人 / 資金流向，取代各頁硬編色）
    'flow_foreign': '#3b82f6', # 外資（藍）
    'flow_trust': '#f59e0b',   # 投信（橘）
    'flow_dealer': '#8b5cf6',  # 自營商（紫）

    # 文字色
    'text_primary': '#f1f5f9',   # 主文字
    'text_secondary': '#a3aec0', # 次文字
    'text_muted': '#8b95a6',     # 淡文字（提升對比至 ~WCAG AA）

    # 邊框
    'border': '#374151',
    'border_light': '#4b5563',

    # 狀態色
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#f6465d',
    'info': '#3b82f6',
}


# ===== 字級 Token（全站統一字級，取代散落 inline 值）=====
TYPO = {
    'page_title': '1.8rem',
    'section_title': '1.1rem',
    'kpi_value': '1.75rem',
    'kpi_value_lg': '2rem',
    'label': '0.8rem',       # KPI/欄位標籤（由 0.7rem 提升避免截斷）
    'body': '0.95rem',
    'caption': '0.8rem',
    'mono': "'IBM Plex Mono', 'SF Mono', 'Roboto Mono', ui-monospace, monospace",  # 數字等寬
}

# ===== 間距 Token =====
SPACE = {
    'card_gap': '12px',
    'card_pad': '1.25rem',
    'section_gap': '2rem',
    'row_gap': '1.5rem',
}


def inject_professional_theme(force: bool = False):
    """注入專業金融主題 CSS

    註：Streamlit 多頁應用每次換頁/rerun 都會重建 DOM，故 CSS 必須每次注入；
    不可用 session_state 做「單次注入」guard（否則第一頁之後會失去樣式）。
    `force` 參數保留以相容呼叫端。
    """
    st.markdown(f"""
    <style>
    /* ===== CSS 變數（單一色彩來源，手刻 HTML 與 class 共用）===== */
    :root {{
        --color-primary: {COLORS['primary']};
        --color-secondary: {COLORS['secondary']};
        --color-accent: {COLORS['accent']};
        --color-up: {COLORS['up']};
        --color-down: {COLORS['down']};
        --color-flat: {COLORS['flat']};
        --text-primary: {COLORS['text_primary']};
        --text-secondary: {COLORS['text_secondary']};
        --text-muted: {COLORS['text_muted']};
        --color-border: {COLORS['border']};
        --font-mono: {TYPO['mono']};
    }}

    /* ===== 全域樣式 ===== */
    .stApp {{
        background: linear-gradient(135deg, {COLORS['primary']} 0%, #0f172a 100%);
    }}

    /* 主內容區域 */
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}

    /* ===== 標題樣式 ===== */
    h1 {{
        color: {COLORS['text_primary']} !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
        border-bottom: 2px solid {COLORS['accent']};
        padding-bottom: 0.5rem;
    }}

    h2, h3, h4, h5, h6 {{
        color: {COLORS['text_primary']} !important;
        font-weight: 600 !important;
    }}

    /* ===== 指標卡片樣式 (st.metric) ===== */
    [data-testid="stMetricValue"] {{
        color: {COLORS['text_primary']} !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }}

    [data-testid="stMetricLabel"] {{
        color: {COLORS['text_secondary']} !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.75rem !important;
    }}

    [data-testid="stMetricDelta"] {{
        font-weight: 600 !important;
    }}

    /* 指標容器背景 */
    [data-testid="metric-container"] {{
        background: {COLORS['secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }}

    /* ===== 全域排版 ===== */
    .stApp, .stApp p, .stApp li {{
        line-height: 1.6;
    }}

    /* ===== 按鈕樣式 ===== */
    .stButton > button {{
        background: linear-gradient(135deg, {COLORS['accent']} 0%, {COLORS['accent']}dd 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
    }}

    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }}

    /* Primary 按鈕 */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #1d4ed8 100%);
    }}

    /* ===== DataFrame 表格樣式 ===== */
    .stDataFrame {{
        background: {COLORS['secondary']} !important;
        border-radius: 12px;
        overflow: hidden;
    }}

    [data-testid="stDataFrame"] > div {{
        background: {COLORS['secondary']} !important;
    }}

    /* 表格標題 */
    .stDataFrame thead th {{
        background: {COLORS['primary']} !important;
        color: {COLORS['text_secondary']} !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.7rem !important;
        border-bottom: 2px solid {COLORS['accent']} !important;
    }}

    /* 表格內容 */
    .stDataFrame tbody td {{
        background: {COLORS['secondary']} !important;
        color: {COLORS['text_primary']} !important;
        border-bottom: 1px solid {COLORS['border']} !important;
    }}

    .stDataFrame tbody tr:hover td {{
        background: rgba(59, 130, 246, 0.1) !important;
    }}

    /* ===== 側邊欄樣式 ===== */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {COLORS['primary']} 0%, #0c1222 100%);
        border-right: 1px solid {COLORS['border']};
    }}

    [data-testid="stSidebar"] .stMarkdown {{
        color: {COLORS['text_secondary']};
    }}

    /* ===== 分隔線 ===== */
    hr {{
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, {COLORS['border']}, transparent);
        margin: 1.5rem 0;
    }}

    /* ===== Expander 折疊區塊 ===== */
    .streamlit-expanderHeader {{
        background: {COLORS['secondary']} !important;
        border-radius: 8px !important;
        color: {COLORS['text_primary']} !important;
    }}

    .streamlit-expanderContent {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']};
        border-top: none;
        border-radius: 0 0 8px 8px;
    }}

    /* ===== 警告/資訊框 ===== */
    .stAlert {{
        background: {COLORS['secondary']} !important;
        border-radius: 8px;
        border-left: 4px solid;
    }}

    /* ===== Caption 說明文字 ===== */
    .stCaption {{
        color: {COLORS['text_muted']} !important;
    }}

    /* ===== Selectbox 下拉選單 ===== */
    .stSelectbox > div > div {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
        border-radius: 8px;
    }}

    /* ===== 多選標籤 ===== */
    .stMultiSelect > div > div {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
    }}

    /* ===== 文字輸入框 ===== */
    .stTextInput > div > div > input {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
        color: {COLORS['text_primary']} !important;
        border-radius: 8px;
    }}

    /* ===== Tab 標籤頁 ===== */
    .stTabs [data-baseweb="tab-list"] {{
        background: {COLORS['primary']};
        border-radius: 8px 8px 0 0;
        gap: 0;
    }}

    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        color: {COLORS['text_secondary']} !important;
        border-radius: 8px 8px 0 0;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }}

    .stTabs [aria-selected="true"] {{
        background: {COLORS['secondary']} !important;
        color: {COLORS['accent']} !important;
        border-bottom: 2px solid {COLORS['accent']};
    }}

    /* ===== 進度條 ===== */
    .stProgress > div > div {{
        background: {COLORS['accent']} !important;
    }}

    /* ===== Plotly 圖表背景 ===== */
    .js-plotly-plot .plotly {{
        background: transparent !important;
    }}

    /* ===== 圖表容器 ===== */
    .chart-container {{
        background: {COLORS['secondary']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
    }}
    .chart-container .chart-title {{
        color: {COLORS['text_primary']};
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
    }}

    /* ===== KPI 卡片 hover ===== */
    .kpi-card {{
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .kpi-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.4) !important;
    }}

    /* ===== 股票報價卡片 hover ===== */
    .stock-card {{
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }}
    .stock-card:hover {{
        transform: translateX(4px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        border-color: {COLORS['accent']} !important;
    }}

    /* ===== 排行榜表格 ===== */
    .ranking-table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .ranking-table tr {{
        transition: background 0.15s ease;
    }}
    .ranking-table tr:nth-child(even) td {{
        background: rgba(37, 43, 61, 0.6);
    }}
    .ranking-table tr:hover td {{
        background: rgba(59, 130, 246, 0.1) !important;
    }}
    .ranking-table thead th {{
        position: sticky;
        top: 0;
        z-index: 1;
    }}

    /* ===== Slider 滑桿 ===== */
    .stSlider [data-baseweb="slider"] [role="slider"] {{
        background: {COLORS['accent']} !important;
        border-color: {COLORS['accent']} !important;
    }}
    .stSlider [data-baseweb="slider"] div[data-testid="stTickBar"] > div {{
        background: {COLORS['border']} !important;
    }}

    /* ===== Checkbox / Radio ===== */
    .stCheckbox label span[data-testid="stCheckbox"] {{
        color: {COLORS['text_primary']};
    }}
    input[type="checkbox"]:checked {{
        accent-color: {COLORS['accent']};
    }}
    input[type="radio"]:checked {{
        accent-color: {COLORS['accent']};
    }}

    /* ===== Number Input ===== */
    .stNumberInput > div > div > input {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
        color: {COLORS['text_primary']} !important;
        border-radius: 8px;
    }}

    /* ===== TextArea ===== */
    .stTextArea > div > div > textarea {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
        color: {COLORS['text_primary']} !important;
        border-radius: 8px;
    }}

    /* ===== Date Input ===== */
    .stDateInput > div > div > input {{
        background: {COLORS['secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
        color: {COLORS['text_primary']} !important;
        border-radius: 8px;
    }}

    /* ===== 深色捲軸 ===== */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: {COLORS['primary']};
    }}
    ::-webkit-scrollbar-thumb {{
        background: {COLORS['border']};
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: {COLORS['border_light']};
    }}

    /* ===== 隱藏右上角 Running Man 載入動畫 ===== */
    div[data-testid="stStatusWidget"] {{
        visibility: hidden;
        height: 0;
        position: fixed;
    }}

    /* ===== 按鈕語義（primary 藍 / secondary 灰 / danger 紅）===== */
    .stButton > button[kind="secondary"] {{
        background: {COLORS['secondary']} !important;
        color: {COLORS['text_secondary']} !important;
        border: 1px solid {COLORS['border']} !important;
        box-shadow: none;
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: {COLORS['accent']} !important;
        color: {COLORS['text_primary']} !important;
    }}
    /* 危險操作：以 .danger-btn 包裹的下一顆按鈕轉紅 */
    .danger-btn + div .stButton > button {{
        background: linear-gradient(135deg, {COLORS['danger']} 0%, #c81e3a 100%) !important;
        box-shadow: 0 2px 4px rgba(246, 70, 93, 0.3);
    }}

    /* ===== 等寬數字（價格/漲跌/金額右對齊）===== */
    .num-mono {{ font-family: {TYPO['mono']}; font-variant-numeric: tabular-nums; }}
    .stDataFrame tbody td {{ font-variant-numeric: tabular-nums; }}

    /* ===== 高密度表格（dense）===== */
    .dense-table .stDataFrame tbody td {{ padding-top: 4px !important; padding-bottom: 4px !important; }}

    /* ===== 響應式排版（KPI/卡片列依寬度自動換行；超寬放大內距）===== */
    /* 平板：5-6 欄列 → 約 3 欄 */
    @media (max-width: 1024px) {{
      [data-testid="stHorizontalBlock"] > div {{ flex: 1 1 31% !important; min-width: 160px; }}
    }}
    /* 小平板/大手機：→ 2 欄 */
    @media (max-width: 768px) {{
      [data-testid="stHorizontalBlock"] > div {{ flex: 1 1 48% !important; min-width: 140px; }}
      .main .block-container {{ padding: 1rem !important; }}
      [data-testid="stMetricValue"] {{ font-size: 1.4rem !important; }}
      h1 {{ font-size: 1.4rem !important; }}
    }}
    /* 手機：單欄 */
    @media (max-width: 480px) {{
      [data-testid="stHorizontalBlock"] > div {{ flex: 1 1 100% !important; }}
      .js-plotly-plot {{ min-height: 240px; }}
    }}
    /* 超寬螢幕：放寬內容區與卡片內距 */
    @media (min-width: 1600px) {{
      .main .block-container {{ max-width: 1680px; }}
    }}

    </style>
    """, unsafe_allow_html=True)


def create_kpi_card(label: str, value: str, delta: str = None, delta_color: str = None,
                    sparkline: list = None):
    """
    建立專業 KPI 卡片

    Parameters:
    -----------
    label : str
        指標標籤
    value : str
        指標數值
    delta : str
        變化值
    delta_color : str
        'up', 'down', 或 'flat'
    sparkline : list, optional
        迷你走勢資料（接入卡片右下角）
    """
    # 決定顏色
    if delta_color == 'up':
        color = COLORS['up']
        bg = COLORS['up_bg']
        arrow = '▲'
    elif delta_color == 'down':
        color = COLORS['down']
        bg = COLORS['down_bg']
        arrow = '▼'
    else:
        color = COLORS['flat']
        bg = 'transparent'
        arrow = ''

    delta_html = f'<div style="color:{color};font-size:0.85rem;font-weight:600;margin-top:4px">{arrow} {delta}</div>' if delta else ''

    spark_html = ''
    if sparkline:
        spark_html = f'<div style="position:absolute;right:12px;bottom:10px;opacity:0.85">{create_mini_sparkline(sparkline, color if delta_color in ("up", "down") else None)}</div>'

    # label 提升至 TYPO['label']（0.8rem）並單行省略，避免 23_AI 等頁被截成「平…」
    html = f'''
    <div class="kpi-card" style="
        background:{COLORS['secondary']};
        border:1px solid {COLORS['border']};
        border-radius:12px;
        padding:{SPACE['card_pad']};
        box-shadow:0 4px 6px rgba(0,0,0,0.3);
        position:relative;
        overflow:hidden;
    ">
        <div style="
            position:absolute;
            top:0;left:0;right:0;
            height:3px;
            background:linear-gradient(90deg,{COLORS['accent']},transparent);
        "></div>
        <div style="color:{COLORS['text_secondary']};font-size:{TYPO['label']};text-transform:uppercase;letter-spacing:0.5px;font-weight:600;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</div>
        <div class="num-mono" style="color:{COLORS['text_primary']};font-size:{TYPO['kpi_value']};font-weight:700">{value}</div>
        {delta_html}
        {spark_html}
    </div>
    '''
    return html


def responsive_columns(n, gap: str = "small"):
    """建立會在窄螢幕自動換行的欄位列（搭配 theme.py 的 @media flex 規則）。

    Streamlit 無法在伺服端得知視窗寬度，故「響應式」由 CSS flex-wrap 達成：
    寬螢幕 n 欄、平板約 3 欄、手機 2→1 欄。此 helper 統一全站 KPI/卡片列呼叫。
    """
    return st.columns(n, gap=gap)


def render_kpi_row(items, cols=None, gap: str = "small"):
    """渲染一整列 KPI 卡片。

    Parameters
    ----------
    items : list[dict]
        每張卡片參數，支援鍵：label, value, delta, delta_color, sparkline
    cols : int, optional
        欄數，預設等於 items 數量
    """
    if not items:
        return
    n = cols or len(items)
    columns = responsive_columns(n, gap=gap)
    for i, item in enumerate(items):
        with columns[i % n]:
            st.markdown(create_kpi_card(
                item.get('label', ''),
                item.get('value', '-'),
                item.get('delta'),
                item.get('delta_color'),
                item.get('sparkline'),
            ), unsafe_allow_html=True)


def create_page_title(title: str, subtitle: str = None, icon: str = None):
    """統一頁面主標題（取代各頁手刻 HTML <h1>，與 render_page_header 對齊視覺）。"""
    icon_html = f'<span style="font-size:1.6rem;margin-right:10px">{icon}</span>' if icon else ''
    subtitle_html = f'<p style="margin:2px 0 0;color:{COLORS["text_muted"]};font-size:0.85rem">{subtitle}</p>' if subtitle else ''
    return f'''
    <div style="display:flex;align-items:center;gap:6px;border-bottom:2px solid {COLORS['accent']};padding-bottom:0.5rem;margin-bottom:1rem">
        {icon_html}
        <div>
            <h1 style="margin:0;padding:0;border:none;font-size:{TYPO['page_title']};font-weight:700;color:{COLORS['text_primary']}">{title}</h1>
            {subtitle_html}
        </div>
    </div>
    '''


def format_number(value, kind: str = 'price', signed: bool = False):
    """統一數值格式化（取代散落 f-string / lambda / .style.format）。

    kind: 'price'（兩位小數）, 'pct'（百分比）, 'volume'（張，含萬/億在地化）,
          'amount'（金額，含萬/億）, 'int'（整數千分位）
    signed: 是否強制顯示正負號
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return '-'
    if value is None or (isinstance(v, float) and (v != v)):  # NaN
        return '-'

    sign = '+' if signed else ''
    if kind == 'pct':
        return f'{v:{sign}.2f}%'
    if kind == 'price':
        return f'{v:{sign},.2f}'
    if kind == 'int':
        return f'{v:{sign},.0f}'
    if kind in ('volume', 'amount'):
        suffix = ''
        unit = 1
        av = abs(v)
        if av >= 1e8:
            unit, suffix = 1e8, '億'
        elif av >= 1e4:
            unit, suffix = 1e4, '萬'
        return f'{v / unit:{sign},.2f}{suffix}'
    return f'{v:{sign},.2f}'


def render_data_table(df, *, freeze_cols: int = 1, dense: bool = False,
                      numeric_cols=None, height: int = None, column_config: dict = None):
    """統一資料表格：數字右對齊等寬、sticky 表頭、可凍結識別欄、密度切換。

    以 st.dataframe 為底（內建虛擬捲動與 sticky 表頭），全站表格一律走此函式。
    """
    import pandas as pd  # 局部 import 避免增加模組載入成本

    cfg = dict(column_config or {})
    if numeric_cols:
        for c in numeric_cols:
            if c not in cfg and c in getattr(df, 'columns', []):
                cfg[c] = st.column_config.NumberColumn(c)

    wrapper_cls = 'dense-table' if dense else ''
    if wrapper_cls:
        st.markdown(f'<div class="{wrapper_cls}">', unsafe_allow_html=True)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=height,
        column_config=cfg or None,
    )
    if wrapper_cls:
        st.markdown('</div>', unsafe_allow_html=True)


def create_section_header(title: str, icon: str = None):
    """建立區塊標題"""
    icon_html = f'<span style="margin-right:8px">{icon}</span>' if icon else ''
    return f'''
    <div style="
        display:flex;
        align-items:center;
        margin-bottom:1rem;
        padding-bottom:0.5rem;
        border-bottom:1px solid {COLORS['border']};
    ">
        <span style="
            color:{COLORS['text_primary']};
            font-size:1.1rem;
            font-weight:600;
        ">{icon_html}{title}</span>
    </div>
    '''


def create_stock_card(
    stock_id: str,
    name: str,
    price: float,
    change: float,
    change_pct: float,
    extra_info: str = None
):
    """
    建立股票報價卡片

    Parameters:
    -----------
    stock_id : str
        股票代號
    name : str
        股票名稱
    price : float
        價格
    change : float
        漲跌
    change_pct : float
        漲跌幅 (%)
    extra_info : str
        額外資訊
    """
    # 決定顏色
    if change > 0:
        color = COLORS['up']
        bg = COLORS['up_bg']
        arrow = '▲'
    elif change < 0:
        color = COLORS['down']
        bg = COLORS['down_bg']
        arrow = '▼'
    else:
        color = COLORS['flat']
        bg = 'transparent'
        arrow = '─'

    extra_html = f'<div style="color:{COLORS["text_muted"]};font-size:0.7rem;margin-top:6px">{extra_info}</div>' if extra_info else ''

    html = f'''
    <div class="stock-card" style="
        background:{COLORS['secondary']};
        border:1px solid {COLORS['border']};
        border-left:4px solid {color};
        border-radius:8px;
        padding:1rem;
        margin-bottom:8px;
    ">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
                <span style="color:{COLORS['text_primary']};font-weight:700;font-size:1rem">{stock_id}</span>
                <span style="color:{COLORS['text_secondary']};font-size:0.8rem;margin-left:6px">{name}</span>
            </div>
            <div style="
                background:{bg};
                padding:2px 8px;
                border-radius:4px;
                color:{color};
                font-size:0.75rem;
                font-weight:600;
            ">{arrow} {change_pct:+.2f}%</div>
        </div>
        <div style="margin-top:8px">
            <span style="color:{color};font-size:1.5rem;font-weight:700">{price:,.2f}</span>
            <span style="color:{color};font-size:0.85rem;margin-left:8px">{change:+.2f}</span>
        </div>
        {extra_html}
    </div>
    '''
    return html


def create_data_table_header(columns: list):
    """建立專業資料表格標題"""
    header_cells = ''.join([
        f'<th style="background:{COLORS["primary"]};color:{COLORS["text_secondary"]};padding:12px 8px;text-align:left;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:2px solid {COLORS["accent"]}">{col}</th>'
        for col in columns
    ])
    return f'<thead><tr>{header_cells}</tr></thead>'


def create_data_table_row(cells: list, highlight: str = None):
    """
    建立資料列

    Parameters:
    -----------
    cells : list
        每欄的內容
    highlight : str
        'up', 'down', 或 None
    """
    if highlight == 'up':
        bg = COLORS['up_bg']
    elif highlight == 'down':
        bg = COLORS['down_bg']
    else:
        bg = COLORS['secondary']

    row_cells = ''.join([
        f'<td style="background:{bg};color:{COLORS["text_primary"]};padding:10px 8px;border-bottom:1px solid {COLORS["border"]}">{cell}</td>'
        for cell in cells
    ])
    return f'<tr>{row_cells}</tr>'


def format_change_value(value: float, show_arrow: bool = True):
    """格式化漲跌值"""
    if value > 0:
        color = COLORS['up']
        arrow = '▲ ' if show_arrow else ''
    elif value < 0:
        color = COLORS['down']
        arrow = '▼ ' if show_arrow else ''
    else:
        color = COLORS['flat']
        arrow = ''

    return f'<span style="color:{color};font-weight:600">{arrow}{value:+.2f}%</span>'


def create_mini_sparkline(values: list, color: str = None):
    """建立迷你走勢圖 (SVG)"""
    if not values or len(values) < 2:
        return ''

    # 正規化值到 0-100
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val != min_val else 1

    normalized = [(v - min_val) / range_val * 40 for v in values]

    # 建立 SVG 路徑
    width = 80
    step = width / (len(values) - 1)
    points = ' '.join([f'{i * step},{45 - v}' for i, v in enumerate(normalized)])

    # 決定顏色
    if color is None:
        color = COLORS['up'] if values[-1] >= values[0] else COLORS['down']

    svg = f'''
    <svg width="{width}" height="50" style="display:block">
        <polyline
            points="{points}"
            fill="none"
            stroke="{color}"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
        />
    </svg>
    '''
    return svg


# 圖表 trace 色票（統一全站圖表線條顏色）
CHART_PALETTE = [
    '#3b82f6',  # Blue (accent)
    '#f59e0b',  # Amber
    '#8b5cf6',  # Purple
    '#06b6d4',  # Cyan
    '#ec4899',  # Pink
    '#f97316',  # Orange
    '#10b981',  # Emerald
    '#6366f1',  # Indigo
]

# 預設主題
DEFAULT_PLOTLY_LAYOUT = {
    'paper_bgcolor': 'rgba(0,0,0,0)',
    'plot_bgcolor': 'rgba(0,0,0,0)',
    'font': {
        'color': COLORS['text_secondary'],
        'family': 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
    },
    'xaxis': {
        'gridcolor': COLORS['border'],
        'zerolinecolor': COLORS['border'],
    },
    'yaxis': {
        'gridcolor': COLORS['border'],
        'zerolinecolor': COLORS['border'],
    },
    'legend': {
        'bgcolor': 'rgba(0,0,0,0)',
        'font': {'color': COLORS['text_secondary']},
    },
}
