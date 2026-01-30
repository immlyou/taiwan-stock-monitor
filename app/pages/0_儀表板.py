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
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import STREAMLIT_CONFIG
from core.data_loader import get_loader, get_data_summary
from core.cache_warmer import warmup_on_startup, is_cache_warm
from app.components.sidebar import render_sidebar
from app.components.error_handler import show_error, safe_execute, create_error_boundary
from app.components.session_manager import init_session_state

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

# 渲染側邊欄
render_sidebar(current_page='dashboard')


# 資料載入函數
@st.cache_data(ttl=300)
def load_dashboard_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'benchmark': loader.get_benchmark(),
        'stock_info': loader.get_stock_info(),
    }


PORTFOLIO_FILE = Path(__file__).parent.parent.parent / 'data' / 'portfolios.json'
SCREENING_FILE = Path(__file__).parent.parent.parent / 'data' / 'latest_screening.json'
ALERTS_FILE = Path(__file__).parent.parent.parent / 'data' / 'alerts.json'


def load_portfolios():
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


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
title_col1, title_col2 = st.columns([4, 1])

with title_col1:
    st.title('💼 投資組合儀表板')
    st.caption('個人持股績效追蹤與分析')

with title_col2:
    if st.button('🔄 重新整理', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 載入資料
try:
    data = load_dashboard_data()
    close = data['close']
    benchmark = data['benchmark']
    stock_info = data['stock_info']
except Exception as e:
    st.error(f'載入數據失敗: {e}')
    st.stop()

portfolios = load_portfolios()
latest_screening = load_latest_screening()
alerts_data = load_alerts()

# ========== 投資組合總覽 (KPI) ==========
st.markdown('---')

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
kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)

with kpi_col1:
    st.metric('💰 總市值', f'{total_portfolio_value:,.0f}')

with kpi_col2:
    st.metric('💵 總成本', f'{total_portfolio_cost:,.0f}')

with kpi_col3:
    total_pnl = total_portfolio_value - total_portfolio_cost
    delta_color = 'normal' if total_pnl >= 0 else 'inverse'
    st.metric('📊 總損益', f'{total_pnl:+,.0f}', delta_color=delta_color)

with kpi_col4:
    if total_portfolio_cost > 0:
        total_pnl_pct = (total_portfolio_value / total_portfolio_cost - 1) * 100
        delta_color = 'normal' if total_pnl_pct >= 0 else 'inverse'
        st.metric('📈 報酬率', f'{total_pnl_pct:+.2f}%', delta_color=delta_color)
    else:
        st.metric('📈 報酬率', '-')

with kpi_col5:
    st.metric('📋 持股檔數', f'{len(all_holdings)}')

# ========== 持股明細 + 損益排行 ==========
st.markdown('---')

if all_holdings:
    detail_col, rank_col = st.columns([3, 2])

    with detail_col:
        st.markdown('##### 📋 持股明細')

        holdings_df = pd.DataFrame(all_holdings)
        display_df = holdings_df[['stock_id', 'name', 'portfolio', 'shares', 'cost_price', 'current_price', 'pnl', 'pnl_pct']].copy()
        display_df.columns = ['代號', '名稱', '組合', '股數', '成本', '現價', '損益', '報酬%']
        display_df['成本'] = display_df['成本'].apply(lambda x: f'{x:.2f}')
        display_df['現價'] = display_df['現價'].apply(lambda x: f'{x:.2f}')
        display_df['損益'] = display_df['損益'].apply(lambda x: f'{x:+,.0f}')
        display_df['報酬%'] = display_df['報酬%'].apply(lambda x: f'{x:+.2f}%')

        st.dataframe(display_df, use_container_width=True, hide_index=True, height=350)

    with rank_col:
        # 獲利排行
        st.markdown('##### 🔥 獲利 Top 5')
        sorted_holdings = sorted(all_holdings, key=lambda x: x['pnl'], reverse=True)
        for h in sorted_holdings[:5]:
            color = '#ef5350' if h['pnl'] >= 0 else '#26a69a'
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:13px'>"
                f"<span>{h['stock_id']} {h['name'][:4]}</span>"
                f"<span style='color:{color};font-weight:bold'>{h['pnl']:+,.0f} ({h['pnl_pct']:+.1f}%)</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.markdown('')

        # 虧損排行
        st.markdown('##### 💧 虧損 Top 5')
        for h in sorted_holdings[-5:][::-1]:
            color = '#ef5350' if h['pnl'] >= 0 else '#26a69a'
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:13px'>"
                f"<span>{h['stock_id']} {h['name'][:4]}</span>"
                f"<span style='color:{color};font-weight:bold'>{h['pnl']:+,.0f} ({h['pnl_pct']:+.1f}%)</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.markdown('')

        # 組合分布
        st.markdown('##### 📊 組合分布')
        portfolio_summary = holdings_df.groupby('portfolio').agg({
            'market_value': 'sum',
            'stock_id': 'count'
        }).reset_index()

        for _, row in portfolio_summary.iterrows():
            pct = row['market_value'] / total_portfolio_value * 100 if total_portfolio_value > 0 else 0
            st.markdown(f"- {row['portfolio']}: {row['stock_id']}檔 ({pct:.1f}%)")

else:
    st.info('尚無持股資料。請至「投資組合」頁面建立投資組合。')

    # 顯示快速操作
    col1, col2 = st.columns(2)
    with col1:
        if st.button('📋 建立投資組合', use_container_width=True):
            st.switch_page('pages/8_投資組合.py')
    with col2:
        if st.button('🔍 執行選股', use_container_width=True):
            st.switch_page('pages/1_選股篩選.py')

# ========== 選股結果追蹤 ==========
st.markdown('---')
st.markdown('##### 🔍 最新選股結果')

if latest_screening and latest_screening.get('stocks'):
    screening_stocks = latest_screening['stocks'][:12]
    screening_date = latest_screening.get('date', '')[:10]
    strategy = latest_screening.get('strategy', '-')

    st.caption(f'策略: {strategy} | 日期: {screening_date} | 共 {len(latest_screening["stocks"])} 檔')

    # 3 欄顯示
    cols = st.columns(4)
    for i, stock_id in enumerate(screening_stocks):
        info = stock_info[stock_info['stock_id'] == stock_id]
        name = info['name'].values[0] if len(info) > 0 else ''

        if stock_id in close.columns:
            prices = close[stock_id].dropna()
            if len(prices) >= 2:
                current = prices.iloc[-1]
                prev = prices.iloc[-2]
                change_pct = (current / prev - 1) * 100
                color = '#ef5350' if change_pct >= 0 else '#26a69a'
            else:
                current = prices.iloc[-1] if len(prices) > 0 else 0
                change_pct = 0
                color = '#888'
        else:
            current = 0
            change_pct = 0
            color = '#888'

        with cols[i % 4]:
            st.markdown(
                f"<div style='background:#f8f9fa;padding:8px;border-radius:6px;margin-bottom:8px'>"
                f"<div style='font-size:12px;color:#666'>{stock_id} {name[:4]}</div>"
                f"<div style='font-size:16px;font-weight:bold;color:{color}'>{current:,.2f}</div>"
                f"<div style='font-size:11px;color:{color}'>{change_pct:+.2f}%</div>"
                f"</div>",
                unsafe_allow_html=True
            )
else:
    st.info('尚未執行選股。')
    if st.button('🔍 前往選股', use_container_width=True):
        st.switch_page('pages/1_選股篩選.py')

# ========== 警報狀態 ==========
st.markdown('---')

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
            date_range = summary.get('date_range', '')
            latest_date = date_range.split(' ~ ')[1] if '~' in date_range else '-'
            st.metric('最新資料', latest_date)
    except Exception:
        st.info('無法取得系統資訊')

st.caption('資料來源: FinLab API')
