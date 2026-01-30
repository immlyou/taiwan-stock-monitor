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

    # 漲跌色
    'up': '#ef4444',           # 紅色 (上漲)
    'up_bg': 'rgba(239, 68, 68, 0.1)',
    'down': '#22c55e',         # 綠色 (下跌)
    'down_bg': 'rgba(34, 197, 94, 0.1)',
    'flat': '#6b7280',         # 灰色 (平盤)

    # 文字色
    'text_primary': '#f1f5f9',   # 主文字
    'text_secondary': '#94a3b8', # 次文字
    'text_muted': '#64748b',     # 淡文字

    # 邊框
    'border': '#374151',
    'border_light': '#4b5563',

    # 狀態色
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'info': '#3b82f6',
}


def inject_professional_theme():
    """注入專業金融主題 CSS"""
    st.markdown(f"""
    <style>
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

    /* ===== 按鈕樣式 ===== */
    .stButton > button {{
        background: linear-gradient(135deg, {COLORS['accent']} 0%, #2563eb 100%);
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

    </style>
    """, unsafe_allow_html=True)


def create_kpi_card(label: str, value: str, delta: str = None, delta_color: str = None):
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

    html = f'''
    <div style="
        background:{COLORS['secondary']};
        border:1px solid {COLORS['border']};
        border-radius:12px;
        padding:1.25rem;
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
        <div style="color:{COLORS['text_secondary']};font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;font-weight:600;margin-bottom:8px">{label}</div>
        <div style="color:{COLORS['text_primary']};font-size:1.75rem;font-weight:700">{value}</div>
        {delta_html}
    </div>
    '''
    return html


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
    <div style="
        background:{COLORS['secondary']};
        border:1px solid {COLORS['border']};
        border-left:4px solid {color};
        border-radius:8px;
        padding:1rem;
        margin-bottom:8px;
        transition:all 0.2s ease;
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
