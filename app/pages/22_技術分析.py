# -*- coding: utf-8 -*-
"""
技術分析頁面 — K 線圖 + MACD / KD / RSI / 布林通道
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from core.indicators import sma, rsi, macd, bollinger_bands, kdj
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.charts import apply_dark_theme
from app.components.theme import COLORS, DEFAULT_PLOTLY_LAYOUT
from app.components.session_manager import get_stock_to_analyze

st.set_page_config(page_title='技術分析', page_icon='📉', layout='wide')
render_sidebar_mini(current_page='technical')
render_page_header('技術分析', icon='📉')

# ─── 資料載入 ─────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL.get('daily', 86400))
def load_price_data():
    loader = get_loader()
    close = loader.get('close')
    open_ = loader.get('open')
    high = loader.get('high')
    low = loader.get('low')
    volume = loader.get('volume')
    return close, open_, high, low, volume


try:
    close, open_, high, low, volume = load_price_data()
except Exception as e:
    show_error(e, title='資料載入失敗')
    st.stop()

if close is None or close.empty:
    show_empty_state('無法取得價格資料', icon='📭', suggestion='請確認資料源是否正確設定')
    st.stop()

# ─── 股票選擇 ─────────────────────────────────────────
active = get_active_stocks()
stock_list = sorted(active) if active else sorted(close.columns.tolist())

# 若從個股分析跳過來，自動帶入
default_stock = get_stock_to_analyze() or (stock_list[0] if stock_list else None)
if default_stock and default_stock not in stock_list:
    default_stock = stock_list[0] if stock_list else None

col_stock, col_period = st.columns([2, 3])
with col_stock:
    selected_stock = st.selectbox(
        '選擇股票',
        options=stock_list,
        index=stock_list.index(default_stock) if default_stock in stock_list else 0,
        key='ta_stock_select',
    )
with col_period:
    period_options = {'近 1 個月': 22, '近 3 個月': 66, '近 6 個月': 132, '近 1 年': 252, '近 2 年': 504}
    period_label = st.select_slider('時間範圍', options=list(period_options.keys()), value='近 6 個月', key='ta_period')
    n_days = period_options[period_label]

if selected_stock is None:
    show_empty_state('請選擇一檔股票')
    st.stop()

# ─── 截取資料 ─────────────────────────────────────────
try:
    c = close[selected_stock].dropna().iloc[-n_days:]
    o = open_[selected_stock].reindex(c.index)
    h = high[selected_stock].reindex(c.index)
    l = low[selected_stock].reindex(c.index)
    v = volume[selected_stock].reindex(c.index) if volume is not None else None
except Exception:
    show_empty_state(f'找不到 {selected_stock} 的價格資料')
    st.stop()

if c.empty:
    show_empty_state(f'{selected_stock} 資料為空')
    st.stop()

# ─── 指標選擇 ─────────────────────────────────────────
st.markdown(f'<div style="margin-top:4px"></div>', unsafe_allow_html=True)
indicator_cols = st.columns(5)
show_ma = indicator_cols[0].checkbox('均線 (MA)', value=True, key='ta_ma')
show_boll = indicator_cols[1].checkbox('布林通道', value=False, key='ta_boll')
show_macd = indicator_cols[2].checkbox('MACD', value=True, key='ta_macd')
show_kd = indicator_cols[3].checkbox('KD', value=True, key='ta_kd')
show_rsi = indicator_cols[4].checkbox('RSI', value=False, key='ta_rsi')

# 計算副圖數量
sub_count = sum([show_macd, show_kd, show_rsi])
total_rows = 1 + 1 + sub_count  # K 線 + 成交量 + 副指標
row_heights = [0.45] + [0.15] + [0.4 / max(sub_count, 1)] * max(sub_count, 0)
if sub_count == 0:
    row_heights = [0.7, 0.3]

# ─── 繪製圖表 ─────────────────────────────────────────
fig = make_subplots(
    rows=total_rows, cols=1, shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=row_heights,
)

# === K 線圖 ===
colors_up = '#ef4444'   # 台股紅漲
colors_down = '#22c55e'  # 台股綠跌

fig.add_trace(go.Candlestick(
    x=c.index, open=o, high=h, low=l, close=c,
    increasing_line_color=colors_up, decreasing_line_color=colors_down,
    increasing_fillcolor=colors_up, decreasing_fillcolor=colors_down,
    name='K 線', showlegend=False,
), row=1, col=1)

# 均線
if show_ma:
    ma_periods = [5, 20, 60]
    ma_colors = ['#fbbf24', '#3b82f6', '#a855f7']
    close_df = c.to_frame(name=selected_stock)
    for period, color in zip(ma_periods, ma_colors):
        ma_val = sma(close_df, period)[selected_stock].reindex(c.index)
        fig.add_trace(go.Scatter(
            x=c.index, y=ma_val, mode='lines',
            line=dict(width=1.2, color=color),
            name=f'MA{period}',
        ), row=1, col=1)

# 布林通道
if show_boll:
    close_df = c.to_frame(name=selected_stock)
    bb = bollinger_bands(close_df, period=20, std_dev=2)
    bb_mid = bb[f'{selected_stock}_middle'].reindex(c.index)
    bb_upper = bb[f'{selected_stock}_upper'].reindex(c.index)
    bb_lower = bb[f'{selected_stock}_lower'].reindex(c.index)

    fig.add_trace(go.Scatter(x=c.index, y=bb_upper, mode='lines',
                             line=dict(width=1, color='rgba(168,85,247,0.5)'), name='BB Upper', showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=bb_lower, mode='lines',
                             line=dict(width=1, color='rgba(168,85,247,0.5)'), fill='tonexty',
                             fillcolor='rgba(168,85,247,0.08)', name='布林通道'), row=1, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=bb_mid, mode='lines',
                             line=dict(width=1, dash='dash', color='#a855f7'), name='BB Mid', showlegend=False), row=1, col=1)

# === 成交量 ===
vol_row = 2
if v is not None and not v.isna().all():
    vol_colors = [colors_up if c.iloc[i] >= o.iloc[i] else colors_down for i in range(len(c))]
    fig.add_trace(go.Bar(
        x=c.index, y=v, marker_color=vol_colors,
        name='成交量', showlegend=False, opacity=0.7,
    ), row=vol_row, col=1)

# === 副指標 ===
current_row = 3

if show_macd:
    close_df = c.to_frame(name=selected_stock)
    macd_result = macd(close_df)
    macd_line = macd_result[f'{selected_stock}_macd'].reindex(c.index)
    signal_line = macd_result[f'{selected_stock}_signal'].reindex(c.index)
    hist = macd_result[f'{selected_stock}_histogram'].reindex(c.index)

    hist_colors = [colors_up if val >= 0 else colors_down for val in hist.fillna(0)]
    fig.add_trace(go.Bar(x=c.index, y=hist, marker_color=hist_colors, name='MACD Hist', showlegend=False, opacity=0.6), row=current_row, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=macd_line, mode='lines', line=dict(width=1.2, color='#3b82f6'), name='MACD'), row=current_row, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=signal_line, mode='lines', line=dict(width=1.2, color='#f97316'), name='Signal'), row=current_row, col=1)
    fig.update_yaxes(title_text='MACD', row=current_row, col=1)
    current_row += 1

if show_kd:
    close_df_kd = c.to_frame(name=selected_stock)
    kd_result = kdj(
        high[selected_stock].to_frame(name=selected_stock).reindex(c.index),
        low[selected_stock].to_frame(name=selected_stock).reindex(c.index),
        close_df_kd,
    )
    k_val = kd_result[f'{selected_stock}_K'].reindex(c.index)
    d_val = kd_result[f'{selected_stock}_D'].reindex(c.index)

    fig.add_trace(go.Scatter(x=c.index, y=k_val, mode='lines', line=dict(width=1.2, color='#3b82f6'), name='K'), row=current_row, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=d_val, mode='lines', line=dict(width=1.2, color='#f97316'), name='D'), row=current_row, col=1)
    # 超買超賣線
    fig.add_hline(y=80, line_dash='dot', line_color='rgba(239,68,68,0.4)', row=current_row, col=1)
    fig.add_hline(y=20, line_dash='dot', line_color='rgba(34,197,94,0.4)', row=current_row, col=1)
    fig.update_yaxes(title_text='KD', range=[0, 100], row=current_row, col=1)
    current_row += 1

if show_rsi:
    close_df = c.to_frame(name=selected_stock)
    rsi_val = rsi(close_df, period=14)[selected_stock].reindex(c.index)

    fig.add_trace(go.Scatter(x=c.index, y=rsi_val, mode='lines', line=dict(width=1.5, color='#a855f7'), name='RSI(14)'), row=current_row, col=1)
    fig.add_hline(y=70, line_dash='dot', line_color='rgba(239,68,68,0.4)', row=current_row, col=1)
    fig.add_hline(y=30, line_dash='dot', line_color='rgba(34,197,94,0.4)', row=current_row, col=1)
    fig.update_yaxes(title_text='RSI', range=[0, 100], row=current_row, col=1)

# === 統一排版 ===
chart_height = 500 + sub_count * 150
fig.update_layout(
    **DEFAULT_PLOTLY_LAYOUT,
    height=chart_height,
    title=dict(text=f'{selected_stock} 技術分析', font=dict(size=16)),
    xaxis_rangeslider_visible=False,
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=11)),
)
fig.update_xaxes(type='category', nticks=12)

st.plotly_chart(fig, use_container_width=True)

# ─── KPI 摘要 ──────────────────────────────────────────
st.markdown(f'<div style="margin-top:0.5rem"></div>', unsafe_allow_html=True)
latest_price = c.iloc[-1]
prev_price = c.iloc[-2] if len(c) > 1 else latest_price
change_pct = (latest_price / prev_price - 1) * 100
high_n = h.max()
low_n = l.min()

kpi_cols = st.columns(5)
kpi_cols[0].metric('最新收盤', f'{latest_price:,.2f}', f'{change_pct:+.2f}%')
kpi_cols[1].metric(f'{period_label}最高', f'{high_n:,.2f}')
kpi_cols[2].metric(f'{period_label}最低', f'{low_n:,.2f}')
kpi_cols[3].metric('振幅', f'{(high_n / low_n - 1) * 100:.1f}%')
if v is not None and not v.isna().all():
    avg_vol = v.mean()
    kpi_cols[4].metric('日均量', f'{avg_vol / 1000:,.0f}K')
