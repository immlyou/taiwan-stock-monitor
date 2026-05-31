# -*- coding: utf-8 -*-
"""
投資組合儀表板 - 專注於個人投資組合績效追蹤

首頁已提供市場總覽，此頁面聚焦於：
- 投資組合損益追蹤
- 持股明細與報酬分析
- 選股結果追蹤
"""
import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime


from config import STREAMLIT_CONFIG, CACHE_TTL
from core.data_loader import get_loader, get_data_summary
from core.cache_warmer import warmup_on_startup, is_cache_warm
from core.realtime_quote import fetch_realtime_quotes
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error
from app.components.session_manager import init_session_state
from app.components.page_header import render_page_header, render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.theme import (
    create_kpi_card,
    create_stock_card,
    render_kpi_row,
    responsive_columns,
    create_section_header,
    render_data_table,
    format_number,
    inject_professional_theme,
    COLORS,
)

st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 投資組合",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 初始化 Session State
init_session_state()

# 快取預熱 (僅首次載入)
if not is_cache_warm():
    warmup_on_startup(show_progress=True)

# 注入專業主題
inject_professional_theme()

# 渲染側邊欄
render_sidebar_mini(current_page='dashboard')

# 全域報價跑馬燈
render_global_ticker_bar()


# 資料載入函數
@st.cache_data(ttl=CACHE_TTL['intraday'])
def load_dashboard_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'benchmark': loader.get_benchmark(),
        'stock_info': loader.get_stock_info(),
    }


from app.components.portfolio_utils import load_portfolios

SCREENING_FILE = Path(__file__).parent.parent.parent / 'data' / 'latest_screening.json'
ALERTS_FILE = Path(__file__).parent.parent.parent / 'data' / 'alerts.json'


def load_latest_screening():
    if SCREENING_FILE.exists():
        with open(SCREENING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_alerts():
    if ALERTS_FILE.exists():
        with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'alerts': []}


# ========== 頁面標題 ==========
render_page_header("儀表板", icon="📊")

# 載入資料
try:
    data = load_dashboard_data()
    close = data['close']
    benchmark = data['benchmark']
    stock_info = data['stock_info']
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

portfolios = load_portfolios()
latest_screening = load_latest_screening()
alerts_data = load_alerts()

# ========== 投資組合總覽 (KPI) ==========
st.markdown(create_section_header('投資組合總覽', icon='💼'), unsafe_allow_html=True)

# 判斷是否為盤中時間，若是則取得即時報價
def _is_market_open():
    now = datetime.now()
    return (now.weekday() < 5 and
            datetime.strptime('09:00', '%H:%M').time() <= now.time() <= datetime.strptime('13:30', '%H:%M').time())

is_realtime = _is_market_open()

# 收集所有持股代號
all_stock_ids = []
for portfolio in portfolios.values():
    for holding in portfolio.get('holdings', []):
        sid = holding['stock_id']
        if sid not in all_stock_ids:
            all_stock_ids.append(sid)

# 盤中時段：批次取得即時報價
realtime_prices = {}
if is_realtime and all_stock_ids:
    try:
        quotes = fetch_realtime_quotes(all_stock_ids)
        for sid, q in quotes.items():
            if q.price > 0:
                realtime_prices[sid] = q.price
    except Exception:
        pass  # fallback 到收盤價

# 計算投資組合總值
total_portfolio_value = 0
total_portfolio_cost = 0
all_holdings = []

for portfolio_name, portfolio in portfolios.items():
    for holding in portfolio.get('holdings', []):
        stock_id = holding['stock_id']
        shares = holding['shares']
        cost_price = holding['cost_price']

        if stock_id in close.columns:
            # 優先使用即時報價，fallback 到收盤價
            if stock_id in realtime_prices:
                latest_price = realtime_prices[stock_id]
            else:
                latest_price = close[stock_id].dropna().iloc[-1]
            market_value = shares * latest_price
            cost_value = shares * cost_price
            pnl = market_value - cost_value
            pnl_pct = (latest_price / cost_price - 1) * 100

            total_portfolio_value += market_value
            total_portfolio_cost += cost_value

            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else stock_id

            all_holdings.append({
                'stock_id': stock_id,
                'name': name,
                'portfolio': portfolio_name,
                'shares': shares,
                'cost_price': cost_price,
                'current_price': latest_price,
                'market_value': market_value,
                'cost_value': cost_value,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
            })

# KPI 卡片
total_pnl = total_portfolio_value - total_portfolio_cost
pnl_color = 'up' if total_pnl >= 0 else 'down'

if total_portfolio_cost > 0:
    total_pnl_pct = (total_portfolio_value / total_portfolio_cost - 1) * 100
    pct_color = 'up' if total_pnl_pct >= 0 else 'down'
    return_value = format_number(total_pnl_pct, kind='pct', signed=True)
    return_delta_color = pct_color
else:
    return_value = '-'
    return_delta_color = 'flat'

render_kpi_row([
    {'label': '總市值', 'value': format_number(total_portfolio_value, kind='int')},
    {'label': '總成本', 'value': format_number(total_portfolio_cost, kind='int')},
    {
        'label': '總損益',
        'value': format_number(total_pnl, kind='int', signed=True),
        'delta': '獲利' if total_pnl >= 0 else '虧損',
        'delta_color': pnl_color,
    },
    {'label': '報酬率', 'value': return_value, 'delta_color': return_delta_color},
    {'label': '持股檔數', 'value': format_number(len(all_holdings), kind='int')},
])

# ========== 持股明細 + 損益排行 ==========
if all_holdings:
    st.markdown(create_section_header('持股明細', icon='📋'), unsafe_allow_html=True)

    holdings_df = pd.DataFrame(all_holdings)
    display_df = holdings_df[['stock_id', 'name', 'portfolio', 'shares', 'cost_price', 'current_price', 'pnl', 'pnl_pct']].copy()
    display_df.columns = ['代號', '名稱', '組合', '股數', '成本', '現價', '損益', '報酬%']
    display_df['成本'] = display_df['成本'].apply(lambda x: format_number(x, kind='price'))
    display_df['現價'] = display_df['現價'].apply(lambda x: format_number(x, kind='price'))
    display_df['損益'] = display_df['損益'].apply(lambda x: format_number(x, kind='int', signed=True))
    display_df['報酬%'] = display_df['報酬%'].apply(lambda x: format_number(x, kind='pct', signed=True))

    render_data_table(
        display_df,
        freeze_cols=1,
        numeric_cols=['股數'],
        height=480,
    )

    rank_col, dist_col = st.columns([3, 2])

    def _rank_row(h):
        is_up = h['pnl'] >= 0
        color = COLORS['up'] if is_up else COLORS['down']
        arrow = '▲' if is_up else '▼'
        return (
            f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:13px'>"
            f"<span style='color:{COLORS['text_secondary']}'>{h['stock_id']} {h['name'][:4]}</span>"
            f"<span style='color:{color};font-weight:bold'>{arrow} "
            f"{format_number(h['pnl'], kind='int', signed=True)} "
            f"({format_number(h['pnl_pct'], kind='pct', signed=True)})</span>"
            f"</div>"
        )

    with rank_col:
        # 損益排行
        st.markdown(create_section_header('損益排行', icon='🔥'), unsafe_allow_html=True)
        sorted_holdings = sorted(all_holdings, key=lambda x: x['pnl'], reverse=True)

        st.caption('獲利 Top 5')
        for h in sorted_holdings[:5]:
            st.markdown(_rank_row(h), unsafe_allow_html=True)

        st.markdown('')

        st.caption('虧損 Top 5')
        for h in sorted_holdings[-5:][::-1]:
            st.markdown(_rank_row(h), unsafe_allow_html=True)

    with dist_col:
        # 組合分布
        st.markdown(create_section_header('組合分布', icon='📊'), unsafe_allow_html=True)
        portfolio_summary = holdings_df.groupby('portfolio').agg({
            'market_value': 'sum',
            'stock_id': 'count'
        }).reset_index()

        for _, row in portfolio_summary.iterrows():
            pct = row['market_value'] / total_portfolio_value * 100 if total_portfolio_value > 0 else 0
            st.markdown(f"- {row['portfolio']}: {row['stock_id']}檔 ({pct:.1f}%)")

else:
    show_empty_state('尚無持股資料', icon='📭', suggestion='請至「投資組合」頁面建立投資組合')

    # 顯示快速操作
    col1, col2 = st.columns(2)
    with col1:
        if st.button('📋 建立投資組合', use_container_width=True):
            st.switch_page('pages/8_投資組合.py')
    with col2:
        if st.button('🔍 執行選股', use_container_width=True):
            st.switch_page('pages/1_選股篩選.py')

# ========== 選股結果追蹤 ==========
st.markdown(create_section_header('最新選股結果', icon='🔍'), unsafe_allow_html=True)

if latest_screening and latest_screening.get('stocks'):
    screening_stocks = latest_screening['stocks'][:12]
    screening_date = latest_screening.get('date', '')[:10]
    strategy = latest_screening.get('strategy', '-')

    st.caption(f'策略: {strategy} | 日期: {screening_date} | 共 {len(latest_screening["stocks"])} 檔')

    # 4 欄顯示
    cols = responsive_columns(4)
    for i, stock_id in enumerate(screening_stocks):
        info = stock_info[stock_info['stock_id'] == stock_id]
        name = info['name'].values[0] if len(info) > 0 else ''

        if stock_id in close.columns:
            prices = close[stock_id].dropna()
            if len(prices) >= 2:
                current = prices.iloc[-1]
                prev = prices.iloc[-2]
                change = current - prev
                change_pct = (current / prev - 1) * 100
            else:
                current = prices.iloc[-1] if len(prices) > 0 else 0
                change = 0
                change_pct = 0
        else:
            current = 0
            change = 0
            change_pct = 0

        with cols[i % 4]:
            st.markdown(
                create_stock_card(stock_id, name[:4], current, change, change_pct),
                unsafe_allow_html=True
            )
else:
    show_empty_state('尚未執行選股', icon='🔍', suggestion='前往選股篩選頁面執行選股')
    if st.button('🔍 前往選股', use_container_width=True):
        st.switch_page('pages/1_選股篩選.py')

# ========== 警報狀態 ==========
st.markdown(create_section_header('警報與系統', icon='🔔'), unsafe_allow_html=True)

with st.expander('🔔 警報狀態'):
    alerts = alerts_data.get('alerts', [])
    active_alerts = [a for a in alerts if a.get('enabled', False)]
    triggered_alerts = [a for a in active_alerts if a.get('triggered', False)]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('📋 總警報數', len(alerts))
    with col2:
        st.metric('✅ 啟用中', len(active_alerts))
    with col3:
        st.metric('⚠️ 已觸發', len(triggered_alerts))

    if triggered_alerts:
        st.markdown('**已觸發的警報:**')
        for alert in triggered_alerts[:5]:
            st.warning(f"{alert.get('stock_id', '')} - {alert.get('condition', '')} {alert.get('target_price', '')}")

# ========== 系統資訊 ==========
with st.expander('📊 系統資訊'):
    try:
        summary = get_data_summary()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric('活躍股票', f"{summary.get('total_stocks', '-')} 檔")
        with col2:
            st.metric('交易日數', f"{summary.get('total_days', '-')} 天")
        with col3:
            if is_realtime and realtime_prices:
                st.metric('最新資料', datetime.now().strftime('%Y-%m-%d %H:%M'))
            else:
                date_range = summary.get('date_range', '')
                latest_date = date_range.split(' ~ ')[1] if '~' in date_range else '-'
                st.metric('最新資料', latest_date)
    except Exception:
        show_empty_state('無法取得系統資訊', icon='ℹ️')

if is_realtime and realtime_prices:
    st.caption(f'📡 即時報價中（{len(realtime_prices)}/{len(all_stock_ids)} 檔） | 資料來源: TWSE 即時 API')
else:
    st.caption('資料來源: FinLab API（盤後收盤價）')
