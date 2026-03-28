# -*- coding: utf-8 -*-
"""
AI 異常警報 - 自動偵測股票異常訊號並提供 AI 解讀
"""
import streamlit as st
import pandas as pd
from datetime import datetime

from config import STREAMLIT_CONFIG, CACHE_TTL
from core.data_loader import get_loader
from core.ai_models import AnomalyDetector
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.theme import COLORS, create_kpi_card

st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - AI 異常警報",
    page_icon='⚠️',
    layout='wide',
)

render_sidebar_mini(current_page='ai_anomaly')
render_page_header('AI 異常警報', icon='⚠️')

st.caption('自動偵測爆量、跳空、法人轉向、連續漲跌停等異常訊號')

# 資料載入
@st.cache_data(ttl=CACHE_TTL['intraday'])
def load_data():
    loader = get_loader()
    return loader

# 掃描設定
st.markdown('---')

col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    scan_scope = st.selectbox('掃描範圍', ['自選股', '全市場（前 500 大）'], index=0)
with col_cfg2:
    enable_ai = st.checkbox('啟用 AI 解讀', value=True)

# 載入自選股
watchlist_ids = []
if scan_scope == '自選股':
    try:
        from app.components.watchlist_utils import load_watchlists
        watchlists = load_watchlists()
        for wl in watchlists.values():
            for s in wl.get('stocks', []):
                sid = s if isinstance(s, str) else s.get('stock_id', '')
                if sid and sid not in watchlist_ids:
                    watchlist_ids.append(sid)
    except Exception:
        pass

    # 也加入持倉的股票
    try:
        from app.components.portfolio_utils import load_portfolios
        portfolios = load_portfolios()
        for p in portfolios.values():
            for h in p.get('holdings', []):
                sid = h.get('stock_id', '')
                if sid and sid not in watchlist_ids:
                    watchlist_ids.append(sid)
    except Exception:
        pass

if st.button('🔍 開始掃描異常', type='primary', use_container_width=True):
    with st.spinner('正在掃描異常訊號...'):
        try:
            loader = load_data()
            detector = AnomalyDetector()

            stock_ids = watchlist_ids if scan_scope == '自選股' and watchlist_ids else None
            anomalies = detector.detect(loader, stock_ids)

            st.session_state['anomalies'] = anomalies

            # AI 解讀
            if enable_ai and anomalies:
                with st.spinner('AI 正在解讀異常訊號...'):
                    explanation = detector.explain(anomalies)
                    st.session_state['anomaly_explanation'] = explanation
        except Exception as e:
            show_error(e, title='掃描失敗')

# 顯示結果
if 'anomalies' in st.session_state:
    anomalies = st.session_state['anomalies']

    st.markdown('---')

    # KPI
    high_count = sum(1 for a in anomalies if a['severity'] == 'high')
    medium_count = sum(1 for a in anomalies if a['severity'] == 'medium')

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric('⚠️ 異常總數', len(anomalies))
    with kpi2:
        st.metric('🔴 高度異常', high_count)
    with kpi3:
        st.metric('🟡 中度異常', medium_count)

    # AI 解讀
    if 'anomaly_explanation' in st.session_state and st.session_state['anomaly_explanation']:
        st.markdown('---')
        st.markdown('##### 🤖 AI 解讀')
        st.info(st.session_state['anomaly_explanation'])

    # 異常列表
    st.markdown('---')
    st.markdown('##### 📋 異常訊號明細')

    if anomalies:
        for a in anomalies:
            severity_icon = '🔴' if a['severity'] == 'high' else '🟡'
            type_icons = {
                '爆量': '📊', '跳空上漲': '⬆️', '跳空下跌': '⬇️',
                '外資轉賣': '🏦', '外資轉買': '🏦',
                '連續漲停': '🚀', '連續跌停': '💥',
            }
            icon = type_icons.get(a['anomaly_type'], '⚡')

            st.markdown(
                f"{severity_icon} {icon} **{a['stock_id']} {a.get('name', '')}** — "
                f"{a['anomaly_type']}：{a['description']}"
            )
    else:
        show_empty_state('目前沒有偵測到異常訊號', icon='✅', suggestion='市場正常運作中')

st.markdown('---')
st.caption('偵測邏輯：爆量(>3x均量)、跳空(>3%)、法人轉向、連續漲跌停')
