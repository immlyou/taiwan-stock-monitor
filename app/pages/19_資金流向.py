# -*- coding: utf-8 -*-
"""
資金流向分析

追蹤三大法人（外資、投信、自營商）買賣超
類似 Bloomberg MFA (Money Flow Analysis)
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import STREAMLIT_CONFIG
from core.data_loader import get_loader
from core.money_flow import (
    calculate_institutional_flow,
    get_top_flows,
    get_sector_flow,
    calculate_flow_trend,
    get_continuous_buy_stocks,
)
from app.components.sidebar import render_sidebar

# 頁面設定
st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 資金流向",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 渲染側邊欄
render_sidebar(current_page='money_flow')

# 標題
st.title('💸 資金流向分析')
st.caption('追蹤三大法人（外資、投信、自營商）買賣超動向')


@st.cache_data(ttl=300)
def load_institutional_data():
    """載入法人買賣超資料"""
    loader = get_loader()

    # 嘗試載入三大法人資料
    try:
        # 外資
        foreign = loader.get('foreign_investors')
        # 投信
        investment_trust = loader.get('investment_trust')
        # 自營商
        dealer = loader.get('dealer')
        # 外資持股比例
        foreign_holding = loader.get('foreign_holding')
        # 股票資訊
        stock_info = loader.get_stock_info()

        return {
            'foreign': foreign,
            'investment_trust': investment_trust,
            'dealer': dealer,
            'foreign_holding': foreign_holding,
            'stock_info': stock_info,
        }
    except Exception as e:
        st.error(f'載入資料失敗: {e}')
        return None


def create_flow_bar_chart(flows, flow_type='foreign', title='外資買賣超排行'):
    """建立買賣超長條圖"""
    if not flows:
        return None

    # 準備資料
    data = []
    for flow in flows[:15]:  # 顯示前 15 名
        if flow_type == 'foreign':
            value = flow.foreign_net
        elif flow_type == 'investment_trust':
            value = flow.investment_trust_net
        elif flow_type == 'dealer':
            value = flow.dealer_net
        else:
            value = flow.total_net

        data.append({
            'stock': f"{flow.stock_id} {flow.name}",
            'value': value,
            'color': 'red' if value > 0 else 'green',
        })

    df = pd.DataFrame(data)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=df['stock'],
        x=df['value'],
        orientation='h',
        marker_color=['#ef5350' if v > 0 else '#26a69a' for v in df['value']],
        text=[f"{v:+,.0f}" for v in df['value']],
        textposition='outside',
    ))

    fig.update_layout(
        title=title,
        xaxis_title='買賣超 (張)',
        yaxis_title='',
        height=500,
        margin=dict(l=150, r=50, t=50, b=50),
        yaxis=dict(autorange='reversed'),
    )

    return fig


def create_trend_chart(trend_df):
    """建立趨勢圖"""
    if trend_df is None or len(trend_df) == 0:
        return None

    fig = go.Figure()

    colors = {'外資': '#2196F3', '投信': '#FF9800', '自營商': '#9C27B0', '合計': '#4CAF50'}

    for col in trend_df.columns:
        fig.add_trace(go.Scatter(
            x=trend_df.index,
            y=trend_df[col],
            name=col,
            mode='lines+markers',
            line=dict(color=colors.get(col, '#666666')),
        ))

    fig.update_layout(
        title='三大法人買賣超趨勢 (近 20 日)',
        xaxis_title='日期',
        yaxis_title='買賣超 (張)',
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )

    # 添加零線
    fig.add_hline(y=0, line_dash='dash', line_color='gray')

    return fig


def create_sector_chart(sector_df):
    """建立產業資金流向圖"""
    if sector_df is None or len(sector_df) == 0:
        return None

    # 取前 10 大產業
    top_sectors = sector_df.head(10)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='外資',
        x=top_sectors['產業'],
        y=top_sectors['外資'],
        marker_color='#2196F3',
    ))

    fig.add_trace(go.Bar(
        name='投信',
        x=top_sectors['產業'],
        y=top_sectors['投信'],
        marker_color='#FF9800',
    ))

    fig.add_trace(go.Bar(
        name='自營商',
        x=top_sectors['產業'],
        y=top_sectors['自營商'],
        marker_color='#9C27B0',
    ))

    fig.update_layout(
        title='產業資金流向 (Top 10)',
        xaxis_title='產業',
        yaxis_title='買賣超 (張)',
        barmode='group',
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )

    return fig


# ===== 主要內容 =====

# 控制列
col1, col2 = st.columns([3, 1])

with col2:
    if st.button('🔄 重新整理', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 載入資料
with st.spinner('載入法人買賣超資料...'):
    data = load_institutional_data()

if data is None:
    st.warning('無法載入法人買賣超資料，請確認 FinLab API 設定')

    # 顯示說明
    st.info('''
    此功能需要 FinLab API 提供的法人買賣超資料：
    - `institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)`
    - `institutional_investors_trading_summary:投信買賣超股數`
    - `institutional_investors_trading_summary:自營商買賣超股數(自行買賣)`

    請確認您的 FinLab 帳號有權限存取這些資料。
    ''')
    st.stop()

# 計算資金流向
foreign_df = data.get('foreign')
investment_trust_df = data.get('investment_trust')
dealer_df = data.get('dealer')
foreign_holding_df = data.get('foreign_holding')
stock_info = data.get('stock_info')

if foreign_df is None or len(foreign_df) == 0:
    st.warning('無法取得外資買賣超資料')
    st.stop()

# 資料日期
data_date = foreign_df.index[-1].strftime('%Y-%m-%d')
st.caption(f'📅 資料日期: {data_date}')

# 計算法人買賣超
flows = calculate_institutional_flow(
    foreign_df=foreign_df,
    investment_trust_df=investment_trust_df,
    dealer_df=dealer_df,
    stock_info=stock_info,
    foreign_holding_df=foreign_holding_df,
)

if not flows:
    st.warning('無法計算法人買賣超')
    st.stop()

# ===== 今日總覽 =====
st.markdown('---')
st.subheader('📊 今日三大法人總買賣超')

total_foreign = sum(f.foreign_net for f in flows.values())
total_investment_trust = sum(f.investment_trust_net for f in flows.values())
total_dealer = sum(f.dealer_net for f in flows.values())
total_all = total_foreign + total_investment_trust + total_dealer

summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

with summary_col1:
    delta_color = 'normal' if total_foreign >= 0 else 'inverse'
    st.metric(
        '🌍 外資',
        f'{total_foreign:+,.0f} 張',
        f'約 {total_foreign * 50 / 100000000:+,.1f} 億',
        delta_color=delta_color,
    )

with summary_col2:
    delta_color = 'normal' if total_investment_trust >= 0 else 'inverse'
    st.metric(
        '🏦 投信',
        f'{total_investment_trust:+,.0f} 張',
        f'約 {total_investment_trust * 50 / 100000000:+,.1f} 億',
        delta_color=delta_color,
    )

with summary_col3:
    delta_color = 'normal' if total_dealer >= 0 else 'inverse'
    st.metric(
        '🏢 自營商',
        f'{total_dealer:+,.0f} 張',
        f'約 {total_dealer * 50 / 100000000:+,.1f} 億',
        delta_color=delta_color,
    )

with summary_col4:
    delta_color = 'normal' if total_all >= 0 else 'inverse'
    st.metric(
        '📈 三大法人合計',
        f'{total_all:+,.0f} 張',
        f'約 {total_all * 50 / 100000000:+,.1f} 億',
        delta_color=delta_color,
    )

# ===== 分頁 =====
tab1, tab2, tab3, tab4 = st.tabs(['📊 買賣超排行', '📈 趨勢分析', '🏭 產業流向', '🔥 連續買超'])

# ===== Tab 1: 買賣超排行 =====
with tab1:
    st.markdown('### 三大法人買賣超排行')

    rank_type = st.radio(
        '選擇法人',
        ['外資', '投信', '自營商', '三大法人合計'],
        horizontal=True,
        key='rank_type',
    )

    type_map = {
        '外資': 'foreign',
        '投信': 'investment_trust',
        '自營商': 'dealer',
        '三大法人合計': 'total',
    }

    flow_type = type_map[rank_type]

    rank_col1, rank_col2 = st.columns(2)

    with rank_col1:
        st.markdown('#### 🔥 買超排行')
        top_buy = get_top_flows(flows, flow_type=flow_type, top_n=15, ascending=False)
        fig = create_flow_bar_chart(top_buy, flow_type, f'{rank_type}買超 Top 15')
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    with rank_col2:
        st.markdown('#### 💧 賣超排行')
        top_sell = get_top_flows(flows, flow_type=flow_type, top_n=15, ascending=True)
        fig = create_flow_bar_chart(top_sell, flow_type, f'{rank_type}賣超 Top 15')
        if fig:
            st.plotly_chart(fig, use_container_width=True)

# ===== Tab 2: 趨勢分析 =====
with tab2:
    st.markdown('### 三大法人買賣超趨勢')

    trend_df = calculate_flow_trend(
        foreign_df=foreign_df,
        investment_trust_df=investment_trust_df,
        dealer_df=dealer_df,
        days=20,
    )

    if len(trend_df) > 0:
        fig = create_trend_chart(trend_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # 顯示數據表
        with st.expander('📋 查看詳細數據'):
            trend_display = trend_df.copy()
            trend_display.index = trend_display.index.strftime('%Y-%m-%d')
            for col in trend_display.columns:
                trend_display[col] = trend_display[col].apply(lambda x: f'{x:+,.0f}')
            st.dataframe(trend_display, use_container_width=True)
    else:
        st.info('無法取得趨勢資料')

# ===== Tab 3: 產業流向 =====
with tab3:
    st.markdown('### 產業資金流向')

    sector_df = get_sector_flow(flows)

    if len(sector_df) > 0:
        fig = create_sector_chart(sector_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # 顯示表格
        st.markdown('#### 產業資金流向明細')
        sector_display = sector_df.copy()
        for col in ['外資', '投信', '自營商', '合計']:
            sector_display[col] = sector_display[col].apply(lambda x: f'{x:+,.0f}')
        st.dataframe(sector_display, use_container_width=True, hide_index=True)
    else:
        st.info('無法取得產業資料')

# ===== Tab 4: 連續買超 =====
with tab4:
    st.markdown('### 連續買超追蹤')
    st.caption('追蹤外資連續買超的股票')

    min_days = st.slider('最少連續天數', 2, 10, 3, key='min_days')

    continuous_stocks = get_continuous_buy_stocks(flows, min_days=min_days)

    if continuous_stocks:
        # 建立表格
        data = []
        for flow in continuous_stocks[:30]:
            data.append({
                '代號': flow.stock_id,
                '名稱': flow.name,
                '產業': flow.category,
                '連續買超天數': flow.consecutive_days,
                '今日外資': f'{flow.foreign_net:+,.0f}',
                '今日投信': f'{flow.investment_trust_net:+,.0f}',
                '外資持股%': f'{flow.foreign_holding_pct:.1f}%' if flow.foreign_holding_pct else '-',
            })

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info(f'共 {len(continuous_stocks)} 檔股票連續買超 {min_days} 天以上')
    else:
        st.info(f'沒有股票連續買超 {min_days} 天以上')

# 頁尾說明
st.markdown('---')
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 資金流向分析說明

    #### 三大法人
    - **外資**: 外國機構投資人，通常是市場主力
    - **投信**: 國內投信公司，代表法人選股方向
    - **自營商**: 券商自營部門，短線交易為主

    #### 指標說明
    - **買賣超**: 買進股數 - 賣出股數，正數為買超
    - **連續買超天數**: 連續幾天維持買超
    - **外資持股比例**: 外資持有該股票的比例

    #### 使用建議
    1. 觀察三大法人同步買超的股票
    2. 追蹤外資連續買超的標的
    3. 注意產業資金輪動方向
    4. 結合技術分析做決策

    #### 注意事項
    - 法人買賣超僅供參考，不代表未來走勢
    - 資料通常在收盤後更新
    - 單日大量買賣超可能是特殊事件
    ''')

st.caption('資料來源: FinLab API')
