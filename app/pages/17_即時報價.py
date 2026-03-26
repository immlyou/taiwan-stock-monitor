# -*- coding: utf-8 -*-
"""
即時報價頁面 - 優化版

整合個股查詢、自選股報價於單一頁面，提高資訊密度
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
import json


from config import STREAMLIT_CONFIG
from core.realtime_quote import (
    fetch_realtime_quote,
    fetch_realtime_quotes,
    clear_quote_cache,
    StockQuote,
)
from core.twse_api import get_taiex, fetch_taiex_realtime
from core.data_loader import get_loader
from app.components.sidebar import render_sidebar
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state

# 頁面設定
st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 即時報價",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 渲染側邊欄
render_sidebar(current_page='realtime_quote')

# 取得股票資訊
try:
    loader = get_loader()
    stock_info = loader.get_stock_info()
except Exception:
    stock_info = None


def format_compact_quote(quote: StockQuote):
    """格式化緊湊報價卡片"""
    if quote.is_up:
        color = '#ef4444'
        arrow = '▲'
        bg = 'rgba(239, 83, 80, 0.05)'
    elif quote.is_down:
        color = '#22c55e'
        arrow = '▼'
        bg = 'rgba(38, 166, 154, 0.05)'
    else:
        color = '#888'
        arrow = '─'
        bg = '#252b3d;border:1px solid #374151'

    limit_tag = ''
    if quote.is_limit_up:
        limit_tag = '<span style="color:#fff;background:#ef4444;padding:1px 4px;border-radius:3px;font-size:10px;margin-left:4px">漲停</span>'
    elif quote.is_limit_down:
        limit_tag = '<span style="color:#fff;background:#22c55e;padding:1px 4px;border-radius:3px;font-size:10px;margin-left:4px">跌停</span>'

    # 使用單行 HTML 避免 Streamlit markdown 解析問題
    html = f'<div style="background:{bg};padding:12px;border-radius:8px;margin-bottom:8px;border-left:4px solid {color}">'
    html += f'<div style="display:flex;justify-content:space-between;align-items:center">'
    html += f'<div><span style="font-weight:bold;font-size:14px">{quote.stock_id}</span>'
    html += f'<span style="color:#94a3b8;font-size:12px;margin-left:4px">{quote.name}</span>{limit_tag}</div>'
    html += f'<span style="font-size:11px;color:#94a3b8">{quote.time}</span></div>'
    html += f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:8px">'
    html += f'<span style="font-size:22px;font-weight:bold;color:{color}">{quote.price:,.2f}</span>'
    html += f'<span style="font-size:14px;color:{color}">{arrow} {quote.change:+.2f} ({quote.change_pct:+.2f}%)</span></div>'
    html += f'<div style="display:flex;justify-content:space-between;margin-top:8px;font-size:11px;color:#94a3b8">'
    html += f'<span>開:{quote.open:,.1f}</span><span>高:{quote.high:,.1f}</span>'
    html += f'<span>低:{quote.low:,.1f}</span><span>量:{quote.volume_lots:,}張</span></div></div>'
    return html


from app.components.watchlist_utils import load_watchlists as load_watchlist


# ========== 頁面標題 ==========
render_page_header('即時報價', icon='💹')

# ========== 第一行：大盤指數 + 個股查詢 ==========
st.markdown('---')

row1_col1, row1_col2 = st.columns([1, 3])

# 大盤指數
with row1_col1:
    st.markdown('##### 大盤指數')
    taiex_data = fetch_taiex_realtime()
    if taiex_data:
        taiex_index = taiex_data['index']
        taiex_change = taiex_data.get('change', 0)
        taiex_change_pct = taiex_data.get('change_pct', 0)

        delta_color = 'normal' if taiex_change >= 0 else 'inverse'
        st.metric(
            '加權指數',
            f"{taiex_index:,.2f}",
            f"{taiex_change:+,.2f} ({taiex_change_pct:+.2f}%)",
            delta_color=delta_color,
        )
        st.caption(f"日期: {taiex_data.get('date', '-')}")
    else:
        st.metric('加權指數', '載入中...')

# 個股查詢
with row1_col2:
    st.markdown('##### 個股查詢')

    search_col1, search_col2 = st.columns([4, 1])

    with search_col1:
        stock_input = st.text_input(
            '輸入股票代號或名稱',
            placeholder='例如: 2330 或 台積電',
            key='stock_search',
            label_visibility='collapsed',
        )

    with search_col2:
        search_clicked = st.button('🔍 查詢', type='primary', use_container_width=True, key='search_btn')

    # 快速選擇
    quick_stocks = [('2330', '台積電'), ('2317', '鴻海'), ('2454', '聯發科'), ('0050', '元大50'), ('2881', '富邦金'), ('2303', '聯電')]
    quick_cols = st.columns(6)

    selected_quick = None
    for i, (sid, sname) in enumerate(quick_stocks):
        with quick_cols[i]:
            if st.button(f'{sid}', key=f'quick_{sid}', use_container_width=True, help=sname):
                selected_quick = sid

    # 查詢結果
    search_stock = selected_quick or (stock_input.strip() if search_clicked and stock_input else None)

    if search_stock:
        # 解析股票代號
        if not search_stock.isdigit() and stock_info is not None:
            matches = stock_info[stock_info['name'].str.contains(search_stock, na=False)]
            if len(matches) > 0:
                search_stock = matches.iloc[0]['stock_id']

        quote = fetch_realtime_quote(search_stock, use_cache=False)

        if quote:
            st.markdown(format_compact_quote(quote), unsafe_allow_html=True)
        else:
            st.warning(f'找不到 {search_stock}')

# ========== 第二行：自選股報價 + 熱門股報價 ==========
st.markdown('---')

row2_col1, row2_col2 = st.columns(2)

# 自選股報價
with row2_col1:
    st.markdown('##### ⭐ 自選股報價')

    watchlists = load_watchlist()

    if watchlists:
        list_names = list(watchlists.keys())
        selected_list = st.selectbox('選擇清單', list_names, key='watchlist_select', label_visibility='collapsed')

        if selected_list and selected_list in watchlists:
            # 支援兩種格式：{"清單": ["股票"]} 或 {"清單": {"stocks": ["股票"]}}
            watchlist_data = watchlists[selected_list]
            if isinstance(watchlist_data, dict):
                stock_ids = watchlist_data.get('stocks', [])
            else:
                stock_ids = watchlist_data if isinstance(watchlist_data, list) else []

            if stock_ids:
                quotes = fetch_realtime_quotes(stock_ids[:12], use_cache=True)  # 最多 12 支

                if quotes:
                    # 統計
                    up_count = sum(1 for q in quotes.values() if q.is_up)
                    down_count = sum(1 for q in quotes.values() if q.is_down)
                    st.caption(f'📈 上漲 {up_count} | 📉 下跌 {down_count} | 共 {len(quotes)} 檔')

                    # 3 欄顯示
                    q_cols = st.columns(3)
                    for i, stock_id in enumerate(stock_ids[:12]):
                        if stock_id in quotes:
                            with q_cols[i % 3]:
                                st.markdown(format_compact_quote(quotes[stock_id]), unsafe_allow_html=True)
                else:
                    show_empty_state('無法取得報價', icon='📊', suggestion='請確認目前是否為交易時段')
            else:
                show_empty_state('此清單沒有股票', icon='📋', suggestion='請至自選股頁面新增股票')
    else:
        show_empty_state('尚未建立自選股清單', icon='⭐', suggestion='請至自選股頁面建立您的第一個清單')

        # 顯示預設熱門股
        st.markdown('**預設顯示熱門股票：**')
        default_stocks = ['2330', '2317', '2454']
        quotes = fetch_realtime_quotes(default_stocks, use_cache=True)

        if quotes:
            for stock_id in default_stocks:
                if stock_id in quotes:
                    st.markdown(format_compact_quote(quotes[stock_id]), unsafe_allow_html=True)

# 更多熱門股
with row2_col2:
    st.markdown('##### 🔥 熱門股票')

    hot_stocks = ['2881', '2882', '2884', '2891', '0050', '0056', '00878', '00919', '2603', '2609', '3037', '6669']

    quotes = fetch_realtime_quotes(hot_stocks, use_cache=True)

    if quotes:
        # 3 欄顯示
        q_cols = st.columns(3)
        for i, stock_id in enumerate(hot_stocks):
            if stock_id in quotes:
                with q_cols[i % 3]:
                    st.markdown(format_compact_quote(quotes[stock_id]), unsafe_allow_html=True)
    else:
        show_empty_state('非交易時段', icon='🕐', suggestion='交易時段為 09:00 - 13:30，非交易時段顯示收盤資料')

# ========== 第三行：批次查詢 ==========
st.markdown('---')

with st.expander('📋 批次查詢', expanded=False):
    batch_input = st.text_area(
        '輸入多支股票代號 (用逗號、空格或換行分隔)',
        placeholder='2330, 2317, 2454, 0050',
        height=60,
        key='batch_input',
    )

    if st.button('📊 批次查詢', key='batch_btn'):
        if batch_input:
            import re
            stock_ids = re.split(r'[,\s\n]+', batch_input.strip())
            stock_ids = [s.strip() for s in stock_ids if s.strip()]

            if stock_ids:
                with st.spinner(f'查詢 {len(stock_ids)} 支股票...'):
                    quotes = fetch_realtime_quotes(stock_ids, use_cache=False)

                if quotes:
                    # 精簡表格
                    data = []
                    for stock_id in stock_ids:
                        if stock_id in quotes:
                            q = quotes[stock_id]
                            arrow = '▲' if q.is_up else ('▼' if q.is_down else '─')
                            data.append({
                                '代號': q.stock_id,
                                '名稱': q.name,
                                '現價': f'{q.price:,.2f}',
                                '漲跌幅': f'{arrow} {q.change_pct:+.2f}%',
                                '量(張)': f'{q.volume_lots:,}',
                            })

                    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
                else:
                    st.warning('無法取得報價')

# ========== 說明 (折疊) ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    #### 即時報價功能
    - **資料來源**: 台灣證券交易所 (TWSE) / 證券櫃檯買賣中心 (TPEx)
    - **更新頻率**: 約 10 秒
    - **交易時段**: 09:00 - 13:30

    #### 顏色說明
    - 🔴 紅色 / ▲: 上漲
    - 🟢 綠色 / ▼: 下跌
    - 漲停/跌停會有特殊標記

    #### 注意事項
    - 非交易時段顯示上一交易日收盤資料
    - 報價可能有數秒延遲
    ''')

st.caption('此系統僅供參考，不構成投資建議')
