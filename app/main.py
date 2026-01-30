# -*- coding: utf-8 -*-
"""
台股分析系統 - 專業戰情中心

整合大盤、法人、熱力圖、即時報價於單一頁面
採用專業金融風格設計
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import datetime

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import STREAMLIT_CONFIG
from core.data_loader import get_loader, get_data_summary, reset_all_caches
from core.realtime_quote import fetch_realtime_quotes
from core.twse_api import get_taiex
from core.cache_warmer import warmup_on_startup, is_cache_warm, get_cache_warmer
from app.components.sidebar import render_sidebar
from app.components.theme import (
    inject_professional_theme,
    create_kpi_card,
    create_section_header,
    create_stock_card,
    COLORS,
    DEFAULT_PLOTLY_LAYOUT,
)
from app.components.session_manager import init_session_state

# 頁面設定 - 使用寬版面
st.set_page_config(
    page_title=STREAMLIT_CONFIG['page_title'],
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)


# ========== 密碼驗證 ==========
def check_password():
    """驗證使用者密碼"""
    def password_entered():
        if st.session_state["password"] == st.secrets["passwords"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh">
            <div style="text-align:center;margin-bottom:2rem">
                <span style="font-size:4rem">📊</span>
                <h1 style="margin:1rem 0 0.5rem 0;font-size:2rem">台股戰情中心</h1>
                <p style="color:#888;font-size:0.9rem">Taiwan Stock Command Center</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("🔐 請輸入密碼", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh">
            <div style="text-align:center;margin-bottom:2rem">
                <span style="font-size:4rem">📊</span>
                <h1 style="margin:1rem 0 0.5rem 0;font-size:2rem">台股戰情中心</h1>
                <p style="color:#888;font-size:0.9rem">Taiwan Stock Command Center</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("🔐 請輸入密碼", type="password", on_change=password_entered, key="password")
            st.error("❌ 密碼錯誤，請重試")
        return False
    else:
        return True


if not check_password():
    st.stop()


# 初始化 Session State
init_session_state()

# 快取預熱 - 首頁作為主要進入點，自動執行預熱
if not is_cache_warm():
    warmup_on_startup(show_progress=True)

# 注入專業主題
inject_professional_theme()

# 渲染側邊欄
render_sidebar(current_page='home')


@st.cache_data(ttl=300)
def load_market_overview():
    """載入市場總覽資料"""
    loader = get_loader()
    data = {}

    # 收盤價
    close = loader.get('close')
    if close is not None and len(close) > 0:
        data['close'] = close
        data['latest_date'] = close.index[-1].strftime('%Y-%m-%d')

        # 計算漲跌幅
        if len(close) > 1:
            change_pct = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).fillna(0)
            data['change_pct'] = change_pct

            # 市場統計
            data['up_count'] = (change_pct > 0).sum()
            data['down_count'] = (change_pct < 0).sum()
            data['flat_count'] = (change_pct == 0).sum()
            data['limit_up'] = (change_pct >= 9.5).sum()
            data['limit_down'] = (change_pct <= -9.5).sum()

    # 市值
    market_value = loader.get('market_value')
    if market_value is not None and len(market_value) > 0:
        data['market_value'] = market_value.iloc[-1]

    # 三大法人
    try:
        foreign = loader.get('foreign_investors')
        if foreign is not None and len(foreign) > 0:
            data['foreign_total'] = foreign.iloc[-1].sum() / 1000  # 轉為張
    except:
        data['foreign_total'] = None

    try:
        trust = loader.get('investment_trust')
        if trust is not None and len(trust) > 0:
            data['trust_total'] = trust.iloc[-1].sum() / 1000
    except:
        data['trust_total'] = None

    try:
        dealer = loader.get('dealer')
        if dealer is not None and len(dealer) > 0:
            data['dealer_total'] = dealer.iloc[-1].sum() / 1000
    except:
        data['dealer_total'] = None

    # 股票資訊
    data['stock_info'] = loader.get_stock_info()

    return data


def create_mini_heatmap(close_df, change_pct, market_value, stock_info, top_n=50):
    """建立專業熱力圖"""
    if close_df is None or change_pct is None:
        return None

    # 取市值前 N 大
    if market_value is not None:
        top_stocks = market_value.nlargest(top_n).index.tolist()
    else:
        top_stocks = change_pct.index[:top_n].tolist()

    data = []
    for stock_id in top_stocks:
        if stock_id not in change_pct.index:
            continue

        chg = change_pct.get(stock_id, 0)
        if pd.isna(chg):
            chg = 0

        mv = market_value.get(stock_id, 1) if market_value is not None else 1
        if pd.isna(mv) or mv <= 0:
            mv = 1

        # 股票名稱
        info = stock_info[stock_info['stock_id'] == stock_id] if stock_info is not None else None
        name = info['name'].values[0] if info is not None and len(info) > 0 else stock_id

        data.append({
            'stock_id': stock_id,
            'name': name,
            'change_pct': chg,
            'market_value': mv,
            'display': f"{stock_id}<br>{chg:+.1f}%",
        })

    if not data:
        return None

    df = pd.DataFrame(data)
    df['change_pct_clipped'] = df['change_pct'].clip(-7, 7)

    # 自訂漲跌色系
    colorscale = [
        [0.0, '#22c55e'],    # 深綠 (大跌)
        [0.3, '#4ade80'],    # 淺綠
        [0.45, '#94a3b8'],   # 灰色
        [0.55, '#94a3b8'],   # 灰色
        [0.7, '#f87171'],    # 淺紅
        [1.0, '#ef4444'],    # 深紅 (大漲)
    ]

    fig = px.treemap(
        df,
        path=['display'],
        values='market_value',
        color='change_pct_clipped',
        color_continuous_scale=colorscale,
        range_color=[-5, 5],
    )

    fig.update_layout(
        margin=dict(t=10, l=5, r=5, b=5),
        height=300,
        coloraxis_showscale=False,
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': COLORS['text_primary']},
    )

    fig.update_traces(
        textfont=dict(size=11, color='white'),
        hovertemplate='<b>%{label}</b><extra></extra>',
        marker=dict(cornerradius=5),
    )

    return fig


def create_market_gauge(up_count, down_count, total):
    """建立市場情緒儀表"""
    if total == 0:
        return None

    up_pct = up_count / total * 100

    # 決定狀態
    if up_pct >= 60:
        color = COLORS['up']
        status = '偏多'
        status_color = COLORS['up']
    elif up_pct <= 40:
        color = COLORS['down']
        status = '偏空'
        status_color = COLORS['down']
    else:
        color = '#fbbf24'
        status = '中性'
        status_color = '#fbbf24'

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=up_pct,
        number={
            'suffix': '%',
            'font': {'size': 32, 'color': COLORS['text_primary'], 'family': 'Inter'}
        },
        gauge={
            'axis': {
                'range': [0, 100],
                'tickwidth': 1,
                'tickcolor': COLORS['border'],
                'tickfont': {'color': COLORS['text_muted'], 'size': 10},
            },
            'bar': {'color': color, 'thickness': 0.8},
            'bgcolor': COLORS['secondary'],
            'borderwidth': 0,
            'steps': [
                {'range': [0, 40], 'color': 'rgba(34, 197, 94, 0.15)'},
                {'range': [40, 60], 'color': 'rgba(251, 191, 36, 0.15)'},
                {'range': [60, 100], 'color': 'rgba(239, 68, 68, 0.15)'},
            ],
        },
        title={
            'text': f"市場情緒<br><span style='font-size:16px;color:{status_color};font-weight:600'>{status}</span>",
            'font': {'color': COLORS['text_secondary'], 'size': 14}
        }
    ))

    fig.update_layout(
        margin=dict(t=80, l=30, r=30, b=20),
        height=220,
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Inter, -apple-system, sans-serif'},
    )

    return fig


# ========== 頁面標題區 ==========
header_col1, header_col2, header_col3 = st.columns([3, 1, 1])

with header_col1:
    st.markdown(f'''
    <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:2.5rem">📊</span>
        <div>
            <h1 style="margin:0;padding:0;border:none;font-size:1.8rem;color:{COLORS['text_primary']}">台股戰情中心</h1>
            <p style="margin:0;color:{COLORS['text_muted']};font-size:0.85rem">Taiwan Stock Command Center</p>
        </div>
    </div>
    ''', unsafe_allow_html=True)

with header_col2:
    # 載入資料
    data = load_market_overview()
    latest_date = data.get('latest_date', '-')
    st.markdown(f'''
    <div style="text-align:right;padding-top:12px">
        <span style="color:{COLORS['text_muted']};font-size:0.8rem">📅 資料日期</span><br>
        <span style="color:{COLORS['text_primary']};font-size:1rem;font-weight:600">{latest_date}</span>
    </div>
    ''', unsafe_allow_html=True)

with header_col3:
    st.markdown('<div style="padding-top:8px">', unsafe_allow_html=True)
    if st.button('🔄 重新整理', use_container_width=True):
        st.cache_data.clear()
        reset_all_caches()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div style="margin-bottom:1.5rem"></div>', unsafe_allow_html=True)

# ========== 第一行：關鍵指標 KPI ==========
st.markdown(create_section_header('關鍵指標', '📈'), unsafe_allow_html=True)

kpi_cols = st.columns(6)

# 加權指數
with kpi_cols[0]:
    taiex_index, taiex_change, _ = get_taiex()
    if taiex_index:
        delta_color = 'up' if taiex_change and taiex_change >= 0 else 'down'
        st.markdown(create_kpi_card(
            '加權指數',
            f'{taiex_index:,.0f}',
            f'{taiex_change:+.2f}%' if taiex_change else None,
            delta_color
        ), unsafe_allow_html=True)
    else:
        st.markdown(create_kpi_card('加權指數', '載入中...'), unsafe_allow_html=True)

# 上漲/下跌
with kpi_cols[1]:
    up = data.get('up_count', 0)
    down = data.get('down_count', 0)
    delta_color = 'up' if up > down else 'down' if down > up else 'flat'
    st.markdown(create_kpi_card(
        '上漲家數',
        f'{up:,}',
        f'下跌 {down:,}',
        delta_color
    ), unsafe_allow_html=True)

# 漲停/跌停
with kpi_cols[2]:
    limit_up = data.get('limit_up', 0)
    limit_down = data.get('limit_down', 0)
    delta_color = 'up' if limit_up > limit_down else 'down' if limit_down > limit_up else 'flat'
    st.markdown(create_kpi_card(
        '漲停家數',
        f'{limit_up:,}',
        f'跌停 {limit_down:,}',
        delta_color
    ), unsafe_allow_html=True)

# 外資
with kpi_cols[3]:
    foreign = data.get('foreign_total')
    if foreign is not None:
        delta_color = 'up' if foreign >= 0 else 'down'
        st.markdown(create_kpi_card(
            '外資',
            f'{foreign/10000:+,.1f}萬張',
            '買超' if foreign >= 0 else '賣超',
            delta_color
        ), unsafe_allow_html=True)
    else:
        st.markdown(create_kpi_card('外資', '-'), unsafe_allow_html=True)

# 投信
with kpi_cols[4]:
    trust = data.get('trust_total')
    if trust is not None:
        delta_color = 'up' if trust >= 0 else 'down'
        st.markdown(create_kpi_card(
            '投信',
            f'{trust/10000:+,.1f}萬張',
            '買超' if trust >= 0 else '賣超',
            delta_color
        ), unsafe_allow_html=True)
    else:
        st.markdown(create_kpi_card('投信', '-'), unsafe_allow_html=True)

# 自營商
with kpi_cols[5]:
    dealer = data.get('dealer_total')
    if dealer is not None:
        delta_color = 'up' if dealer >= 0 else 'down'
        st.markdown(create_kpi_card(
            '自營商',
            f'{dealer/10000:+,.1f}萬張',
            '買超' if dealer >= 0 else '賣超',
            delta_color
        ), unsafe_allow_html=True)
    else:
        st.markdown(create_kpi_card('自營商', '-'), unsafe_allow_html=True)

st.markdown('<div style="margin-bottom:2rem"></div>', unsafe_allow_html=True)

# ========== 第二行：市場情緒 + 熱力圖 + 即時報價 ==========
row2_col1, row2_col2, row2_col3 = st.columns([1, 2, 2])

# 市場情緒儀表
with row2_col1:
    st.markdown(create_section_header('市場情緒', '🎯'), unsafe_allow_html=True)

    up = data.get('up_count', 0)
    down = data.get('down_count', 0)
    total = up + down + data.get('flat_count', 0)

    if total > 0:
        fig = create_market_gauge(up, down, total)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # 額外統計
        st.markdown(f'''
        <div style="background:{COLORS['secondary']};border-radius:8px;padding:12px;margin-top:-10px">
            <div style="display:flex;justify-content:space-around;text-align:center">
                <div>
                    <div style="color:{COLORS['up']};font-size:1.2rem;font-weight:700">{up}</div>
                    <div style="color:{COLORS['text_muted']};font-size:0.7rem">上漲</div>
                </div>
                <div style="border-left:1px solid {COLORS['border']};padding-left:12px">
                    <div style="color:{COLORS['flat']};font-size:1.2rem;font-weight:700">{data.get('flat_count', 0)}</div>
                    <div style="color:{COLORS['text_muted']};font-size:0.7rem">平盤</div>
                </div>
                <div style="border-left:1px solid {COLORS['border']};padding-left:12px">
                    <div style="color:{COLORS['down']};font-size:1.2rem;font-weight:700">{down}</div>
                    <div style="color:{COLORS['text_muted']};font-size:0.7rem">下跌</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.info('無資料')

# 熱力圖
with row2_col2:
    st.markdown(create_section_header('權值股熱力圖', '🗺️'), unsafe_allow_html=True)

    close = data.get('close')
    change_pct = data.get('change_pct')
    mv = data.get('market_value')
    stock_info = data.get('stock_info')

    if close is not None and change_pct is not None:
        fig = create_mini_heatmap(close, change_pct, mv, stock_info, top_n=50)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info('無法載入熱力圖')
    else:
        st.info('無資料')

    if st.button('🗺️ 查看完整熱力圖', use_container_width=True, key='btn_heatmap'):
        st.switch_page('pages/18_市場熱力圖.py')

# 即時報價
with row2_col3:
    st.markdown(create_section_header('熱門股即時報價', '💹'), unsafe_allow_html=True)

    hot_stocks = ['2330', '2317', '2454', '2881', '0050', '2303']

    try:
        quotes = fetch_realtime_quotes(hot_stocks, use_cache=True)

        if quotes:
            for stock_id in hot_stocks:
                if stock_id in quotes:
                    q = quotes[stock_id]
                    st.markdown(create_stock_card(
                        stock_id=q.stock_id,
                        name=q.name,
                        price=q.price,
                        change=q.change,
                        change_pct=q.change_pct,
                        extra_info=f'成交量: {q.volume_lots:,} 張'
                    ), unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div style="background:{COLORS['secondary']};border-radius:8px;padding:2rem;text-align:center">
                <div style="color:{COLORS['text_muted']};font-size:0.9rem">⏰ 非交易時段</div>
            </div>
            ''', unsafe_allow_html=True)

    except Exception as e:
        st.warning('報價載入失敗')

    if st.button('💹 查看更多即時報價', use_container_width=True, key='btn_quote'):
        st.switch_page('pages/17_即時報價.py')

st.markdown('<div style="margin-bottom:2rem"></div>', unsafe_allow_html=True)

# ========== 第三行：排行榜 ==========
st.markdown(create_section_header('今日排行', '🏆'), unsafe_allow_html=True)

row3_col1, row3_col2, row3_col3 = st.columns(3)


def create_ranking_table(title: str, data_rows: list, icon: str = '📊'):
    """建立排行榜表格"""
    rows_html = ''
    for i, row in enumerate(data_rows[:10], 1):
        # 排名顏色
        if i <= 3:
            rank_color = COLORS['up'] if i == 1 else '#fbbf24' if i == 2 else '#fb923c'
            rank_bg = f'rgba({239 if i==1 else 251 if i==2 else 251}, {68 if i==1 else 191 if i==2 else 146}, {68 if i==1 else 36 if i==2 else 60}, 0.2)'
        else:
            rank_color = COLORS['text_muted']
            rank_bg = 'transparent'

        # 值的顏色
        value = row.get('value', 0)
        if isinstance(value, str):
            val_color = COLORS['up'] if '+' in value else COLORS['down'] if '-' in value else COLORS['text_primary']
        else:
            val_color = COLORS['up'] if value > 0 else COLORS['down'] if value < 0 else COLORS['text_primary']

        rows_html += f'''
        <tr style="border-bottom:1px solid {COLORS['border']}">
            <td style="padding:10px 8px;width:40px">
                <span style="background:{rank_bg};color:{rank_color};padding:2px 8px;border-radius:4px;font-size:0.8rem;font-weight:600">{i}</span>
            </td>
            <td style="padding:10px 8px">
                <span style="color:{COLORS['text_primary']};font-weight:600">{row.get('code', '')}</span>
                <span style="color:{COLORS['text_secondary']};font-size:0.8rem;margin-left:6px">{row.get('name', '')}</span>
            </td>
            <td style="padding:10px 8px;text-align:right">
                <span style="color:{val_color};font-weight:600">{row.get('display', '')}</span>
            </td>
        </tr>
        '''

    return f'''
    <div style="background:{COLORS['secondary']};border-radius:12px;overflow:hidden;border:1px solid {COLORS['border']}">
        <div style="background:{COLORS['primary']};padding:12px 16px;border-bottom:1px solid {COLORS['border']}">
            <span style="color:{COLORS['text_primary']};font-weight:600">{icon} {title}</span>
        </div>
        <table style="width:100%;border-collapse:collapse">
            {rows_html}
        </table>
    </div>
    '''


# 今日漲幅榜
with row3_col1:
    change_pct = data.get('change_pct')
    stock_info = data.get('stock_info')

    if change_pct is not None and stock_info is not None:
        top_gainers = change_pct.nlargest(10)
        rows = []
        for stock_id, chg in top_gainers.items():
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''
            rows.append({
                'code': stock_id,
                'name': name,
                'value': chg,
                'display': f'{chg:+.2f}%'
            })

        st.markdown(create_ranking_table('今日漲幅 TOP 10', rows, '🔥'), unsafe_allow_html=True)
    else:
        st.info('無資料')

# 外資買超榜
with row3_col2:
    try:
        loader = get_loader()
        foreign = loader.get('foreign_investors')
        stock_info = data.get('stock_info')

        if foreign is not None and len(foreign) > 0 and stock_info is not None:
            latest = foreign.iloc[-1] / 1000  # 張
            top_foreign = latest.nlargest(10)
            rows = []
            for stock_id, val in top_foreign.items():
                if pd.isna(val):
                    continue
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''
                rows.append({
                    'code': stock_id,
                    'name': name,
                    'value': val,
                    'display': f'{val:+,.0f}張'
                })

            st.markdown(create_ranking_table('外資買超 TOP 10', rows, '🌍'), unsafe_allow_html=True)
        else:
            st.info('無法人資料')
    except:
        st.info('無法人資料')

# 投信買超榜
with row3_col3:
    try:
        loader = get_loader()
        trust = loader.get('investment_trust')
        stock_info = data.get('stock_info')

        if trust is not None and len(trust) > 0 and stock_info is not None:
            latest = trust.iloc[-1] / 1000
            top_trust = latest.nlargest(10)
            rows = []
            for stock_id, val in top_trust.items():
                if pd.isna(val):
                    continue
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''
                rows.append({
                    'code': stock_id,
                    'name': name,
                    'value': val,
                    'display': f'{val:+,.0f}張'
                })

            st.markdown(create_ranking_table('投信買超 TOP 10', rows, '🏦'), unsafe_allow_html=True)
        else:
            st.info('無法人資料')
    except:
        st.info('無法人資料')

st.markdown('<div style="margin-bottom:2rem"></div>', unsafe_allow_html=True)

# ========== 第四行：快速操作 ==========
st.markdown(create_section_header('快速操作', '⚡'), unsafe_allow_html=True)

action_cols = st.columns(5)

action_buttons = [
    ('🔍 選股篩選', 'pages/1_選股篩選.py'),
    ('📊 回測分析', 'pages/2_回測分析.py'),
    ('💸 資金流向', 'pages/19_資金流向.py'),
    ('📋 盤後總覽', 'pages/20_盤後總覽.py'),
    ('⭐ 自選股', 'pages/10_自選股.py'),
]

for i, (label, page) in enumerate(action_buttons):
    with action_cols[i]:
        if st.button(label, use_container_width=True, key=f'action_{i}'):
            st.switch_page(page)

# ========== 說明 (折疊) ==========
st.markdown('<div style="margin-top:2rem"></div>', unsafe_allow_html=True)

with st.expander('📖 系統說明', expanded=False):
    st.markdown(f'''
    <div style="color:{COLORS['text_secondary']}">

    ### 選股策略說明

    | 策略 | 說明 | 主要指標 |
    |------|------|----------|
    | **價值投資** | 尋找被低估的股票 | 本益比、股價淨值比、殖利率 |
    | **成長投資** | 尋找高成長股票 | 營收年增率、營收月增率 |
    | **動能投資** | 尋找強勢股票 | 價格突破、成交量、RSI |
    | **綜合策略** | 結合多種因子 | 價值+成長+動能加權評分 |

    ### 使用提示
    1. 使用左側選單進入各功能頁面
    2. 選股結果僅供參考，投資前請自行研究
    3. 回測結果不代表未來績效

    </div>
    ''', unsafe_allow_html=True)

# Footer
st.markdown(f'''
<div style="margin-top:3rem;padding-top:1.5rem;border-top:1px solid {COLORS['border']};text-align:center">
    <p style="color:{COLORS['text_muted']};font-size:0.8rem;margin:0">
        此系統僅供學習研究使用，不構成任何投資建議
    </p>
</div>
''', unsafe_allow_html=True)
