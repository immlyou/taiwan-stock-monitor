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
from pathlib import Path
from datetime import datetime


from config import STREAMLIT_CONFIG, CACHE_TTL
from core.data_loader import get_loader
from core.twse_api import get_taiex
from app.components.sidebar import render_sidebar
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error

# 頁面設定
st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 盤後總覽",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 渲染側邊欄
render_sidebar(current_page='after_hours')

# 標題
render_page_header('盤後總覽', icon='📊')


@st.cache_data(ttl=CACHE_TTL['intraday'])
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


from app.components.watchlist_utils import load_watchlists as load_watchlist


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
    show_error(Exception('無法載入市場資料'), title='載入市場資料失敗', suggestion='請確認 FinLab API 設定及網路連線')
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
            show_empty_state('無資料', icon='📭')

    with col2:
        st.markdown('**賣超 Top 10**')
        df = get_top_institutional(data, 'foreign', 10, True)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            show_empty_state('無資料', icon='📭')

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**買超 Top 10**')
        df = get_top_institutional(data, 'investment_trust', 10, False)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            show_empty_state('無資料', icon='📭')

    with col2:
        st.markdown('**賣超 Top 10**')
        df = get_top_institutional(data, 'investment_trust', 10, True)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            show_empty_state('無資料', icon='📭')

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**買超 Top 10**')
        df = get_top_institutional(data, 'dealer', 10, False)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            show_empty_state('無資料', icon='📭')

    with col2:
        st.markdown('**賣超 Top 10**')
        df = get_top_institutional(data, 'dealer', 10, True)
        if len(df) > 0:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            show_empty_state('無資料', icon='📭')

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
        show_empty_state('無融資資料', icon='📈', suggestion='融資融券資料通常在收盤後 18:00 更新')

with margin_col2:
    st.markdown('**融資減少 Top 10**')
    df = get_margin_changes(data, 10, 'decrease')
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        show_empty_state('無融資資料', icon='📈', suggestion='融資融券資料通常在收盤後 18:00 更新')

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
                show_empty_state('無法取得自選股資料', icon='📊')
        else:
            show_empty_state('此清單沒有股票', icon='📋', suggestion='請至自選股頁面新增股票')
else:
    show_empty_state('尚未建立自選股清單', icon='⭐', suggestion='請至「自選股」頁面建立您的第一個清單')

    # 顯示範例
    st.markdown('### 範例：熱門股票籌碼')
    example_stocks = ['2330', '2317', '2454', '2881', '0050']
    df = get_watchlist_summary(data, example_stocks)
    if len(df) > 0:
        st.dataframe(df, use_container_width=True, hide_index=True)

# ===== AI 策略選股建議 =====
st.markdown('---')
st.header('🤖 AI 策略選股建議')
st.caption('根據今日盤後數據，AI 自動篩選推薦標的（僅供參考，非投資建議）')

# 股票類型篩選切換
filter_col1, filter_col2 = st.columns([2, 3])
with filter_col1:
    stock_filter = st.radio(
        '篩選範圍',
        ['僅個股', '個股 + ETF', '全部（含金融）'],
        index=0,
        horizontal=True,
        key='ai_stock_filter',
    )


def _filter_stock_type(index, mode):
    """根據模式過濾股票代號"""
    filtered = index
    if mode == '僅個股':
        # 排除 ETF（00開頭）和金融股（28xx, 58xx 證券/金控）
        filtered = filtered[~filtered.str.startswith('00')]
        filtered = filtered[~filtered.str.match(r'^(28|58)\d{2}$')]
    elif mode == '個股 + ETF':
        # 排除金融股
        filtered = filtered[~filtered.str.match(r'^(28|58)\d{2}$')]
    # '全部' 不過濾
    return filtered


@st.cache_data(ttl=3600)
def compute_ai_stock_picks(filter_mode='僅個股'):
    """計算三大策略選股結果"""
    from core.indicators import rsi as calc_rsi, sma as calc_sma

    loader = get_loader()
    stock_info = loader.get_stock_info()
    results = {}

    # ---- 載入共用資料 ----
    try:
        close = loader.get('close')
    except Exception:
        return {'error': '無法載入收盤價資料'}

    def _name(sid):
        if stock_info is None:
            return ''
        info = stock_info[stock_info['stock_id'] == sid]
        return info['name'].values[0] if len(info) > 0 else ''

    # 最新一天的收盤價
    latest_close = close.iloc[-1]

    # ========== 1. 獲利優先（價值投資） ==========
    try:
        pe = loader.get('pe_ratio')
        pb = loader.get('pb_ratio')
        dy = loader.get('dividend_yield')
        rev_yoy = loader.get('revenue_yoy')

        # 取最新一列
        pe_last = pe.iloc[-1]
        pb_last = pb.iloc[-1]
        dy_last = dy.iloc[-1]
        rev_yoy_last = rev_yoy.iloc[-1]

        # 找出所有股票的交集
        common = latest_close.dropna().index \
            .intersection(pe_last.dropna().index) \
            .intersection(pb_last.dropna().index) \
            .intersection(dy_last.dropna().index) \
            .intersection(rev_yoy_last.dropna().index)
        common = _filter_stock_type(common, filter_mode)

        mask = (
            (pe_last[common] > 0) & (pe_last[common] < 15) &
            (pb_last[common] < 1.5) &
            (dy_last[common] > 4) &
            (rev_yoy_last[common] > 0)
        )
        filtered = common[mask]
        value_df = pd.DataFrame({
            '代號': filtered,
            '名稱': [_name(s) for s in filtered],
            '現價': latest_close[filtered].values,
            '本益比': pe_last[filtered].values,
            '股價淨值比': pb_last[filtered].values,
            '殖利率(%)': dy_last[filtered].values,
            '營收年增率(%)': rev_yoy_last[filtered].values,
        })
        value_df = value_df.sort_values('殖利率(%)', ascending=False).head(10).reset_index(drop=True)
        value_df['推薦理由'] = value_df.apply(
            lambda r: f"殖利率 {r['殖利率(%)']:.1f}% + PE {r['本益比']:.1f} + 營收年增 {r['營收年增率(%)']:.1f}%",
            axis=1,
        )
        # 格式化數值
        for col in ['現價', '本益比', '股價淨值比', '殖利率(%)', '營收年增率(%)']:
            value_df[col] = value_df[col].apply(lambda x: f'{x:.2f}')
        results['value'] = value_df
    except Exception:
        results['value'] = None

    # ========== 2. 短期動能 ==========
    try:
        volume = loader.get('volume')

        # RSI(14)
        rsi_df = calc_rsi(close, period=14)
        rsi_last = rsi_df.iloc[-1]

        # 20 日均量
        vol_sma20 = calc_sma(volume, period=20)
        vol_last = volume.iloc[-1]
        vol_sma20_last = vol_sma20.iloc[-1]

        # 20 日均線
        sma20 = calc_sma(close, period=20)
        sma20_last = sma20.iloc[-1]

        # 近 5 日漲幅
        if len(close) >= 6:
            change_5d = ((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100)
        else:
            change_5d = pd.Series(0, index=close.columns)

        common_m = latest_close.dropna().index \
            .intersection(rsi_last.dropna().index) \
            .intersection(vol_last.dropna().index) \
            .intersection(vol_sma20_last.dropna().index) \
            .intersection(sma20_last.dropna().index) \
            .intersection(change_5d.dropna().index)
        common_m = _filter_stock_type(common_m, filter_mode)

        mask_m = (
            (rsi_last[common_m] >= 50) & (rsi_last[common_m] <= 70) &
            (vol_last[common_m] > vol_sma20_last[common_m] * 1.5) &
            (latest_close[common_m] > sma20_last[common_m]) &
            (change_5d[common_m] > 0)
        )
        filtered_m = common_m[mask_m]
        momentum_df = pd.DataFrame({
            '代號': filtered_m,
            '名稱': [_name(s) for s in filtered_m],
            '現價': latest_close[filtered_m].values,
            'RSI(14)': rsi_last[filtered_m].values,
            '量比(倍)': (vol_last[filtered_m] / vol_sma20_last[filtered_m]).values,
            '近5日漲幅(%)': change_5d[filtered_m].values,
        })
        momentum_df = momentum_df.sort_values('近5日漲幅(%)', ascending=False).head(10).reset_index(drop=True)
        momentum_df['推薦理由'] = momentum_df.apply(
            lambda r: f"RSI {r['RSI(14)']:.0f} + 量比 {r['量比(倍)']:.1f}x + 5日漲 {r['近5日漲幅(%)']:.1f}%",
            axis=1,
        )
        for col in ['現價', 'RSI(14)', '量比(倍)', '近5日漲幅(%)']:
            momentum_df[col] = momentum_df[col].apply(lambda x: f'{x:.2f}')
        results['momentum'] = momentum_df
    except Exception:
        results['momentum'] = None

    # ========== 3. 長期存股（穩健配息） ==========
    try:
        pe = loader.get('pe_ratio')
        dy = loader.get('dividend_yield')
        rev_yoy = loader.get('revenue_yoy')
        market_value = loader.get('market_value')

        pe_last = pe.iloc[-1]
        dy_last = dy.iloc[-1]
        rev_yoy_last = rev_yoy.iloc[-1]
        mv_last = market_value.iloc[-1]

        # 市值排名前 50%
        mv_valid = mv_last.dropna()
        mv_median = mv_valid.median()

        common_s = latest_close.dropna().index \
            .intersection(pe_last.dropna().index) \
            .intersection(dy_last.dropna().index) \
            .intersection(rev_yoy_last.dropna().index) \
            .intersection(mv_valid.index)
        common_s = _filter_stock_type(common_s, filter_mode)

        mask_s = (
            (dy_last[common_s] > 5) &
            (pe_last[common_s] > 0) & (pe_last[common_s] < 20) &
            (rev_yoy_last[common_s] > -10) &
            (mv_last[common_s] >= mv_median)
        )
        filtered_s = common_s[mask_s]
        savings_df = pd.DataFrame({
            '代號': filtered_s,
            '名稱': [_name(s) for s in filtered_s],
            '現價': latest_close[filtered_s].values,
            '殖利率(%)': dy_last[filtered_s].values,
            '本益比': pe_last[filtered_s].values,
            '營收年增率(%)': rev_yoy_last[filtered_s].values,
            '市值(億)': (mv_last[filtered_s] / 1e8).values,
        })
        savings_df = savings_df.sort_values('殖利率(%)', ascending=False).head(10).reset_index(drop=True)
        savings_df['推薦理由'] = savings_df.apply(
            lambda r: f"殖利率 {r['殖利率(%)']:.1f}% + PE {r['本益比']:.1f} + 市值 {r['市值(億)']:.0f}億",
            axis=1,
        )
        for col in ['現價', '殖利率(%)', '本益比', '營收年增率(%)']:
            savings_df[col] = savings_df[col].apply(lambda x: f'{x:.2f}')
        savings_df['市值(億)'] = savings_df['市值(億)'].apply(lambda x: f'{x:,.0f}')
        results['savings'] = savings_df
    except Exception:
        results['savings'] = None

    return results


ai_picks = compute_ai_stock_picks(filter_mode=stock_filter)

if isinstance(ai_picks, dict) and 'error' in ai_picks:
    show_error(Exception(ai_picks['error']), title='AI 選股資料載入失敗', suggestion='請確認資料已下載完成')
else:
    _disclaimer = '⚠️ **免責聲明**：以上結果僅為量化篩選，不構成任何投資建議。投資有風險，請自行評估並諮詢專業人士。'

    ai_tab1, ai_tab2, ai_tab3 = st.tabs(['💰 獲利優先', '🚀 短期動能', '🏦 長期存股'])

    with ai_tab1:
        st.markdown('**價值投資策略** — PE < 15、PB < 1.5、殖利率 > 4%、營收正成長')
        df_v = ai_picks.get('value')
        if df_v is not None and len(df_v) > 0:
            st.dataframe(df_v, use_container_width=True, hide_index=True)
        else:
            show_empty_state('目前無符合條件的股票', icon='📭', suggestion='價值型篩選較嚴格，盤後資料更新後再試')
        st.markdown(_disclaimer)

    with ai_tab2:
        st.markdown('**動能策略** — RSI 50-70、量 > 1.5倍均量、突破20MA、近5日上漲')
        df_m = ai_picks.get('momentum')
        if df_m is not None and len(df_m) > 0:
            st.dataframe(df_m, use_container_width=True, hide_index=True)
        else:
            show_empty_state('目前無符合條件的股票', icon='📭', suggestion='動能策略需要同時滿足多項條件')
        st.markdown(_disclaimer)

    with ai_tab3:
        st.markdown('**穩健存股策略** — 殖利率 > 5%、PE 0-20、營收衰退 < 10%、市值前50%')
        df_s = ai_picks.get('savings')
        if df_s is not None and len(df_s) > 0:
            st.dataframe(df_s, use_container_width=True, hide_index=True)
        else:
            show_empty_state('目前無符合條件的股票', icon='📭', suggestion='存股篩選需要穩定配息的大型股')
        st.markdown(_disclaimer)

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
