# -*- coding: utf-8 -*-
"""
市場熱力圖 (Market Heatmap) - 優化版

以視覺化方式呈現市場全貌，方塊大小=市值，顏色=漲跌幅
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

from config import STREAMLIT_CONFIG, CACHE_TTL
from core.data_loader import get_loader
from app.components.sidebar import render_sidebar
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error

# 頁面設定
st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 市場熱力圖",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 渲染側邊欄
render_sidebar(current_page='heatmap')


@st.cache_data(ttl=CACHE_TTL['intraday'])
def load_market_data(top_n=200):
    """載入市場資料"""
    loader = get_loader()

    # 取得收盤價
    close = loader.get('close')
    if close is None or len(close) == 0:
        return None

    # 取得最近兩天的資料計算漲跌幅
    latest_close = close.iloc[-1]
    prev_close = close.iloc[-2] if len(close) > 1 else close.iloc[-1]

    # 計算漲跌幅
    change_pct = ((latest_close - prev_close) / prev_close * 100).fillna(0)

    # 取得市值
    market_value = loader.get('market_value')
    if market_value is not None and len(market_value) > 0:
        latest_mv = market_value.iloc[-1]
    else:
        latest_mv = latest_close

    # 取得股票資訊
    stock_info = loader.get_stock_info()

    # 建立資料框
    data = []
    for stock_id in latest_close.index:
        if pd.isna(latest_close[stock_id]) or latest_close[stock_id] <= 0:
            continue

        info = stock_info[stock_info['stock_id'] == stock_id]
        if len(info) == 0:
            continue

        name = info['name'].values[0]
        category = info['category'].values[0] if 'category' in info.columns else '其他'

        if pd.isna(category) or category == '':
            category = '其他'

        mv = latest_mv.get(stock_id, 0)
        if pd.isna(mv) or mv <= 0:
            mv = latest_close[stock_id] * 1000000

        chg = change_pct.get(stock_id, 0)
        if pd.isna(chg):
            chg = 0

        data.append({
            'stock_id': stock_id,
            'name': name,
            'category': category,
            'close': latest_close[stock_id],
            'change_pct': chg,
            'market_value': mv,
            'display': f"{stock_id}<br>{name}<br>{chg:+.2f}%",
        })

    df = pd.DataFrame(data)
    df = df.nlargest(top_n, 'market_value')

    return df, close.index[-1].strftime('%Y-%m-%d')


def create_heatmap(df, color_scale='RdYlGn_r', height=650):
    """建立熱力圖"""
    if df is None or len(df) == 0:
        return None

    df['change_pct_clipped'] = df['change_pct'].clip(-7, 7)

    fig = px.treemap(
        df,
        path=['category', 'display'],
        values='market_value',
        color='change_pct_clipped',
        color_continuous_scale=color_scale,
        range_color=[-7, 7],
        custom_data=['stock_id', 'name', 'close', 'change_pct', 'market_value'],
    )

    fig.update_traces(
        hovertemplate=(
            '<b>%{customdata[0]} %{customdata[1]}</b><br>'
            '收盤價: %{customdata[2]:,.2f}<br>'
            '漲跌幅: %{customdata[3]:+.2f}%<br>'
            '市值: %{customdata[4]:,.0f} 億<br>'
            '<extra></extra>'
        ),
        textfont=dict(size=11),
    )

    fig.update_layout(
        margin=dict(t=10, l=5, r=5, b=5),
        height=height,
        coloraxis_colorbar=dict(
            title='漲跌%',
            ticksuffix='%',
            len=0.5,
            thickness=15,
        ),
    )

    return fig


def create_sector_bar(df):
    """建立產業漲跌長條圖"""
    if df is None or len(df) == 0:
        return None

    summary = df.groupby('category').agg({
        'change_pct': 'mean',
        'market_value': 'sum',
    }).reset_index()

    summary = summary.sort_values('market_value', ascending=False).head(12)

    colors = ['#ef5350' if x > 0 else '#26a69a' for x in summary['change_pct']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=summary['category'],
        y=summary['change_pct'],
        marker_color=colors,
        text=[f"{x:+.2f}%" for x in summary['change_pct']],
        textposition='outside',
    ))

    fig.update_layout(
        title='產業平均漲跌幅',
        xaxis_title='',
        yaxis_title='漲跌幅 (%)',
        height=280,
        margin=dict(t=40, l=40, r=20, b=60),
        yaxis=dict(zeroline=True, zerolinecolor='gray', zerolinewidth=1),
    )

    return fig


# ========== 頁面標題 ==========
render_page_header('市場熱力圖', icon='🗺️')

# ========== 控制列與統計 (整合) ==========
ctrl_col1, ctrl_col2, stat_col1, stat_col2, stat_col3, stat_col4 = st.columns([1.5, 1.5, 1, 1, 1, 1])

with ctrl_col1:
    color_option = st.selectbox(
        '顏色',
        ['紅漲綠跌', '綠漲紅跌'],
        key='color_scheme',
        label_visibility='collapsed',
    )

with ctrl_col2:
    top_n = st.selectbox(
        '範圍',
        [('前 200 大', 200), ('前 100 大', 100), ('前 50 大', 50)],
        format_func=lambda x: x[0],
        key='top_n',
        label_visibility='collapsed',
    )

# 載入資料
result = load_market_data(top_n[1] if isinstance(top_n, tuple) else 200)

if result is None:
    show_error(Exception('無法載入市場資料'), title='載入市場資料失敗', suggestion='請確認 FinLab API 設定及網路連線')
    st.stop()

df, data_date = result

# 統計數據
up_count = len(df[df['change_pct'] > 0])
down_count = len(df[df['change_pct'] < 0])
avg_change = df['change_pct'].mean()
limit_up = len(df[df['change_pct'] >= 9.5])
limit_down = len(df[df['change_pct'] <= -9.5])

with stat_col1:
    st.metric('📈 上漲', f'{up_count}')

with stat_col2:
    st.metric('📉 下跌', f'{down_count}')

with stat_col3:
    st.metric('🔴 漲停', f'{limit_up}')

with stat_col4:
    st.metric('🟢 跌停', f'{limit_down}')

st.caption(f'📅 資料日期: {data_date} | 顯示市值前 {len(df)} 大股票')

# ========== 主要內容：熱力圖 + 產業圖 ==========
st.markdown('---')

main_col1, main_col2 = st.columns([3, 1])

with main_col1:
    # 熱力圖
    color_scale = 'RdYlGn_r' if '紅漲綠跌' in color_option else 'RdYlGn'
    fig = create_heatmap(df, color_scale, height=600)

    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning('無法建立熱力圖')

with main_col2:
    # 產業漲跌
    sector_fig = create_sector_bar(df)
    if sector_fig:
        st.plotly_chart(sector_fig, use_container_width=True)

    # 漲幅 Top 5
    st.markdown('##### 🔥 漲幅 Top 5')
    top_gainers = df.nlargest(5, 'change_pct')[['stock_id', 'name', 'change_pct']]
    for _, row in top_gainers.iterrows():
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:2px 0;font-size:13px'>"
            f"<span>{row['stock_id']} {row['name'][:4]}</span>"
            f"<span style='color:#ef5350;font-weight:bold'>{row['change_pct']:+.2f}%</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown('')

    # 跌幅 Top 5
    st.markdown('##### 💧 跌幅 Top 5')
    top_losers = df.nsmallest(5, 'change_pct')[['stock_id', 'name', 'change_pct']]
    for _, row in top_losers.iterrows():
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:2px 0;font-size:13px'>"
            f"<span>{row['stock_id']} {row['name'][:4]}</span>"
            f"<span style='color:#26a69a;font-weight:bold'>{row['change_pct']:+.2f}%</span>"
            f"</div>",
            unsafe_allow_html=True
        )

# ========== 產業明細 (折疊) ==========
with st.expander('📊 產業明細表'):
    summary = df.groupby('category').agg({
        'stock_id': 'count',
        'change_pct': 'mean',
        'market_value': 'sum',
    }).reset_index()

    summary.columns = ['產業', '股票數', '平均漲跌幅', '總市值']
    summary = summary.sort_values('總市值', ascending=False)
    summary['平均漲跌幅'] = summary['平均漲跌幅'].apply(lambda x: f"{x:+.2f}%")
    summary['總市值'] = summary['總市值'].apply(lambda x: f"{x/100000000:,.0f} 億")

    col1, col2 = st.columns(2)
    half = len(summary) // 2
    with col1:
        st.dataframe(summary.iloc[:half], use_container_width=True, hide_index=True)
    with col2:
        st.dataframe(summary.iloc[half:], use_container_width=True, hide_index=True)

# ========== 使用說明 (折疊) ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    #### 熱力圖說明
    - **方塊大小**: 市值越大，方塊越大
    - **顏色深淺**: 漲跌幅越大，顏色越深
    - 🔴 紅色 = 上漲 | 🟢 綠色 = 下跌

    #### 互動操作
    - 滑鼠懸停查看詳細資訊
    - 點擊產業區塊可放大查看
    - 雙擊返回全貌
    ''')

st.caption('資料來源: FinLab API')
