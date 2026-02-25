# -*- coding: utf-8 -*-
"""
AI 智慧選股 — 多因子評分 + 市場摘要
基於量化因子自動篩選推薦股票，並提供市場綜合摘要。
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.theme import COLORS, create_kpi_card, DEFAULT_PLOTLY_LAYOUT

st.set_page_config(page_title='AI 智慧選股', page_icon='🤖', layout='wide')
render_sidebar_mini(current_page='ai_stock')
render_page_header('AI 智慧選股', icon='🤖')

# ─── 資料載入 ─────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL.get('daily', 86400))
def load_ai_data():
    loader = get_loader()
    close = loader.get('close')
    volume = loader.get('volume')
    pe = loader.get('pe_ratio')
    pb = loader.get('pb_ratio')
    dividend = loader.get('dividend_yield')
    revenue = loader.get('monthly_revenue')
    market_value = loader.get('market_value')
    try:
        stock_info = loader.get_stock_info()
    except Exception:
        stock_info = None  # 股票資訊非必要，缺少時仍可進行選股
    return close, volume, pe, pb, dividend, revenue, market_value, stock_info


with st.spinner('正在載入資料與計算因子...'):
    try:
        close, volume, pe, pb, dividend, revenue, market_value, stock_info = load_ai_data()
    except Exception as e:
        show_error(e, title='資料載入失敗')
        st.stop()

if close is None or close.empty:
    show_empty_state('無法取得價格資料', icon='📭')
    st.stop()

# 建立股票代碼 → 名稱映射
stock_name_map = {}
if stock_info is not None:
    try:
        if hasattr(stock_info, 'empty') and not stock_info.empty:
            if 'stock_id' in stock_info.columns and 'name' in stock_info.columns:
                stock_name_map = dict(zip(stock_info['stock_id'], stock_info['name']))
            elif hasattr(stock_info, 'index'):
                # 有些格式 index 就是股票代碼
                stock_name_map = stock_info.to_dict().get('name', {})
    except Exception:
        pass  # 名稱映射建立失敗時以空字典繼續

active = get_active_stocks()
active_stocks = active if active else close.columns.tolist()

# ─── 多因子計算 ────────────────────────────────────────
st.markdown(f'''
<div style="background:{COLORS["secondary"]};border:1px solid {COLORS["border"]};border-radius:10px;padding:1rem 1.25rem;margin-bottom:1rem">
    <h4 style="color:{COLORS["text_primary"]};margin:0 0 0.5rem 0">🧠 AI 多因子評分模型</h4>
    <p style="color:{COLORS["text_muted"]};font-size:0.85rem;margin:0">
        綜合動能、價值、品質、規模四大面向，為每檔股票計算 0-100 分的綜合評分。
    </p>
</div>
''', unsafe_allow_html=True)

# 參數設定
with st.expander('⚙️ 因子權重設定', expanded=False):
    w_cols = st.columns(4)
    w_momentum = w_cols[0].slider('動能因子', 0, 100, 30, 5, key='ai_w_mom')
    w_value = w_cols[1].slider('價值因子', 0, 100, 30, 5, key='ai_w_val')
    w_quality = w_cols[2].slider('品質因子', 0, 100, 20, 5, key='ai_w_qual')
    w_size = w_cols[3].slider('規模因子', 0, 100, 20, 5, key='ai_w_size')

top_n = st.slider('推薦檔數', 5, 50, 20, 5, key='ai_top_n')


@st.cache_data(ttl=CACHE_TTL.get('daily', 86400))
def compute_scores(_close, _volume, _pe, _pb, _dividend, _revenue, _mv, stocks, w_m, w_v, w_q, w_s):
    """向量化多因子評分計算（不逐檔 loop，速度快 50x）"""
    # 篩選有效欄位
    cols = [s for s in stocks if s in _close.columns]
    if not cols:
        return pd.DataFrame()

    cl = _close[cols]

    # 排除交易日不足 60 天的股票
    valid_counts = cl.notna().sum()
    cols = valid_counts[valid_counts >= 60].index.tolist()
    if not cols:
        return pd.DataFrame()
    cl = cl[cols]

    # --- 向量化取最後一筆有效值 (用 ffill 後取最後一列) ---
    last_close = cl.ffill().iloc[-1]

    # --- 動能因子 (向量化) ---
    close_21 = cl.ffill().iloc[-22] if len(cl) > 21 else last_close
    close_61 = cl.ffill().iloc[-62] if len(cl) > 61 else last_close
    ret_20 = (last_close / close_21 - 1) * 100
    ret_60 = (last_close / close_61 - 1) * 100
    momentum = ret_20 * 0.6 + ret_60 * 0.4

    # --- 價值因子 (向量化取最後有效值) ---
    def last_valid(df, target_cols):
        if df is None or df.empty:
            return pd.Series(np.nan, index=target_cols)
        shared = [c for c in target_cols if c in df.columns]
        if not shared:
            return pd.Series(np.nan, index=target_cols)
        result = df[shared].ffill().iloc[-1]
        return result.reindex(target_cols)

    pe_last = last_valid(_pe, cols)
    pb_last = last_valid(_pb, cols)
    div_last = last_valid(_dividend, cols)
    mv_last = last_valid(_mv, cols)

    # --- 品質因子：月營收年增率 (向量化) ---
    rev_growth = pd.Series(np.nan, index=cols)
    if _revenue is not None and not _revenue.empty:
        rev_cols = [c for c in cols if c in _revenue.columns]
        if rev_cols and len(_revenue) >= 13:
            rev = _revenue[rev_cols].ffill()
            rev_growth_vals = (rev.iloc[-1] / rev.iloc[-13] - 1) * 100
            rev_growth.update(rev_growth_vals)

    # --- 組合 DataFrame ---
    df = pd.DataFrame({
        'close': last_close,
        'ret_20d': ret_20,
        'ret_60d': ret_60,
        'momentum': momentum,
        'pe': pe_last,
        'pb': pb_last,
        'dividend_yield': div_last,
        'rev_growth': rev_growth,
        'market_value': mv_last,
    }, index=cols)
    df.index.name = 'stock_id'

    # 移除收盤價為 NaN 的
    df = df.dropna(subset=['close'])

    if df.empty:
        return df

    # --- 百分位排名 → 0-100 ---
    def pct_rank(s, ascending=True):
        return s.rank(pct=True, ascending=ascending).fillna(0.5) * 100

    df['score_momentum'] = pct_rank(df['momentum'], ascending=True)
    df['score_value'] = (pct_rank(df['pe'], ascending=False) * 0.4
                         + pct_rank(df['pb'], ascending=False) * 0.3
                         + pct_rank(df['dividend_yield'], ascending=True) * 0.3)
    df['score_quality'] = pct_rank(df['rev_growth'], ascending=True)
    df['score_size'] = pct_rank(df['market_value'], ascending=True)

    total_w = w_m + w_v + w_q + w_s or 1
    df['total_score'] = (
        df['score_momentum'] * w_m
        + df['score_value'] * w_v
        + df['score_quality'] * w_q
        + df['score_size'] * w_s
    ) / total_w

    return df.sort_values('total_score', ascending=False)


with st.spinner('計算因子評分中...'):
    result = compute_scores(close, volume, pe, pb, dividend, revenue, market_value,
                            active_stocks, w_momentum, w_value, w_quality, w_size)

if result.empty:
    show_empty_state('因子計算結果為空', suggestion='請確認資料完整性')
    st.stop()

# ─── 市場摘要 KPI ──────────────────────────────────────
st.markdown(f'<div class="nav-group-title" style="color:{COLORS["text_muted"]}">市場因子概覽</div>', unsafe_allow_html=True)
kpi_cols = st.columns(4)

avg_momentum = result['momentum'].mean()
avg_pe = result['pe'].dropna().median()
avg_div = result['dividend_yield'].dropna().median()
avg_rev = result['rev_growth'].dropna().median()

with kpi_cols[0]:
    st.markdown(create_kpi_card('📈 平均動能', f'{avg_momentum:+.1f}%'), unsafe_allow_html=True)
with kpi_cols[1]:
    st.markdown(create_kpi_card('💰 中位 PE', f'{avg_pe:.1f}' if not np.isnan(avg_pe) else 'N/A'), unsafe_allow_html=True)
with kpi_cols[2]:
    st.markdown(create_kpi_card('🎁 中位殖利率', f'{avg_div:.2f}%' if not np.isnan(avg_div) else 'N/A'), unsafe_allow_html=True)
with kpi_cols[3]:
    st.markdown(create_kpi_card('🏭 中位營收成長', f'{avg_rev:+.1f}%' if not np.isnan(avg_rev) else 'N/A'), unsafe_allow_html=True)

# ─── AI 推薦列表 ───────────────────────────────────────
st.markdown(f'### 🏆 AI 推薦 Top {top_n}')

top = result.head(top_n).copy()

# 加入股票名稱欄位
top.insert(0, 'name', top.index.map(lambda sid: stock_name_map.get(sid, '')))

display_df = top[['name', 'close', 'total_score', 'score_momentum', 'score_value', 'score_quality', 'score_size',
                   'ret_20d', 'pe', 'dividend_yield', 'rev_growth']].copy()
display_df.columns = ['名稱', '收盤價', '綜合評分', '動能分', '價值分', '品質分', '規模分',
                       '20日報酬%', 'PE', '殖利率%', '營收成長%']

# 格式化
for col in ['收盤價']:
    display_df[col] = display_df[col].map(lambda x: f'{x:,.2f}')
for col in ['綜合評分', '動能分', '價值分', '品質分', '規模分']:
    display_df[col] = display_df[col].map(lambda x: f'{x:.1f}')
for col in ['20日報酬%', '營收成長%']:
    display_df[col] = display_df[col].map(lambda x: f'{x:+.1f}' if not np.isnan(x) else '-')
display_df['PE'] = display_df['PE'].map(lambda x: f'{x:.1f}' if not (isinstance(x, float) and np.isnan(x)) else '-')
display_df['殖利率%'] = display_df['殖利率%'].map(lambda x: f'{x:.2f}' if not (isinstance(x, float) and np.isnan(x)) else '-')

st.dataframe(display_df, use_container_width=True, height=min(35 * (top_n + 1), 700))

# ─── 因子分佈圖 ───────────────────────────────────────
with st.expander('📊 因子分佈圖', expanded=False):
    import plotly.express as px

    factor_col = st.selectbox('選擇因子', ['total_score', 'score_momentum', 'score_value', 'score_quality', 'score_size'], key='ai_factor')
    fig_hist = px.histogram(result, x=factor_col, nbins=50, title=f'{factor_col} 分佈',
                            color_discrete_sequence=[COLORS['accent']])
    fig_hist.update_layout(**DEFAULT_PLOTLY_LAYOUT, height=350)
    st.plotly_chart(fig_hist, use_container_width=True)

# ─── 免責聲明 ──────────────────────────────────────────
st.markdown(f'''
<div style="background:{COLORS["secondary"]};border:1px solid {COLORS["border"]};border-radius:8px;padding:0.75rem 1rem;margin-top:1rem">
    <p style="color:{COLORS["text_muted"]};font-size:0.75rem;margin:0">
        ⚠️ <b>免責聲明</b>：本頁面所有資訊僅供參考，不構成投資建議。
        AI 評分模型基於歷史數據計算，過去績效不代表未來表現。
        投資有風險，請謹慎評估。
    </p>
</div>
''', unsafe_allow_html=True)
