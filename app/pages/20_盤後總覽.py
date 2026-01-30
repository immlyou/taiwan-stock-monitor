# -*- coding: utf-8 -*-
"""
盤後籌碼總覽

每日收盤後的籌碼報告：三大法人買賣超、融資融券變化、自選股追蹤
類似 Bloomberg 盤後報告
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import sys
from pathlib import Path
from datetime import datetime

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import STREAMLIT_CONFIG
from core.data_loader import get_loader
from core.twse_api import get_taiex
from app.components.sidebar import render_sidebar

# 頁面設定
st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 盤後總覽",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 渲染側邊欄
render_sidebar(current_page='after_hours')

# 標題
st.title('📋 盤後籌碼總覽')
st.caption('每日收盤後的市場籌碼報告')


@st.cache_data(ttl=300)
def load_after_hours_data():
    """載入盤後資料"""
    loader = get_loader()

    data = {}

    # 收盤價
    close = loader.get('close')
    if close is not None and len(close) > 0:
        data['close'] = close
        data['latest_date'] = close.index[-1].strftime('%Y-%m-%d')

        # 計算漲跌幅
        if len(close) > 1:
            data['change_pct'] = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).fillna(0)
        else:
            data['change_pct'] = pd.Series(0, index=close.columns)

    # 成交量
    volume = loader.get('volume')
    if volume is not None and len(volume) > 0:
        data['volume'] = volume

    # 三大法人
    data['foreign'] = loader.get('foreign_investors')
    data['investment_trust'] = loader.get('investment_trust')
    data['dealer'] = loader.get('dealer')

    # 融資融券
    data['margin_buy'] = loader.get('margin_buy')
    data['margin_sell'] = loader.get('margin_sell')

    # 股票資訊
    data['stock_info'] = loader.get_stock_info()

    return data


def load_watchlist():
    """載入自選股清單"""
    watchlist_file = Path(__file__).parent.parent.parent / 'data' / 'watchlists.json'
    if watchlist_file.exists():
        try:
            with open(watchlist_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_stock_name(stock_id, stock_info):
    """取得股票名稱"""
    if stock_info is None:
        return ''
    info = stock_info[stock_info['stock_id'] == stock_id]
    return info['name'].values[0] if len(info) > 0 else ''


def create_market_summary(data):
    """建立市場摘要"""
    if 'change_pct' not in data:
        return None

    change_pct = data['change_pct']

    up_count = (change_pct > 0).sum()
    down_count = (change_pct < 0).sum()
    flat_count = (change_pct == 0).sum()
    limit_up = (change_pct >= 9.5).sum()
    limit_down = (change_pct <= -9.5).sum()

    return {
        'up_count': up_count,
        'down_count': down_count,
        'flat_count': flat_count,
        'limit_up': limit_up,
        'limit_down': limit_down,
        'total': len(change_pct),
    }


def get_top_institutional(data, inst_type='foreign', top_n=10, ascending=False):
    """取得法人買賣超排行"""
    df = data.get(inst_type)
    stock_info = data.get('stock_info')

    if df is None or len(df) == 0:
        return pd.DataFrame()

    latest = df.iloc[-1] / 1000  # 轉換為張

    if ascending:
        top_stocks = latest.nsmallest(top_n)
    else:
        top_stocks = latest.nlargest(top_n)

    result = []
    for stock_id, value in top_stocks.items():
        if pd.isna(value):
            continue
        result.append({
            '代號': stock_id,
            '名稱': get_stock_name(stock_id, stock_info),
            '買賣超(張)': f'{value:+,.0f}',
        })

    return pd.DataFrame(result)


def get_margin_changes(data, top_n=10, change_type='increase'):
    """取得融資融券變化排行"""
    margin_buy = data.get('margin_buy')
    stock_info = data.get('stock_info')

    if margin_buy is None or len(margin_buy) < 2:
        return pd.DataFrame()

    # 計算變化
    latest = margin_buy.iloc[-1]
    prev = margin_buy.iloc[-2]
    change = latest - prev

    if change_type == 'increase':
        top_stocks = change.nlargest(top_n)
    else:
        top_stocks = change.nsmallest(top_n)

    result = []
    for stock_id, value in top_stocks.items():
        if pd.isna(value):
            continue
        result.append({
            '代號': stock_id,
            '名稱': get_stock_name(stock_id, stock_info),
            '融資變化(張)': f'{value:+,.0f}',
            '融資餘額(張)': f'{latest.get(stock_id, 0):,.0f}',
        })

    return pd.DataFrame(result)


def get_watchlist_summary(data, watchlist_stocks):
    """取得自選股籌碼摘要"""
    if not watchlist_stocks:
        return pd.DataFrame()

    stock_info = data.get('stock_info')
    close = data.get('close')
    change_pct = data.get('change_pct', pd.Series())
    foreign = data.get('foreign')
    investment_trust = data.get('investment_trust')

    result = []
    for stock_id in watchlist_stocks:
        row = {'代號': stock_id}
        row['名稱'] = get_stock_name(stock_id, stock_info)

        # 收盤價
        if close is not None and stock_id in close.columns:
            row['收盤價'] = f'{close.iloc[-1][stock_id]:,.2f}'
        else:
            row['收盤價'] = '-'

        # 漲跌幅
        if stock_id in change_pct.index:
            chg = change_pct[stock_id]
            row['漲跌幅'] = f'{chg:+.2f}%'
        else:
            row['漲跌幅'] = '-'

        # 外資
        if foreign is not None and stock_id in foreign.columns:
            foreign_net = foreign.iloc[-1][stock_id] / 1000
            row['外資'] = f'{foreign_net:+,.0f}'
        else:
            row['外資'] = '-'

        # 投信
        if investment_trust is not None and stock_id in investment_trust.columns:
            trust_net = investment_trust.iloc[-1][stock_id] / 1000
            row['投信'] = f'{trust_net:+,.0f}'
        else:
            row['投信'] = '-'

        result.append(row)

    return pd.DataFrame(result)


# ===== 主要內容 =====

# 控制列
col1, col2 = st.columns([3, 1])

with col2:
    if st.button('🔄 重新整理', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 載入資料
with st.spinner('載入盤後資料...'):
    data = load_after_hours_data()

if not data or 'close' not in data:
    st.error('無法載入市場資料')
    st.stop()

# 資料日期
data_date = data.get('latest_date', '-')
st.caption(f'📅 資料日期: {data_date}')

# ===== 大盤總覽 =====
st.markdown('---')
st.subheader('📊 大盤總覽')

# 加權指數
taiex_index, taiex_change, taiex_date = get_taiex()

market_summary = create_market_summary(data)

idx_col1, idx_col2, idx_col3, idx_col4, idx_col5 = st.columns(5)

with idx_col1:
    if taiex_index:
        delta_color = 'normal' if taiex_change and taiex_change >= 0 else 'inverse'
        st.metric(
            '加權指數',
            f'{taiex_index:,.2f}',
            f'{taiex_change:+.2f}%' if taiex_change else None,
            delta_color=delta_color,
        )
    else:
        st.metric('加權指數', '載入中...')

with idx_col2:
    if market_summary:
        st.metric('📈 上漲家數', f"{market_summary['up_count']:,}")

with idx_col3:
    if market_summary:
        st.metric('📉 下跌家數', f"{market_summary['down_count']:,}")

with idx_col4:
    if market_summary:
        st.metric('🔴 漲停', f"{market_summary['limit_up']:,}")

with idx_col5:
    if market_summary:
        st.metric('🟢 跌停', f"{market_summary['limit_down']:,}")

# ===== 三大法人買賣超 =====
st.markdown('---')
st.subheader('💰 三大法人買賣超')

# 計算三大法人總買賣超
total_foreign = 0
total_trust = 0
total_dealer = 0

if data.get('foreign') is not None and len(data['foreign']) > 0:
    total_foreign = data['foreign'].iloc[-1].sum() / 1000

if data.get('investment_trust') is not None and len(data['investment_trust']) > 0:
    total_trust = data['investment_trust'].iloc[-1].sum() / 1000

if data.get('dealer') is not None and len(data['dealer']) > 0:
    total_dealer = data['dealer'].iloc[-1].sum() / 1000

total_all = total_foreign + total_trust + total_dealer

inst_col1, inst_col2, inst_col3, inst_col4 = st.columns(4)

with inst_col1:
    delta_color = 'normal' if total_foreign >= 0 else 'inverse'
    st.metric('🌍 外資', f'{total_foreign:+,.0f} 張', delta_color=delta_color)

with inst_col2:
    delta_color = 'normal' if total_trust >= 0 else 'inverse'
    st.metric('🏦 投信', f'{total_trust:+,.0f} 張', delta_color=delta_color)

with inst_col3:
    delta_color = 'normal' if total_dealer >= 0 else 'inverse'
    st.metric('🏢 自營商', f'{total_dealer:+,.0f} 張', delta_color=delta_color)

with inst_col4:
    delta_color = 'normal' if total_all >= 0 else 'inverse'
    st.metric('📊 合計', f'{total_all:+,.0f} 張', delta_color=delta_color)

# 買賣超排行
st.markdown('### 法人買賣超排行')

tab1, tab2, tab3 = st.tabs(['🌍 外資', '🏦 投信', '🏢 自營商'])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**買超 Top 10**')
        df = get_top_institutional(data, 'foreign', 10, False)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('無資料')

    with col2:
        st.markdown('**賣超 Top 10**')
        df = get_top_institutional(data, 'foreign', 10, True)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('無資料')

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**買超 Top 10**')
        df = get_top_institutional(data, 'investment_trust', 10, False)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('無資料')

    with col2:
        st.markdown('**賣超 Top 10**')
        df = get_top_institutional(data, 'investment_trust', 10, True)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('無資料')

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**買超 Top 10**')
        df = get_top_institutional(data, 'dealer', 10, False)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('無資料')

    with col2:
        st.markdown('**賣超 Top 10**')
        df = get_top_institutional(data, 'dealer', 10, True)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info('無資料')

# ===== 融資融券變化 =====
st.markdown('---')
st.subheader('📈 融資融券變化')

margin_col1, margin_col2 = st.columns(2)

with margin_col1:
    st.markdown('**融資增加 Top 10**')
    df = get_margin_changes(data, 10, 'increase')
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info('無融資資料')

with margin_col2:
    st.markdown('**融資減少 Top 10**')
    df = get_margin_changes(data, 10, 'decrease')
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info('無融資資料')

# ===== 自選股籌碼追蹤 =====
st.markdown('---')
st.subheader('⭐ 自選股籌碼追蹤')

watchlists = load_watchlist()

if watchlists:
    list_names = list(watchlists.keys())
    selected_list = st.selectbox('選擇自選股清單', list_names, key='watchlist_select')

    if selected_list and selected_list in watchlists:
        stocks = watchlists[selected_list]
        if stocks:
            df = get_watchlist_summary(data, stocks)
            if len(df) > 0:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info('無法取得自選股資料')
        else:
            st.info('此清單沒有股票')
else:
    st.info('尚未建立自選股清單。請至「自選股」頁面建立。')

    # 顯示範例
    st.markdown('### 範例：熱門股票籌碼')
    example_stocks = ['2330', '2317', '2454', '2881', '0050']
    df = get_watchlist_summary(data, example_stocks)
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)

# 頁尾說明
st.markdown('---')
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 盤後籌碼總覽說明

    #### 資料更新時間
    - 三大法人買賣超：收盤後約 16:00 更新
    - 融資融券：收盤後約 18:00 更新
    - 建議每日收盤後查看

    #### 指標說明
    - **買賣超**: 買進張數 - 賣出張數
    - **融資增加**: 可能代表散戶看多
    - **融資減少**: 可能代表獲利了結或停損

    #### 使用建議
    1. 追蹤三大法人同步買超的標的
    2. 觀察外資連續買超趨勢
    3. 注意融資大增的股票風險
    4. 定期追蹤自選股籌碼變化
    ''')

st.caption('資料來源: FinLab API')
