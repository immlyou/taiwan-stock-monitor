"""
個股分析頁面
功能：走勢圖、技術分析、籌碼、法人買賣、資券變化、估價(河流圖)、財務、基本、同業比較
"""
import streamlit as st
import pandas as pd
import numpy as np
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks, reset_all_caches
from core.indicators import sma, rsi, macd, bollinger_bands, resample_ohlcv, get_timeframe_label, get_ma_periods_for_timeframe
from app.components.charts import create_price_chart, create_technical_chart, apply_dark_theme
from app.components.theme import DEFAULT_PLOTLY_LAYOUT, COLORS
from app.components.sidebar import render_sidebar
from app.components.session_manager import (
    init_session_state, get_state, set_state, StateKeys,
    get_stock_to_analyze
)
from app.components.error_handler import show_error, safe_execute, create_error_boundary

# 嘗試導入 FinLab API
try:
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    from finlab import data as finlab_data
    FINLAB_AVAILABLE = True
except Exception:
    FINLAB_AVAILABLE = False
    finlab_data = None

st.set_page_config(page_title='個股分析', page_icon='📈', layout='wide')

# 初始化 Session State
init_session_state()

render_sidebar(current_page='stock')

# ==================== 資料載入 ====================
@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner="載入股票數據中...")
def load_stock_data():
    """載入基礎股票數據"""
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'open': loader.get('open'),
        'high': loader.get('high'),
        'low': loader.get('low'),
        'volume': loader.get('volume'),
        'pe_ratio': loader.get('pe_ratio'),
        'pb_ratio': loader.get('pb_ratio'),
        'dividend_yield': loader.get('dividend_yield'),
        'monthly_revenue': loader.get('monthly_revenue'),
        'revenue_yoy': loader.get('revenue_yoy'),
        'revenue_mom': loader.get('revenue_mom'),
        'stock_info': loader.get_stock_info(),
    }

@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner="載入 FinLab 數據...")
def load_finlab_data(data_key: str):
    """快取 FinLab 資料"""
    if FINLAB_AVAILABLE and finlab_data:
        try:
            return finlab_data.get(data_key)
        except Exception:
            return None
    return None

@st.cache_data(ttl=CACHE_TTL['daily'])
def load_news_cache():
    """載入新聞快取"""
    cache_file = Path(__file__).parent.parent.parent / 'data' / 'news_cache.json'
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'news': []}

from app.components.watchlist_utils import load_watchlists, save_watchlists

try:
    data = load_stock_data()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

# ==================== 股票選擇區 ====================
active_stocks = get_active_stocks()
stock_info = data['stock_info']

# 建立選項清單
all_stock_options = []
stock_id_map = {}
for _, row in stock_info.iterrows():
    stock_id = row['stock_id']
    name = row['name']
    if stock_id in active_stocks:
        option_label = f"{stock_id} {name}"
        all_stock_options.append(option_label)
        stock_id_map[option_label] = stock_id

# 取得預設股票 (從晨報或其他頁面跳轉過來)
preset_stock = get_stock_to_analyze() or ''

# 找出預設選項的索引
default_index = 0
if preset_stock:
    for i, opt in enumerate(all_stock_options):
        if opt.startswith(preset_stock):
            default_index = i
            break

# 主內容區 - 股票選擇
col_search, col_period, col_action = st.columns([3, 1, 1])

with col_search:
    selected_option = st.selectbox(
        '🔍 選擇股票 (可直接輸入搜尋)',
        options=all_stock_options,
        index=default_index,
        placeholder='輸入股票代號或名稱搜尋...',
        key='stock_selector'
    )
    selected_stock = stock_id_map.get(selected_option) if selected_option else None

with col_period:
    period = st.selectbox('📅 期間', ['1個月', '3個月', '6個月', '1年', '3年', '5年'], index=3)

period_map = {'1個月': 22, '3個月': 66, '6個月': 132, '1年': 252, '3年': 756, '5年': 1260}

with col_action:
    st.write("")  # 對齊
    if st.button('🔄 重整數據', use_container_width=True):
        reset_all_caches()
        st.cache_data.clear()
        st.rerun()

# 顯示從晨報選擇的提示
if preset_stock and selected_option and selected_option.startswith(preset_stock):
    st.info(f'📰 從晨報選擇: {preset_stock}')

st.markdown('---')

# ==================== 主內容區 ====================
if selected_stock:
    # 取得股票數據
    close = data['close'][selected_stock].dropna()
    open_price = data['open'][selected_stock].dropna() if selected_stock in data['open'].columns else close
    high = data['high'][selected_stock].dropna() if selected_stock in data['high'].columns else close
    low = data['low'][selected_stock].dropna() if selected_stock in data['low'].columns else close
    volume = data['volume'][selected_stock].dropna() if selected_stock in data['volume'].columns else None

    days = period_map[period]
    close_period = close.tail(days)
    open_period = open_price.tail(days)
    high_period = high.tail(days)
    low_period = low.tail(days)
    volume_period = volume.tail(days) if volume is not None else None

    stock_row = stock_info[stock_info['stock_id'] == selected_stock]
    if len(stock_row) > 0:
        name = stock_row['name'].values[0]
        category = stock_row['category'].values[0]
        market = stock_row['market'].values[0]
    else:
        name = selected_stock
        category = '-'
        market = '-'

    if len(close_period) == 0:
        st.warning(f'沒有 {selected_stock} 的資料')
        st.stop()

    # ==================== 標題區 ====================
    col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1, 1, 1])

    with col1:
        st.markdown(f"## {selected_stock} {name}")
        st.caption(f'{category} | {market}')

    with col2:
        latest_price = close_period.iloc[-1]
        prev_price = close_period.iloc[-2] if len(close_period) > 1 else latest_price
        change = latest_price - prev_price
        change_pct = (change / prev_price) * 100
        color = "🔴" if change < 0 else "🟢" if change > 0 else "⚪"
        st.metric('股價', f'{latest_price:.2f}', f'{change:+.2f} ({change_pct:+.2f}%)')

    with col3:
        if selected_stock in data['pe_ratio'].columns:
            pe = data['pe_ratio'][selected_stock].dropna()
            st.metric('本益比', f'{pe.iloc[-1]:.2f}' if len(pe) > 0 else '-')
        else:
            st.metric('本益比', '-')

    with col4:
        if selected_stock in data['pb_ratio'].columns:
            pb = data['pb_ratio'][selected_stock].dropna()
            st.metric('股價淨值比', f'{pb.iloc[-1]:.2f}' if len(pb) > 0 else '-')
        else:
            st.metric('股價淨值比', '-')

    with col5:
        watchlists = load_watchlists()
        if not watchlists:
            watchlists['預設清單'] = {'created_at': datetime.now().isoformat(), 'stocks': [], 'notes': {}}
        if st.button('⭐ 加入自選', use_container_width=True, type='secondary'):
            if '預設清單' not in watchlists:
                watchlists['預設清單'] = {'created_at': datetime.now().isoformat(), 'stocks': [], 'notes': {}}
            if selected_stock not in watchlists['預設清單']['stocks']:
                watchlists['預設清單']['stocks'].append(selected_stock)
                save_watchlists(watchlists)
                st.success(f'已加入自選股')
            else:
                st.info(f'已在自選股中')

    # ==================== 匯出報告按鈕 ====================
    export_col1, export_col2, export_col3 = st.columns([3, 1, 1])
    with export_col2:
        if st.button('📄 匯出 PDF 報告', use_container_width=True, key='export_pdf_btn'):
            set_state(StateKeys.SHOW_EXPORT_DIALOG, True)

    with export_col3:
        if st.button('📊 匯出 Excel', use_container_width=True, key='export_excel_btn'):
            set_state(StateKeys.SHOW_EXCEL_EXPORT, True)

    # 處理 PDF 報告匯出
    if get_state(StateKeys.SHOW_EXPORT_DIALOG, False):
        from core.report_generator import ReportGenerator
        from core.indicators import rsi as calc_rsi, macd as calc_macd, bollinger_bands as calc_bb

        # 準備基本面資料
        pe_val = None
        pb_val = None
        dy_val = None
        mv_val = None
        rev_yoy = None
        rev_mom = None

        if selected_stock in data['pe_ratio'].columns:
            pe_series = data['pe_ratio'][selected_stock].dropna()
            pe_val = pe_series.iloc[-1] if len(pe_series) > 0 else None
        if selected_stock in data['pb_ratio'].columns:
            pb_series = data['pb_ratio'][selected_stock].dropna()
            pb_val = pb_series.iloc[-1] if len(pb_series) > 0 else None
        if selected_stock in data['dividend_yield'].columns:
            dy_series = data['dividend_yield'][selected_stock].dropna()
            dy_val = dy_series.iloc[-1] if len(dy_series) > 0 else None
        if selected_stock in data['revenue_yoy'].columns:
            yoy_series = data['revenue_yoy'][selected_stock].dropna()
            rev_yoy = yoy_series.iloc[-1] if len(yoy_series) > 0 else None
        if selected_stock in data['revenue_mom'].columns:
            mom_series = data['revenue_mom'][selected_stock].dropna()
            rev_mom = mom_series.iloc[-1] if len(mom_series) > 0 else None

        fundamental_data = {
            'pe': pe_val,
            'pb': pb_val,
            'dividend_yield': dy_val,
            'market_value': mv_val,
            'revenue_yoy': rev_yoy,
            'revenue_mom': rev_mom,
        }

        # 準備技術面資料
        rsi_val = calc_rsi(close, 14).iloc[-1] if len(close) > 14 else 50
        macd_line, signal_line, _ = calc_macd(close)
        macd_val = macd_line.iloc[-1] - signal_line.iloc[-1] if len(macd_line) > 0 else 0
        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else close.iloc[-1]
        ma20_diff = close.iloc[-1] - ma20

        bb_upper, bb_middle, bb_lower = calc_bb(close, 20, 2)

        technical_data = {
            'rsi': rsi_val,
            'macd': macd_val,
            'ma20': ma20,
            'ma60': ma60,
            'ma20_diff': ma20_diff,
            'bb_upper': bb_upper.iloc[-1] if len(bb_upper) > 0 else 0,
            'bb_lower': bb_lower.iloc[-1] if len(bb_lower) > 0 else 0,
        }

        # 生成報告
        generator = ReportGenerator()
        html_report = generator.generate_stock_analysis_html(
            stock_id=selected_stock,
            stock_name=name,
            category=category,
            market=market,
            close=close,
            volume=volume,
            fundamental_data=fundamental_data,
            technical_data=technical_data,
        )

        # 下載按鈕
        report_filename = f'{selected_stock}_{name}_分析報告_{datetime.now().strftime("%Y%m%d")}.html'
        st.download_button(
            label='下載分析報告 (HTML)',
            data=html_report.encode('utf-8'),
            file_name=report_filename,
            mime='text/html',
            help='下載 HTML 報告後，可在瀏覽器開啟並列印為 PDF',
            key='download_html_report'
        )
        st.caption('提示：下載後在瀏覽器開啟，按 Ctrl+P (或 Cmd+P) 即可列印為 PDF')
        set_state(StateKeys.SHOW_EXPORT_DIALOG, False)

    st.markdown('---')

    # ==================== 主要 Tabs ====================
    tab_chart, tab_chip, tab_valuation, tab_finance, tab_basic, tab_health = st.tabs([
        '📈 走勢圖', '💰 籌碼分析', '📊 估價分析', '📋 財務分析', '🏢 基本資料', '🩺 健診'
    ])

    # ==================== Tab 1: 走勢圖 ====================
    with tab_chart:
        # 時間框架選擇器
        tf_col1, tf_col2, tf_col3 = st.columns([1, 3, 1])
        with tf_col1:
            timeframe = st.radio(
                '時間週期',
                options=['D', 'W', 'M'],
                format_func=get_timeframe_label,
                horizontal=True,
                key='chart_timeframe'
            )

        # 根據時間框架重採樣數據
        resampled = resample_ohlcv(
            open_period, high_period, low_period, close_period,
            volume_period, timeframe
        )
        tf_open = resampled['open']
        tf_high = resampled['high']
        tf_low = resampled['low']
        tf_close = resampled['close']
        tf_volume = resampled.get('volume')

        # 取得對應時間框架的均線週期
        ma_short, ma_mid, ma_long = get_ma_periods_for_timeframe(timeframe)
        tf_label = get_timeframe_label(timeframe)

        # 子分頁
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(['K線走勢', '技術分析', '成交彙整'])

        with sub_tab1:
            price_df = pd.DataFrame({
                'open': tf_open, 'high': tf_high, 'low': tf_low, 'close': tf_close
            })
            if tf_volume is not None:
                price_df['volume'] = tf_volume
            price_df = price_df.dropna()

            # K線圖
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                               row_heights=[0.7, 0.3])

            # K線
            fig.add_trace(go.Candlestick(
                x=price_df.index, open=price_df['open'], high=price_df['high'],
                low=price_df['low'], close=price_df['close'], name='K線',
                increasing_line_color='#ef4444', decreasing_line_color='#22c55e',
                increasing_fillcolor='#ef4444', decreasing_fillcolor='#22c55e'
            ), row=1, col=1)

            # 均線 (根據時間框架調整)
            ma_periods = [ma_short, ma_mid, ma_long]
            ma_colors = ['#FF9800', '#2196F3', '#9C27B0']
            ma_names = {
                'D': [f'MA{ma_short}', f'MA{ma_mid}', f'MA{ma_long}'],
                'W': [f'{ma_short}週', f'{ma_mid}週', f'{ma_long}週'],
                'M': [f'{ma_short}月', f'{ma_mid}月', f'{ma_long}月']
            }
            for i, ma_period in enumerate(ma_periods):
                if len(price_df) >= ma_period:
                    ma = price_df['close'].rolling(ma_period).mean()
                    fig.add_trace(go.Scatter(
                        x=ma.index, y=ma, name=ma_names[timeframe][i],
                        line=dict(color=ma_colors[i], width=1)
                    ), row=1, col=1)

            # 成交量
            if 'volume' in price_df.columns:
                colors = ['#ef4444' if c >= o else '#22c55e'
                         for c, o in zip(price_df['close'], price_df['open'])]
                fig.add_trace(go.Bar(x=price_df.index, y=price_df['volume']/1000,
                                    name='成交量(張)', marker_color=colors), row=2, col=1)

            fig.update_layout(
                title=f'{selected_stock} {name} {tf_label}股價走勢',
                **DEFAULT_PLOTLY_LAYOUT,height=600,
                xaxis_rangeslider_visible=False,
                legend=dict(orientation='h', y=1.02)
            )
            fig.update_yaxes(title_text='股價', row=1, col=1)
            fig.update_yaxes(title_text='成交量(張)', row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)

        with sub_tab2:
            st.markdown(f'### 技術指標分析 ({tf_label})')

            # 計算技術指標 (使用重採樣後的數據)
            rsi_14 = rsi(tf_close, period=14)
            macd_line, signal_line, histogram = macd(tf_close)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                current_rsi = rsi_14.iloc[-1] if len(rsi_14) > 0 and not pd.isna(rsi_14.iloc[-1]) else 0
                rsi_status = '超買' if current_rsi > 70 else '超賣' if current_rsi < 30 else '中性'
                st.metric('RSI(14)', f'{current_rsi:.1f}', rsi_status)
            with col2:
                current_macd = macd_line.iloc[-1] if len(macd_line) > 0 and not pd.isna(macd_line.iloc[-1]) else 0
                signal_val = signal_line.iloc[-1] if len(signal_line) > 0 else 0
                macd_status = '多頭' if current_macd > signal_val else '空頭'
                st.metric('MACD', f'{current_macd:.2f}', macd_status)
            with col3:
                if len(tf_close) >= ma_mid:
                    ma_s = tf_close.rolling(ma_short).mean().iloc[-1]
                    ma_m = tf_close.rolling(ma_mid).mean().iloc[-1]
                    tf_latest = tf_close.iloc[-1]
                    ma_status = '多頭排列' if tf_latest > ma_s > ma_m else '空頭排列' if tf_latest < ma_s < ma_m else '盤整'
                else:
                    ma_status = '數據不足'
                st.metric('均線狀態', ma_status)
            with col4:
                # KD 指標
                if len(tf_close) >= 9:
                    low_min = tf_low.rolling(9).min()
                    high_max = tf_high.rolling(9).max()
                    rsv = (tf_close - low_min) / (high_max - low_min) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    k_val = k.iloc[-1] if len(k) > 0 else 50
                    kd_status = '超買' if k_val > 80 else '超賣' if k_val < 20 else '中性'
                    st.metric('K值', f'{k_val:.1f}', kd_status)
                else:
                    st.metric('K值', '-', '數據不足')

            # RSI 圖
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=rsi_14.index, y=rsi_14, name='RSI(14)', line=dict(color='#2196F3')))
            fig_rsi.add_hline(y=70, line_dash='dash', line_color='red', annotation_text='超買')
            fig_rsi.add_hline(y=30, line_dash='dash', line_color='green', annotation_text='超賣')
            fig_rsi.update_layout(title=f'RSI 指標 ({tf_label})', **DEFAULT_PLOTLY_LAYOUT,height=250)
            st.plotly_chart(fig_rsi, use_container_width=True)

            # MACD 圖
            fig_macd = make_subplots(rows=1, cols=1)
            fig_macd.add_trace(go.Scatter(x=macd_line.index, y=macd_line, name='MACD', line=dict(color='#2196F3')))
            fig_macd.add_trace(go.Scatter(x=signal_line.index, y=signal_line, name='Signal', line=dict(color='#FF9800')))
            colors = ['#ef4444' if v >= 0 else '#22c55e' for v in histogram]
            fig_macd.add_trace(go.Bar(x=histogram.index, y=histogram, name='Histogram', marker_color=colors))
            fig_macd.update_layout(title=f'MACD 指標 ({tf_label})', **DEFAULT_PLOTLY_LAYOUT,height=250)
            st.plotly_chart(fig_macd, use_container_width=True)

            # KD 圖 (新增)
            if len(tf_close) >= 9:
                low_min = tf_low.rolling(9).min()
                high_max = tf_high.rolling(9).max()
                rsv = (tf_close - low_min) / (high_max - low_min) * 100
                k = rsv.ewm(com=2).mean()
                d = k.ewm(com=2).mean()

                fig_kd = go.Figure()
                fig_kd.add_trace(go.Scatter(x=k.index, y=k, name='K', line=dict(color='#2196F3')))
                fig_kd.add_trace(go.Scatter(x=d.index, y=d, name='D', line=dict(color='#FF9800')))
                fig_kd.add_hline(y=80, line_dash='dash', line_color='red', annotation_text='超買')
                fig_kd.add_hline(y=20, line_dash='dash', line_color='green', annotation_text='超賣')
                fig_kd.update_layout(title=f'KD 指標 ({tf_label})', **DEFAULT_PLOTLY_LAYOUT,height=250)
                st.plotly_chart(fig_kd, use_container_width=True)

        with sub_tab3:
            st.markdown(f'### 成交彙整 ({tf_label})')
            if tf_volume is not None and len(tf_volume) > 0:
                col1, col2, col3, col4 = st.columns(4)

                # 根據時間框架調整均量計算
                vol_short = min(5, len(tf_volume))
                vol_long = min(20, len(tf_volume))

                with col1:
                    avg_vol_short = tf_volume.tail(vol_short).mean() / 1000
                    vol_label_short = {
                        'D': f'{vol_short}日均量',
                        'W': f'{vol_short}週均量',
                        'M': f'{vol_short}月均量'
                    }
                    st.metric(vol_label_short[timeframe], f'{avg_vol_short:,.0f}張')
                with col2:
                    avg_vol_long = tf_volume.tail(vol_long).mean() / 1000
                    vol_label_long = {
                        'D': f'{vol_long}日均量',
                        'W': f'{vol_long}週均量',
                        'M': f'{vol_long}月均量'
                    }
                    st.metric(vol_label_long[timeframe], f'{avg_vol_long:,.0f}張')
                with col3:
                    latest_vol = tf_volume.iloc[-1] / 1000
                    vol_ratio = latest_vol / avg_vol_long if avg_vol_long > 0 else 1
                    period_label = {'D': '今日', 'W': '本週', 'M': '本月'}
                    st.metric(f'{period_label[timeframe]}成交量', f'{latest_vol:,.0f}張', f'均量比 {vol_ratio:.1f}x')
                with col4:
                    tf_latest_price = tf_close.iloc[-1] if len(tf_close) > 0 else latest_price
                    turnover = latest_vol * tf_latest_price / 1e8
                    st.metric('成交金額', f'{turnover:.2f}億')

                # 成交量分布圖
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Bar(x=tf_volume.index, y=tf_volume/1000, name='成交量',
                                        marker_color='steelblue'))
                if len(tf_volume) >= vol_long:
                    fig_vol.add_trace(go.Scatter(x=tf_volume.index,
                                                y=tf_volume.rolling(vol_long).mean()/1000,
                                                name=f'{vol_long}MA', line=dict(color='orange', width=2)))
                fig_vol.update_layout(title=f'成交量走勢 ({tf_label})', **DEFAULT_PLOTLY_LAYOUT,height=300)
                st.plotly_chart(fig_vol, use_container_width=True)
            else:
                st.warning('無成交量資料')

    # ==================== Tab 2: 籌碼分析 ====================
    with tab_chip:
        sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(['法人買賣', '資券變化', '外資持股', '大戶籌碼'])

        with sub_tab1:
            st.markdown('### 三大法人買賣超')
            if FINLAB_AVAILABLE:
                try:
                    foreign = load_finlab_data('institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)')
                    investment = load_finlab_data('institutional_investors_trading_summary:投信買賣超股數')
                    dealer = load_finlab_data('institutional_investors_trading_summary:自營商買賣超股數(自行買賣)')

                    if foreign is not None and selected_stock in foreign.columns:
                        foreign_data = (foreign[selected_stock].dropna().tail(60) / 1000).astype(int)
                        inv_data = (investment[selected_stock].dropna().tail(60) / 1000).astype(int) if investment is not None and selected_stock in investment.columns else pd.Series(dtype=int)
                        dealer_data = (dealer[selected_stock].dropna().tail(60) / 1000).astype(int) if dealer is not None and selected_stock in dealer.columns else pd.Series(dtype=int)

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            f5 = int(foreign_data.tail(5).sum())
                            st.metric('外資(5日)', f'{f5:+,}張', '買超' if f5 > 0 else '賣超',
                                     delta_color='normal' if f5 > 0 else 'inverse')
                        with col2:
                            i5 = int(inv_data.tail(5).sum()) if len(inv_data) >= 5 else 0
                            st.metric('投信(5日)', f'{i5:+,}張', '買超' if i5 > 0 else '賣超',
                                     delta_color='normal' if i5 > 0 else 'inverse')
                        with col3:
                            d5 = int(dealer_data.tail(5).sum()) if len(dealer_data) >= 5 else 0
                            st.metric('自營(5日)', f'{d5:+,}張', '買超' if d5 > 0 else '賣超',
                                     delta_color='normal' if d5 > 0 else 'inverse')
                        with col4:
                            total = f5 + i5 + d5
                            st.metric('合計(5日)', f'{total:+,}張', '買超' if total > 0 else '賣超',
                                     delta_color='normal' if total > 0 else 'inverse')

                        # 法人買賣超走勢圖
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=foreign_data.tail(20).index, y=foreign_data.tail(20),
                                            name='外資', marker_color='#1976D2'))
                        if len(inv_data) > 0:
                            fig.add_trace(go.Bar(x=inv_data.tail(20).index, y=inv_data.tail(20),
                                                name='投信', marker_color='#388E3C'))
                        if len(dealer_data) > 0:
                            fig.add_trace(go.Bar(x=dealer_data.tail(20).index, y=dealer_data.tail(20),
                                                name='自營', marker_color='#F57C00'))
                        fig.update_layout(title='三大法人買賣超 (近20日)', **DEFAULT_PLOTLY_LAYOUT,
                                         height=350, barmode='group')
                        st.plotly_chart(fig, use_container_width=True)

                        # 彙整表格
                        common_idx = foreign_data.tail(10).index
                        inst_df = pd.DataFrame({
                            '日期': common_idx.strftime('%m/%d'),
                            '外資': foreign_data.reindex(common_idx).fillna(0).astype(int).values,
                            '投信': inv_data.reindex(common_idx).fillna(0).astype(int).values if len(inv_data) > 0 else [0]*len(common_idx),
                            '自營': dealer_data.reindex(common_idx).fillna(0).astype(int).values if len(dealer_data) > 0 else [0]*len(common_idx),
                        })
                        inst_df['合計'] = inst_df['外資'] + inst_df['投信'] + inst_df['自營']
                        st.dataframe(inst_df.iloc[::-1], use_container_width=True, hide_index=True)
                    else:
                        st.warning('找不到法人買賣資料')
                except Exception as e:
                    show_error(e, title='載入法人資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab2:
            st.markdown('### 融資融券變化')
            if FINLAB_AVAILABLE:
                try:
                    margin_balance = load_finlab_data('margin_transactions:融資今日餘額')
                    short_balance = load_finlab_data('margin_transactions:融券今日餘額')

                    if margin_balance is not None and selected_stock in margin_balance.columns:
                        margin = margin_balance[selected_stock].dropna().tail(60)
                        short = short_balance[selected_stock].dropna().tail(60) if short_balance is not None and selected_stock in short_balance.columns else pd.Series(dtype=float)

                        if len(margin) > 0:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric('融資餘額', f'{int(margin.iloc[-1]):,}張',
                                         f'{int(margin.iloc[-1] - margin.iloc[-2]):+,}' if len(margin) > 1 else None)
                            with col2:
                                short_val = int(short.iloc[-1]) if len(short) > 0 else 0
                                short_chg = int(short.iloc[-1] - short.iloc[-2]) if len(short) > 1 else 0
                                st.metric('融券餘額', f'{short_val:,}張', f'{short_chg:+,}' if short_chg != 0 else None)
                            with col3:
                                ratio = (short_val / int(margin.iloc[-1]) * 100) if margin.iloc[-1] > 0 else 0
                                st.metric('券資比', f'{ratio:.2f}%')
                            with col4:
                                margin_util = load_finlab_data('margin_transactions:融資使用率')
                                if margin_util is not None and selected_stock in margin_util.columns:
                                    util = margin_util[selected_stock].dropna()
                                    st.metric('融資使用率', f'{util.iloc[-1]:.1f}%' if len(util) > 0 else '-')
                                else:
                                    st.metric('融資使用率', '-')

                            # 融資融券走勢圖
                            fig = make_subplots(specs=[[{"secondary_y": True}]])
                            fig.add_trace(go.Bar(x=margin.tail(30).index, y=margin.tail(30),
                                                name='融資餘額', marker_color='#ef4444'), secondary_y=False)
                            if len(short) > 0:
                                fig.add_trace(go.Scatter(x=short.tail(30).index, y=short.tail(30),
                                                        name='融券餘額', line=dict(color='#22c55e', width=2)),
                                             secondary_y=True)
                            fig.update_layout(title='融資融券走勢 (近30日)', **DEFAULT_PLOTLY_LAYOUT,height=350)
                            fig.update_yaxes(title_text='融資(張)', secondary_y=False)
                            fig.update_yaxes(title_text='融券(張)', secondary_y=True)
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning('找不到融資融券資料')
                except Exception as e:
                    show_error(e, title='載入融資融券資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab3:
            st.markdown('### 外資持股比率')
            if FINLAB_AVAILABLE:
                try:
                    foreign_hold = load_finlab_data('foreign_investors_shareholding:全體外資及陸資持股比率')
                    if foreign_hold is not None and selected_stock in foreign_hold.columns:
                        hold = foreign_hold[selected_stock].dropna().tail(120)
                        if len(hold) > 0:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric('外資持股比率', f'{hold.iloc[-1]:.2f}%',
                                         f'{hold.iloc[-1] - hold.iloc[-2]:+.2f}%' if len(hold) > 1 else None)
                            with col2:
                                hold_max = hold.max()
                                st.metric('近半年最高', f'{hold_max:.2f}%')
                            with col3:
                                hold_min = hold.min()
                                st.metric('近半年最低', f'{hold_min:.2f}%')

                            fig = go.Figure()
                            fig.add_trace(go.Scatter(x=hold.index, y=hold, fill='tozeroy',
                                                    name='外資持股比率', line=dict(color='#1976D2')))
                            fig.update_layout(title='外資持股比率走勢', **DEFAULT_PLOTLY_LAYOUT,height=300)
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning('找不到外資持股資料')
                except Exception as e:
                    show_error(e, title='載入外資持股資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab4:
            st.markdown('### 大戶籌碼集中度')
            if FINLAB_AVAILABLE:
                try:
                    # 載入集保餘額資料 - 各級距股數和人數
                    big_holder_shares = load_finlab_data('etl:inventory:大於四百張股數')
                    big_holder_count = load_finlab_data('etl:inventory:大於四百張人數')
                    big_holder_pct = load_finlab_data('etl:inventory:大於四百張佔比')

                    small_holder_shares = load_finlab_data('etl:inventory:小於十張股數')
                    small_holder_count = load_finlab_data('etl:inventory:小於十張人數')
                    small_holder_pct = load_finlab_data('etl:inventory:小於十張佔比')

                    total_holders = load_finlab_data('etl:inventory:全部人數')

                    # 千張大戶
                    super_big_shares = load_finlab_data('etl:inventory:大於一千張股數')
                    super_big_pct = load_finlab_data('etl:inventory:大於一千張佔比')

                    if big_holder_pct is not None and selected_stock in big_holder_pct.columns:
                        big_pct = big_holder_pct[selected_stock].dropna().tail(52)  # 約一年週資料

                        if len(big_pct) > 0:
                            col1, col2, col3, col4 = st.columns(4)

                            with col1:
                                latest_big_pct = big_pct.iloc[-1]
                                prev_big_pct = big_pct.iloc[-2] if len(big_pct) > 1 else latest_big_pct
                                chg = latest_big_pct - prev_big_pct
                                st.metric('400張以上持股比例',
                                         f'{latest_big_pct:.2f}%',
                                         f'{chg:+.2f}%' if chg != 0 else None,
                                         delta_color='normal' if chg > 0 else 'inverse')

                            with col2:
                                if super_big_pct is not None and selected_stock in super_big_pct.columns:
                                    sb_pct = super_big_pct[selected_stock].dropna()
                                    if len(sb_pct) > 0:
                                        st.metric('千張大戶持股比例', f'{sb_pct.iloc[-1]:.2f}%')

                            with col3:
                                if small_holder_pct is not None and selected_stock in small_holder_pct.columns:
                                    sm_pct = small_holder_pct[selected_stock].dropna()
                                    if len(sm_pct) > 0:
                                        st.metric('散戶持股比例 (<10張)', f'{sm_pct.iloc[-1]:.2f}%')

                            with col4:
                                if total_holders is not None and selected_stock in total_holders.columns:
                                    th = total_holders[selected_stock].dropna()
                                    if len(th) > 0:
                                        prev_th = th.iloc[-2] if len(th) > 1 else th.iloc[-1]
                                        th_chg = int(th.iloc[-1] - prev_th)
                                        st.metric('股東總人數',
                                                 f'{int(th.iloc[-1]):,}人',
                                                 f'{th_chg:+,}人' if th_chg != 0 else None,
                                                 delta_color='inverse' if th_chg > 0 else 'normal')  # 人數減少=籌碼集中

                            # 籌碼集中度走勢圖
                            fig = make_subplots(specs=[[{"secondary_y": True}]])

                            fig.add_trace(go.Scatter(
                                x=big_pct.index, y=big_pct,
                                name='大戶持股比例 (>400張)',
                                fill='tozeroy',
                                line=dict(color='#1976D2')
                            ), secondary_y=False)

                            if total_holders is not None and selected_stock in total_holders.columns:
                                th = total_holders[selected_stock].dropna().tail(52)
                                fig.add_trace(go.Scatter(
                                    x=th.index, y=th,
                                    name='股東人數',
                                    line=dict(color='#FF9800', dash='dot')
                                ), secondary_y=True)

                            fig.update_layout(title='籌碼集中度變化',
                                            **DEFAULT_PLOTLY_LAYOUT,height=350)
                            fig.update_yaxes(title_text='持股比例 (%)', secondary_y=False)
                            fig.update_yaxes(title_text='股東人數', secondary_y=True)
                            st.plotly_chart(fig, use_container_width=True)

                            # 各級距股東分布
                            st.markdown('#### 股東分級分布')

                            # 收集各級距資料
                            levels = [
                                ('大於一千張', 'etl:inventory:大於一千張佔比'),
                                ('400-1000張', None),  # 需計算
                                ('100-400張', None),
                                ('50-100張', None),
                                ('10-50張', None),
                                ('小於十張', 'etl:inventory:小於十張佔比'),
                            ]

                            # 簡化：直接顯示幾個主要級距
                            dist_data = []
                            for level_name, data_key in [
                                ('千張大戶 (>1000張)', 'etl:inventory:大於一千張佔比'),
                                ('大戶 (400-1000張)', None),
                                ('中實戶 (100-400張)', None),
                                ('小額投資人 (<100張)', None),
                            ]:
                                if data_key:
                                    d = load_finlab_data(data_key)
                                    if d is not None and selected_stock in d.columns:
                                        val = d[selected_stock].dropna()
                                        if len(val) > 0:
                                            dist_data.append({
                                                '級距': level_name,
                                                '持股比例': f'{val.iloc[-1]:.2f}%',
                                                '比例值': val.iloc[-1]
                                            })

                            # 補上其他計算級距
                            if big_holder_pct is not None and selected_stock in big_holder_pct.columns:
                                big_400 = big_holder_pct[selected_stock].dropna().iloc[-1] if len(big_holder_pct[selected_stock].dropna()) > 0 else 0
                                super_big = super_big_pct[selected_stock].dropna().iloc[-1] if super_big_pct is not None and selected_stock in super_big_pct.columns and len(super_big_pct[selected_stock].dropna()) > 0 else 0
                                big_100_400_data = load_finlab_data('etl:inventory:大於一百張佔比')
                                big_100 = big_100_400_data[selected_stock].dropna().iloc[-1] if big_100_400_data is not None and selected_stock in big_100_400_data.columns and len(big_100_400_data[selected_stock].dropna()) > 0 else 0

                                # 計算中間級距
                                pct_400_1000 = big_400 - super_big
                                pct_100_400 = big_100 - big_400

                                small_pct_val = small_holder_pct[selected_stock].dropna().iloc[-1] if small_holder_pct is not None and selected_stock in small_holder_pct.columns and len(small_holder_pct[selected_stock].dropna()) > 0 else 0
                                pct_below_100 = 100 - big_100

                                # 圓餅圖
                                fig_pie = go.Figure(data=[go.Pie(
                                    labels=['千張大戶', '大戶(400-1000張)', '中實戶(100-400張)', '小額投資人(<100張)'],
                                    values=[super_big, pct_400_1000, pct_100_400, pct_below_100],
                                    hole=.4,
                                    marker_colors=['#1976D2', '#42A5F5', '#90CAF9', '#BBDEFB']
                                )])
                                fig_pie.update_layout(title='股東持股分布', height=350)
                                st.plotly_chart(fig_pie, use_container_width=True)

                            # 籌碼集中度評估
                            st.markdown('#### 籌碼集中度評估')
                            latest_big = big_pct.iloc[-1]
                            if latest_big > 60:
                                st.success(f'籌碼高度集中 ({latest_big:.1f}%)：大戶持股超過60%，股價較易受大戶操控')
                            elif latest_big > 40:
                                st.info(f'籌碼中度集中 ({latest_big:.1f}%)：大戶與散戶持股較為均衡')
                            else:
                                st.warning(f'籌碼較為分散 ({latest_big:.1f}%)：散戶持股較多，股價波動可能較大')

                    else:
                        st.warning('找不到集保餘額資料')
                except Exception as e:
                    show_error(e, title='載入集保餘額資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

    # ==================== Tab 3: 估價分析 ====================
    with tab_valuation:
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(['本益比河流圖', '股價淨值比河流圖', '多空分析'])

        with sub_tab1:
            st.markdown('### 本益比河流圖')
            if FINLAB_AVAILABLE:
                try:
                    pe_data = load_finlab_data('price_earning_ratio:本益比')
                    if pe_data is not None and selected_stock in pe_data.columns:
                        pe = pe_data[selected_stock].dropna().tail(756)  # 3年
                        close_3y = close.tail(len(pe)).reindex(pe.index)

                        if len(pe) > 0:
                            # 計算本益比河流
                            eps_ttm = close_3y / pe  # 推算 EPS
                            pe_bands = {}
                            for multiple in [8, 12, 16, 20, 24, 28]:
                                pe_bands[f'PE {multiple}x'] = eps_ttm * multiple

                            fig = go.Figure()

                            # 填充區域
                            colors = ['rgba(76, 175, 80, 0.3)', 'rgba(139, 195, 74, 0.3)',
                                     'rgba(255, 235, 59, 0.3)', 'rgba(255, 152, 0, 0.3)',
                                     'rgba(244, 67, 54, 0.3)']
                            multiples = [8, 12, 16, 20, 24, 28]
                            for i in range(len(multiples)-1):
                                low_band = eps_ttm * multiples[i]
                                high_band = eps_ttm * multiples[i+1]
                                fig.add_trace(go.Scatter(
                                    x=list(pe.index) + list(pe.index[::-1]),
                                    y=list(low_band) + list(high_band[::-1]),
                                    fill='toself', fillcolor=colors[i],
                                    line=dict(color='rgba(0,0,0,0)'),
                                    name=f'PE {multiples[i]}-{multiples[i+1]}x'
                                ))

                            # 股價線
                            fig.add_trace(go.Scatter(x=close_3y.index, y=close_3y,
                                                    name='股價', line=dict(color='#1976D2', width=2)))

                            fig.update_layout(title=f'{selected_stock} 本益比河流圖',
                                            **DEFAULT_PLOTLY_LAYOUT,height=450)
                            st.plotly_chart(fig, use_container_width=True)

                            # 目前估值位置
                            current_pe = pe.iloc[-1]
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric('目前本益比', f'{current_pe:.2f}')
                            with col2:
                                pe_avg = pe.mean()
                                st.metric('平均本益比', f'{pe_avg:.2f}')
                            with col3:
                                pe_std = pe.std()
                                pe_z = (current_pe - pe_avg) / pe_std if pe_std > 0 else 0
                                st.metric('Z-Score', f'{pe_z:.2f}',
                                         '偏貴' if pe_z > 1 else '偏低' if pe_z < -1 else '合理')
                            with col4:
                                percentile = (pe < current_pe).sum() / len(pe) * 100
                                st.metric('百分位', f'{percentile:.0f}%')
                    else:
                        st.warning('找不到本益比資料')
                except Exception as e:
                    show_error(e, title='載入本益比資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab2:
            st.markdown('### 股價淨值比河流圖')
            if FINLAB_AVAILABLE:
                try:
                    pb_data = load_finlab_data('price_earning_ratio:股價淨值比')
                    if pb_data is not None and selected_stock in pb_data.columns:
                        pb = pb_data[selected_stock].dropna().tail(756)
                        close_3y = close.tail(len(pb)).reindex(pb.index)

                        if len(pb) > 0:
                            bv_per_share = close_3y / pb  # 推算每股淨值

                            fig = go.Figure()

                            # 填充區域
                            colors = ['rgba(76, 175, 80, 0.3)', 'rgba(139, 195, 74, 0.3)',
                                     'rgba(255, 235, 59, 0.3)', 'rgba(255, 152, 0, 0.3)',
                                     'rgba(244, 67, 54, 0.3)']
                            multiples = [0.8, 1.2, 1.6, 2.0, 2.5, 3.0]
                            for i in range(len(multiples)-1):
                                low_band = bv_per_share * multiples[i]
                                high_band = bv_per_share * multiples[i+1]
                                fig.add_trace(go.Scatter(
                                    x=list(pb.index) + list(pb.index[::-1]),
                                    y=list(low_band) + list(high_band[::-1]),
                                    fill='toself', fillcolor=colors[i],
                                    line=dict(color='rgba(0,0,0,0)'),
                                    name=f'PB {multiples[i]}-{multiples[i+1]}x'
                                ))

                            fig.add_trace(go.Scatter(x=close_3y.index, y=close_3y,
                                                    name='股價', line=dict(color='#1976D2', width=2)))

                            fig.update_layout(title=f'{selected_stock} 股價淨值比河流圖',
                                            **DEFAULT_PLOTLY_LAYOUT,height=450)
                            st.plotly_chart(fig, use_container_width=True)

                            current_pb = pb.iloc[-1]
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric('目前PB', f'{current_pb:.2f}')
                            with col2:
                                pb_avg = pb.mean()
                                st.metric('平均PB', f'{pb_avg:.2f}')
                            with col3:
                                pb_std = pb.std()
                                pb_z = (current_pb - pb_avg) / pb_std if pb_std > 0 else 0
                                st.metric('Z-Score', f'{pb_z:.2f}',
                                         '偏貴' if pb_z > 1 else '偏低' if pb_z < -1 else '合理')
                            with col4:
                                percentile = (pb < current_pb).sum() / len(pb) * 100
                                st.metric('百分位', f'{percentile:.0f}%')
                    else:
                        st.warning('找不到股價淨值比資料')
                except Exception as e:
                    show_error(e, title='載入股價淨值比資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab3:
            st.markdown('### 多空分析')
            # 綜合多空訊號
            signals = []
            bullish = 0
            bearish = 0

            # RSI
            rsi_val = rsi(close_period, 14).iloc[-1]
            if not pd.isna(rsi_val):
                if rsi_val > 70:
                    signals.append(('RSI(14)', f'{rsi_val:.1f}', '超買', '🔴'))
                    bearish += 1
                elif rsi_val < 30:
                    signals.append(('RSI(14)', f'{rsi_val:.1f}', '超賣', '🟢'))
                    bullish += 1
                else:
                    signals.append(('RSI(14)', f'{rsi_val:.1f}', '中性', '⚪'))

            # MACD
            macd_l, sig_l, _ = macd(close_period)
            if not pd.isna(macd_l.iloc[-1]):
                if macd_l.iloc[-1] > sig_l.iloc[-1]:
                    signals.append(('MACD', f'{macd_l.iloc[-1]:.2f}', '多頭', '🟢'))
                    bullish += 1
                else:
                    signals.append(('MACD', f'{macd_l.iloc[-1]:.2f}', '空頭', '🔴'))
                    bearish += 1

            # 均線
            ma5 = close_period.rolling(5).mean().iloc[-1]
            ma20 = close_period.rolling(20).mean().iloc[-1]
            ma60 = close_period.rolling(60).mean().iloc[-1] if len(close_period) >= 60 else ma20
            if latest_price > ma5 > ma20 > ma60:
                signals.append(('均線排列', '多頭排列', '強勢', '🟢'))
                bullish += 2
            elif latest_price < ma5 < ma20 < ma60:
                signals.append(('均線排列', '空頭排列', '弱勢', '🔴'))
                bearish += 2
            else:
                signals.append(('均線排列', '盤整', '中性', '⚪'))

            # 成交量
            if volume_period is not None:
                vol_ma = volume_period.rolling(20).mean().iloc[-1]
                if volume_period.iloc[-1] > vol_ma * 1.5:
                    signals.append(('成交量', '放量', '關注', '🟡'))
                elif volume_period.iloc[-1] < vol_ma * 0.5:
                    signals.append(('成交量', '縮量', '觀望', '⚪'))
                else:
                    signals.append(('成交量', '正常', '中性', '⚪'))

            signal_df = pd.DataFrame(signals, columns=['指標', '數值', '狀態', '訊號'])
            st.dataframe(signal_df, use_container_width=True, hide_index=True)

            # 綜合評分
            score = bullish - bearish
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric('多頭訊號', f'{bullish}')
            with col2:
                st.metric('空頭訊號', f'{bearish}')
            with col3:
                if score >= 2:
                    st.success(f'**綜合建議: 偏多** (分數: {score:+d})')
                elif score <= -2:
                    st.error(f'**綜合建議: 偏空** (分數: {score:+d})')
                else:
                    st.info(f'**綜合建議: 中性** (分數: {score:+d})')

    # ==================== Tab 4: 財務分析 ====================
    with tab_finance:
        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5, sub_tab6, sub_tab7 = st.tabs([
            '營收表', '每股盈餘', '獲利能力', '財務健全', '損益表', '資產負債表', '現金流量'
        ])

        with sub_tab1:
            st.markdown('### 月營收趨勢')
            if selected_stock in data['monthly_revenue'].columns:
                revenue = data['monthly_revenue'][selected_stock].dropna().tail(24)
                revenue_yoy = data['revenue_yoy'][selected_stock].dropna().tail(24) if selected_stock in data['revenue_yoy'].columns else None

                if len(revenue) > 0:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric('最新營收', f'{revenue.iloc[-1]/1e8:.2f}億')
                    with col2:
                        if revenue_yoy is not None and len(revenue_yoy) > 0:
                            yoy = revenue_yoy.iloc[-1]
                            st.metric('年增率', f'{yoy:.1f}%', '成長' if yoy > 0 else '衰退',
                                     delta_color='normal' if yoy > 0 else 'inverse')
                    with col3:
                        cum_revenue = revenue.tail(12).sum()
                        st.metric('近12月累計', f'{cum_revenue/1e8:.1f}億')
                    with col4:
                        avg_revenue = revenue.mean()
                        st.metric('平均月營收', f'{avg_revenue/1e8:.2f}億')

                    # 營收走勢圖
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Bar(x=revenue.index, y=revenue/1e8, name='月營收(億)',
                                        marker_color='steelblue'), secondary_y=False)
                    if revenue_yoy is not None and len(revenue_yoy) > 0:
                        fig.add_trace(go.Scatter(x=revenue_yoy.index, y=revenue_yoy, name='年增率(%)',
                                                line=dict(color='orange', width=2)), secondary_y=True)
                    fig.update_layout(title='月營收與年增率', **DEFAULT_PLOTLY_LAYOUT,height=400)
                    fig.update_yaxes(title_text='營收(億)', secondary_y=False)
                    fig.update_yaxes(title_text='年增率(%)', secondary_y=True)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info('無營收數據')

        with sub_tab2:
            st.markdown('### 每股盈餘 (EPS)')
            if FINLAB_AVAILABLE:
                try:
                    eps_data = load_finlab_data('financial_statement:每股盈餘')
                    if eps_data is not None and selected_stock in eps_data.columns:
                        eps = eps_data[selected_stock].dropna().tail(16)  # 4年
                        if len(eps) > 0:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric('最新EPS', f'{eps.iloc[-1]:.2f}')
                            with col2:
                                # 近四季合計
                                eps_ttm = eps.tail(4).sum()
                                st.metric('近四季EPS', f'{eps_ttm:.2f}')
                            with col3:
                                eps_growth = ((eps.iloc[-1] / eps.iloc[-5]) - 1) * 100 if len(eps) >= 5 else 0
                                st.metric('年成長率', f'{eps_growth:.1f}%')

                            fig = go.Figure()
                            fig.add_trace(go.Bar(x=[str(x) for x in eps.index], y=eps,
                                                name='EPS', marker_color='steelblue'))
                            fig.update_layout(title='每季EPS趨勢', **DEFAULT_PLOTLY_LAYOUT,height=350)
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning('找不到EPS資料')
                except Exception as e:
                    show_error(e, title='載入EPS資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab3:
            st.markdown('### 獲利能力')
            if FINLAB_AVAILABLE:
                try:
                    roe = load_finlab_data('fundamental_features:ROE稅後')
                    roa = load_finlab_data('fundamental_features:ROA稅後息前')
                    gross_margin = load_finlab_data('fundamental_features:營業毛利率')
                    operating_margin = load_finlab_data('fundamental_features:營業利益率')

                    metrics = []
                    if roe is not None and selected_stock in roe.columns:
                        roe_val = roe[selected_stock].dropna()
                        if len(roe_val) > 0:
                            metrics.append(('ROE', f'{roe_val.iloc[-1]:.2f}%', roe_val))
                    if roa is not None and selected_stock in roa.columns:
                        roa_val = roa[selected_stock].dropna()
                        if len(roa_val) > 0:
                            metrics.append(('ROA', f'{roa_val.iloc[-1]:.2f}%', roa_val))
                    if gross_margin is not None and selected_stock in gross_margin.columns:
                        gm_val = gross_margin[selected_stock].dropna()
                        if len(gm_val) > 0:
                            metrics.append(('毛利率', f'{gm_val.iloc[-1]:.2f}%', gm_val))
                    if operating_margin is not None and selected_stock in operating_margin.columns:
                        om_val = operating_margin[selected_stock].dropna()
                        if len(om_val) > 0:
                            metrics.append(('營業利益率', f'{om_val.iloc[-1]:.2f}%', om_val))

                    if metrics:
                        cols = st.columns(len(metrics))
                        for i, (name, val, _) in enumerate(metrics):
                            with cols[i]:
                                st.metric(name, val)

                        # 獲利能力走勢
                        fig = go.Figure()
                        for name, _, series in metrics:
                            fig.add_trace(go.Scatter(x=[str(x) for x in series.tail(12).index],
                                                    y=series.tail(12), name=name))
                        fig.update_layout(title='獲利能力趨勢', **DEFAULT_PLOTLY_LAYOUT,height=350)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning('找不到獲利能力資料')
                except Exception as e:
                    show_error(e, title='載入獲利能力資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        with sub_tab4:
            st.markdown('### 財務健全度')
            if FINLAB_AVAILABLE:
                try:
                    current_ratio = load_finlab_data('fundamental_features:流動比率')
                    debt_ratio = load_finlab_data('fundamental_features:負債比率')

                    if current_ratio is not None and selected_stock in current_ratio.columns:
                        cr = current_ratio[selected_stock].dropna()
                        dr = debt_ratio[selected_stock].dropna() if debt_ratio is not None and selected_stock in debt_ratio.columns else pd.Series(dtype=float)

                        col1, col2 = st.columns(2)
                        with col1:
                            if len(cr) > 0:
                                st.metric('流動比率', f'{cr.iloc[-1]:.2f}%',
                                         '健全' if cr.iloc[-1] > 150 else '偏低')
                        with col2:
                            if len(dr) > 0:
                                st.metric('負債比率', f'{dr.iloc[-1]:.2f}%',
                                         '偏高' if dr.iloc[-1] > 50 else '健全',
                                         delta_color='inverse' if dr.iloc[-1] > 50 else 'normal')
                    else:
                        st.warning('找不到財務健全度資料')
                except Exception as e:
                    show_error(e, title='載入財務健全度資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        # ==================== 損益表 ====================
        with sub_tab5:
            st.markdown('### 損益表 (季度)')
            if FINLAB_AVAILABLE:
                try:
                    # 載入損益表相關資料
                    revenue = load_finlab_data('financial_statement:營業收入淨額')
                    cost = load_finlab_data('financial_statement:營業成本')
                    gross_profit = load_finlab_data('financial_statement:營業毛利')
                    operating_expense = load_finlab_data('financial_statement:營業費用')
                    operating_income = load_finlab_data('financial_statement:營業利益')
                    pretax_income = load_finlab_data('financial_statement:稅前淨利')
                    net_income = load_finlab_data('financial_statement:歸屬母公司淨利_損')
                    eps_data = load_finlab_data('financial_statement:每股盈餘')

                    if revenue is not None and selected_stock in revenue.columns:
                        # 取得最近 8 季資料
                        quarters = 8

                        income_data = []
                        rev = revenue[selected_stock].dropna().tail(quarters)

                        for q in rev.index:
                            row = {'季度': str(q)[:7]}

                            # 營收
                            if selected_stock in revenue.columns:
                                val = revenue[selected_stock].get(q, None)
                                row['營業收入'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 營業成本
                            if cost is not None and selected_stock in cost.columns:
                                val = cost[selected_stock].get(q, None)
                                row['營業成本'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 毛利
                            if gross_profit is not None and selected_stock in gross_profit.columns:
                                val = gross_profit[selected_stock].get(q, None)
                                row['營業毛利'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 營業費用
                            if operating_expense is not None and selected_stock in operating_expense.columns:
                                val = operating_expense[selected_stock].get(q, None)
                                row['營業費用'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 營業利益
                            if operating_income is not None and selected_stock in operating_income.columns:
                                val = operating_income[selected_stock].get(q, None)
                                row['營業利益'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 稅前淨利
                            if pretax_income is not None and selected_stock in pretax_income.columns:
                                val = pretax_income[selected_stock].get(q, None)
                                row['稅前淨利'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 歸屬母公司淨利
                            if net_income is not None and selected_stock in net_income.columns:
                                val = net_income[selected_stock].get(q, None)
                                row['稅後淨利'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # EPS
                            if eps_data is not None and selected_stock in eps_data.columns:
                                val = eps_data[selected_stock].get(q, None)
                                row['EPS'] = f'{val:.2f}' if pd.notna(val) else '-'

                            income_data.append(row)

                        income_df = pd.DataFrame(income_data)
                        st.dataframe(income_df.iloc[::-1], use_container_width=True, hide_index=True)

                        # 損益趨勢圖
                        if net_income is not None and selected_stock in net_income.columns:
                            ni = net_income[selected_stock].dropna().tail(quarters)
                            oi = operating_income[selected_stock].dropna().tail(quarters) if operating_income is not None and selected_stock in operating_income.columns else None

                            fig = go.Figure()
                            if oi is not None:
                                fig.add_trace(go.Bar(x=[str(x)[:7] for x in oi.index], y=oi/1e8,
                                                    name='營業利益', marker_color='#2196F3'))
                            fig.add_trace(go.Bar(x=[str(x)[:7] for x in ni.index], y=ni/1e8,
                                                name='稅後淨利', marker_color='#4CAF50'))
                            fig.update_layout(title='季度獲利趨勢', **DEFAULT_PLOTLY_LAYOUT,
                                            height=350, barmode='group')
                            fig.update_yaxes(title_text='金額 (億元)')
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning('找不到損益表資料')
                except Exception as e:
                    show_error(e, title='載入損益表資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        # ==================== 資產負債表 ====================
        with sub_tab6:
            st.markdown('### 資產負債表 (季度)')
            if FINLAB_AVAILABLE:
                try:
                    # 載入資產負債表資料
                    current_assets = load_finlab_data('financial_statement:流動資產')
                    non_current_assets = load_finlab_data('financial_statement:非流動資產')
                    total_assets = load_finlab_data('financial_statement:資產總額')
                    current_liab = load_finlab_data('financial_statement:流動負債')
                    non_current_liab = load_finlab_data('financial_statement:非流動負債')
                    total_liab = load_finlab_data('financial_statement:負債總額')
                    equity = load_finlab_data('financial_statement:股東權益總額')
                    cash = load_finlab_data('financial_statement:現金及約當現金')
                    inventory = load_finlab_data('financial_statement:存貨')
                    receivable = load_finlab_data('financial_statement:應收帳款及票據')

                    if total_assets is not None and selected_stock in total_assets.columns:
                        quarters = 8
                        ta = total_assets[selected_stock].dropna().tail(quarters)

                        bs_data = []
                        for q in ta.index:
                            row = {'季度': str(q)[:7]}

                            # 資產
                            if selected_stock in total_assets.columns:
                                val = total_assets[selected_stock].get(q, None)
                                row['資產總額'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            if current_assets is not None and selected_stock in current_assets.columns:
                                val = current_assets[selected_stock].get(q, None)
                                row['流動資產'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            if cash is not None and selected_stock in cash.columns:
                                val = cash[selected_stock].get(q, None)
                                row['現金'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            if receivable is not None and selected_stock in receivable.columns:
                                val = receivable[selected_stock].get(q, None)
                                row['應收帳款'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            if inventory is not None and selected_stock in inventory.columns:
                                val = inventory[selected_stock].get(q, None)
                                row['存貨'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 負債
                            if total_liab is not None and selected_stock in total_liab.columns:
                                val = total_liab[selected_stock].get(q, None)
                                row['負債總額'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            if current_liab is not None and selected_stock in current_liab.columns:
                                val = current_liab[selected_stock].get(q, None)
                                row['流動負債'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            # 股東權益
                            if equity is not None and selected_stock in equity.columns:
                                val = equity[selected_stock].get(q, None)
                                row['股東權益'] = f'{val/1e8:.1f}億' if pd.notna(val) else '-'

                            bs_data.append(row)

                        bs_df = pd.DataFrame(bs_data)
                        st.dataframe(bs_df.iloc[::-1], use_container_width=True, hide_index=True)

                        # 資產負債結構圖
                        col1, col2 = st.columns(2)

                        with col1:
                            # 最新一季資產結構
                            latest_q = ta.index[-1]
                            ca_val = current_assets[selected_stock].get(latest_q, 0) if current_assets is not None and selected_stock in current_assets.columns else 0
                            nca_val = non_current_assets[selected_stock].get(latest_q, 0) if non_current_assets is not None and selected_stock in non_current_assets.columns else 0

                            if ca_val > 0 or nca_val > 0:
                                fig_asset = go.Figure(data=[go.Pie(
                                    labels=['流動資產', '非流動資產'],
                                    values=[ca_val, nca_val],
                                    hole=.4,
                                    marker_colors=['#4CAF50', '#2196F3']
                                )])
                                fig_asset.update_layout(title='資產結構', height=300)
                                st.plotly_chart(fig_asset, use_container_width=True)

                        with col2:
                            # 最新一季負債與權益結構
                            tl_val = total_liab[selected_stock].get(latest_q, 0) if total_liab is not None and selected_stock in total_liab.columns else 0
                            eq_val = equity[selected_stock].get(latest_q, 0) if equity is not None and selected_stock in equity.columns else 0

                            if tl_val > 0 or eq_val > 0:
                                fig_liab = go.Figure(data=[go.Pie(
                                    labels=['負債', '股東權益'],
                                    values=[tl_val, eq_val],
                                    hole=.4,
                                    marker_colors=['#f44336', '#4CAF50']
                                )])
                                fig_liab.update_layout(title='負債與權益結構', height=300)
                                st.plotly_chart(fig_liab, use_container_width=True)
                    else:
                        st.warning('找不到資產負債表資料')
                except Exception as e:
                    show_error(e, title='載入資產負債表資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

        # ==================== 現金流量表 ====================
        with sub_tab7:
            st.markdown('### 現金流量分析')
            if FINLAB_AVAILABLE:
                try:
                    # 載入現金流量相關資料
                    operating_cf = load_finlab_data('fundamental_features:營運現金流')
                    invest_cf = load_finlab_data('financial_statement:取得不動產廠房及設備')
                    cash_flow_ratio = load_finlab_data('fundamental_features:現金流量比率')
                    per_share_cf = load_finlab_data('fundamental_features:每股現金流量')

                    if operating_cf is not None and selected_stock in operating_cf.columns:
                        ocf = operating_cf[selected_stock].dropna().tail(12)

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric('營運現金流', f'{ocf.iloc[-1]/1e8:.1f}億',
                                     '正向' if ocf.iloc[-1] > 0 else '負向',
                                     delta_color='normal' if ocf.iloc[-1] > 0 else 'inverse')
                        with col2:
                            if per_share_cf is not None and selected_stock in per_share_cf.columns:
                                pscf = per_share_cf[selected_stock].dropna()
                                if len(pscf) > 0:
                                    st.metric('每股現金流', f'{pscf.iloc[-1]:.2f}')
                        with col3:
                            if cash_flow_ratio is not None and selected_stock in cash_flow_ratio.columns:
                                cfr = cash_flow_ratio[selected_stock].dropna()
                                if len(cfr) > 0:
                                    st.metric('現金流量比率', f'{cfr.iloc[-1]:.1f}%')
                        with col4:
                            # 自由現金流 = 營運現金流 - 資本支出
                            if invest_cf is not None and selected_stock in invest_cf.columns:
                                icf = invest_cf[selected_stock].dropna()
                                if len(icf) > 0 and len(ocf) > 0:
                                    # 取得不動產廠房設備通常為負數 (支出)
                                    fcf = ocf.iloc[-1] + icf.iloc[-1]  # 加上負值 = 減去
                                    st.metric('自由現金流', f'{fcf/1e8:.1f}億',
                                             '正向' if fcf > 0 else '負向',
                                             delta_color='normal' if fcf > 0 else 'inverse')

                        # 現金流量走勢
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=[str(x)[:7] for x in ocf.index], y=ocf/1e8,
                                            name='營運現金流', marker_color='#4CAF50'))

                        if invest_cf is not None and selected_stock in invest_cf.columns:
                            icf = invest_cf[selected_stock].dropna().tail(12)
                            # 投資活動現金流 (取得不動產廠房設備，通常為負)
                            fig.add_trace(go.Bar(x=[str(x)[:7] for x in icf.index], y=icf/1e8,
                                                name='投資支出', marker_color='#f44336'))

                        fig.update_layout(title='現金流量趨勢', **DEFAULT_PLOTLY_LAYOUT,
                                        height=350, barmode='group')
                        fig.update_yaxes(title_text='金額 (億元)')
                        st.plotly_chart(fig, use_container_width=True)

                        # 現金流量品質分析
                        st.markdown('#### 現金流量品質')
                        net_income = load_finlab_data('financial_statement:歸屬母公司淨利_損')
                        if net_income is not None and selected_stock in net_income.columns:
                            ni = net_income[selected_stock].dropna().tail(4).sum()
                            ocf_4q = ocf.tail(4).sum()
                            if ni != 0:
                                quality_ratio = ocf_4q / ni * 100
                                quality_text = '良好' if quality_ratio > 80 else '普通' if quality_ratio > 50 else '較差'
                                quality_color = 'success' if quality_ratio > 80 else 'warning' if quality_ratio > 50 else 'error'

                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric('盈餘品質 (營運現金流/淨利)', f'{quality_ratio:.0f}%', quality_text)
                                with col2:
                                    if quality_ratio > 80:
                                        st.success('獲利有實際現金流入支撐')
                                    elif quality_ratio > 50:
                                        st.warning('現金流入略低於帳面獲利')
                                    else:
                                        st.error('帳面獲利未能轉化為現金')
                    else:
                        st.warning('找不到現金流量資料')
                except Exception as e:
                    show_error(e, title='載入現金流量資料失敗', suggestion='請檢查 FinLab API 連線狀態')
            else:
                st.warning('FinLab API 未載入')

    # ==================== Tab 5: 基本資料 ====================
    with tab_basic:
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(['公司資訊', '股利政策', '同業比較'])

        with sub_tab1:
            st.markdown('### 公司基本資訊')
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                | 項目 | 內容 |
                |------|------|
                | 股票代碼 | {selected_stock} |
                | 公司名稱 | {name} |
                | 產業類別 | {category} |
                | 上市市場 | {market} |
                """)
            with col2:
                if FINLAB_AVAILABLE:
                    try:
                        market_value = load_finlab_data('etl:market_value')
                        if market_value is not None and selected_stock in market_value.columns:
                            mv = market_value[selected_stock].dropna()
                            if len(mv) > 0:
                                st.metric('市值', f'{mv.iloc[-1]/1e8:.0f}億')
                    except Exception:
                        pass

        with sub_tab2:
            st.markdown('### 股利政策')
            if selected_stock in data['dividend_yield'].columns:
                dy = data['dividend_yield'][selected_stock].dropna()
                if len(dy) > 0:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric('現金殖利率', f'{dy.iloc[-1]:.2f}%')
                    with col2:
                        dy_avg = dy.tail(252).mean()
                        st.metric('一年平均殖利率', f'{dy_avg:.2f}%')
                    with col3:
                        dy_max = dy.tail(252).max()
                        st.metric('一年最高殖利率', f'{dy_max:.2f}%')

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=dy.tail(252).index, y=dy.tail(252),
                                            fill='tozeroy', name='殖利率', line=dict(color='#4CAF50')))
                    fig.update_layout(title='殖利率走勢', **DEFAULT_PLOTLY_LAYOUT,height=300)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info('無殖利率資料')

        with sub_tab3:
            st.markdown('### 同業比較')
            same_category = stock_info[stock_info['category'] == category]
            same_category = same_category[same_category['stock_id'].isin(active_stocks)]

            if len(same_category) > 1:
                comparison_data = []
                for _, row in same_category.head(10).iterrows():
                    comp_stock = row['stock_id']
                    comp_name = row['name']

                    comp_price = '-'
                    comp_pe = '-'
                    comp_pb = '-'
                    comp_yield = '-'

                    if comp_stock in data['close'].columns:
                        comp_close = data['close'][comp_stock].dropna()
                        if len(comp_close) > 0:
                            comp_price = f'{comp_close.iloc[-1]:.2f}'

                    if comp_stock in data['pe_ratio'].columns:
                        pe = data['pe_ratio'][comp_stock].dropna()
                        if len(pe) > 0:
                            comp_pe = f'{pe.iloc[-1]:.2f}'

                    if comp_stock in data['pb_ratio'].columns:
                        pb = data['pb_ratio'][comp_stock].dropna()
                        if len(pb) > 0:
                            comp_pb = f'{pb.iloc[-1]:.2f}'

                    if comp_stock in data['dividend_yield'].columns:
                        dy = data['dividend_yield'][comp_stock].dropna()
                        if len(dy) > 0:
                            comp_yield = f'{dy.iloc[-1]:.2f}%'

                    highlight = '👉 ' if comp_stock == selected_stock else ''
                    comparison_data.append({
                        '股票': f'{highlight}{comp_stock} {comp_name}',
                        '股價': comp_price,
                        'PE': comp_pe,
                        'PB': comp_pb,
                        '殖利率': comp_yield,
                    })

                comp_df = pd.DataFrame(comparison_data)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                # 相對強弱
                st.markdown('#### 股價相對強弱 (近一年)')
                fig = go.Figure()
                for _, row in same_category.head(5).iterrows():
                    comp_stock = row['stock_id']
                    if comp_stock in data['close'].columns:
                        comp_close = data['close'][comp_stock].dropna().tail(252)
                        if len(comp_close) > 0:
                            normalized = comp_close / comp_close.iloc[0] * 100
                            line_width = 3 if comp_stock == selected_stock else 1
                            fig.add_trace(go.Scatter(x=normalized.index, y=normalized,
                                                    name=f'{comp_stock}', line=dict(width=line_width)))
                fig.update_layout(title='股價相對強弱 (基期=100)', **DEFAULT_PLOTLY_LAYOUT,height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info('找不到同產業股票進行比較')

    # ==================== Tab 6: 健診 ====================
    with tab_health:
        st.markdown('### 📋 綜合健診報告')

        # 收集各項指標進行評分
        scores = {}
        details = {}

        # ===== 1. 獲利能力評分 (25分) =====
        profit_score = 0
        profit_details = []

        if FINLAB_AVAILABLE:
            try:
                roe_data = load_finlab_data('fundamental_features:ROE稅後')
                roa_data = load_finlab_data('fundamental_features:ROA稅後息前')
                gm_data = load_finlab_data('fundamental_features:營業毛利率')
                om_data = load_finlab_data('fundamental_features:營業利益率')

                # ROE 評分 (0-8分)
                if roe_data is not None and selected_stock in roe_data.columns:
                    roe_val = roe_data[selected_stock].dropna()
                    if len(roe_val) > 0:
                        roe = roe_val.iloc[-1]
                        if roe > 20:
                            profit_score += 8
                            profit_details.append(f'✅ ROE {roe:.1f}% (優秀)')
                        elif roe > 15:
                            profit_score += 6
                            profit_details.append(f'✅ ROE {roe:.1f}% (良好)')
                        elif roe > 10:
                            profit_score += 4
                            profit_details.append(f'⚠️ ROE {roe:.1f}% (普通)')
                        elif roe > 5:
                            profit_score += 2
                            profit_details.append(f'⚠️ ROE {roe:.1f}% (偏低)')
                        else:
                            profit_details.append(f'❌ ROE {roe:.1f}% (不佳)')

                # ROA 評分 (0-5分)
                if roa_data is not None and selected_stock in roa_data.columns:
                    roa_val = roa_data[selected_stock].dropna()
                    if len(roa_val) > 0:
                        roa = roa_val.iloc[-1]
                        if roa > 10:
                            profit_score += 5
                            profit_details.append(f'✅ ROA {roa:.1f}% (優秀)')
                        elif roa > 5:
                            profit_score += 3
                            profit_details.append(f'✅ ROA {roa:.1f}% (良好)')
                        else:
                            profit_score += 1
                            profit_details.append(f'⚠️ ROA {roa:.1f}% (普通)')

                # 毛利率評分 (0-6分)
                if gm_data is not None and selected_stock in gm_data.columns:
                    gm_val = gm_data[selected_stock].dropna()
                    if len(gm_val) > 0:
                        gm = gm_val.iloc[-1]
                        if gm > 40:
                            profit_score += 6
                            profit_details.append(f'✅ 毛利率 {gm:.1f}% (高)')
                        elif gm > 25:
                            profit_score += 4
                            profit_details.append(f'✅ 毛利率 {gm:.1f}% (中等)')
                        elif gm > 15:
                            profit_score += 2
                            profit_details.append(f'⚠️ 毛利率 {gm:.1f}% (偏低)')
                        else:
                            profit_details.append(f'❌ 毛利率 {gm:.1f}% (低)')

                # 營業利益率評分 (0-6分)
                if om_data is not None and selected_stock in om_data.columns:
                    om_val = om_data[selected_stock].dropna()
                    if len(om_val) > 0:
                        om = om_val.iloc[-1]
                        if om > 20:
                            profit_score += 6
                            profit_details.append(f'✅ 營業利益率 {om:.1f}% (高)')
                        elif om > 10:
                            profit_score += 4
                            profit_details.append(f'✅ 營業利益率 {om:.1f}% (中等)')
                        elif om > 5:
                            profit_score += 2
                            profit_details.append(f'⚠️ 營業利益率 {om:.1f}% (偏低)')
                        else:
                            profit_details.append(f'❌ 營業利益率 {om:.1f}% (低)')

            except Exception:
                pass

        scores['獲利能力'] = min(profit_score, 25)
        details['獲利能力'] = profit_details

        # ===== 2. 財務安全評分 (25分) =====
        safety_score = 0
        safety_details = []

        if FINLAB_AVAILABLE:
            try:
                cr_data = load_finlab_data('fundamental_features:流動比率')
                dr_data = load_finlab_data('fundamental_features:負債比率')
                cfr_data = load_finlab_data('fundamental_features:現金流量比率')

                # 流動比率 (0-10分)
                if cr_data is not None and selected_stock in cr_data.columns:
                    cr_val = cr_data[selected_stock].dropna()
                    if len(cr_val) > 0:
                        cr = cr_val.iloc[-1]
                        if cr > 200:
                            safety_score += 10
                            safety_details.append(f'✅ 流動比率 {cr:.0f}% (優秀)')
                        elif cr > 150:
                            safety_score += 7
                            safety_details.append(f'✅ 流動比率 {cr:.0f}% (良好)')
                        elif cr > 100:
                            safety_score += 4
                            safety_details.append(f'⚠️ 流動比率 {cr:.0f}% (尚可)')
                        else:
                            safety_details.append(f'❌ 流動比率 {cr:.0f}% (偏低)')

                # 負債比率 (0-10分)
                if dr_data is not None and selected_stock in dr_data.columns:
                    dr_val = dr_data[selected_stock].dropna()
                    if len(dr_val) > 0:
                        dr = dr_val.iloc[-1]
                        if dr < 30:
                            safety_score += 10
                            safety_details.append(f'✅ 負債比率 {dr:.0f}% (低)')
                        elif dr < 50:
                            safety_score += 7
                            safety_details.append(f'✅ 負債比率 {dr:.0f}% (適中)')
                        elif dr < 70:
                            safety_score += 3
                            safety_details.append(f'⚠️ 負債比率 {dr:.0f}% (偏高)')
                        else:
                            safety_details.append(f'❌ 負債比率 {dr:.0f}% (高)')

                # 現金流量比率 (0-5分)
                if cfr_data is not None and selected_stock in cfr_data.columns:
                    cfr_val = cfr_data[selected_stock].dropna()
                    if len(cfr_val) > 0:
                        cfr = cfr_val.iloc[-1]
                        if cfr > 100:
                            safety_score += 5
                            safety_details.append(f'✅ 現金流量比率 {cfr:.0f}% (充裕)')
                        elif cfr > 50:
                            safety_score += 3
                            safety_details.append(f'✅ 現金流量比率 {cfr:.0f}% (適中)')
                        else:
                            safety_score += 1
                            safety_details.append(f'⚠️ 現金流量比率 {cfr:.0f}% (偏低)')

            except Exception:
                pass

        scores['財務安全'] = min(safety_score, 25)
        details['財務安全'] = safety_details

        # ===== 3. 成長動能評分 (25分) =====
        growth_score = 0
        growth_details = []

        # 營收成長
        if selected_stock in data['revenue_yoy'].columns:
            rev_yoy = data['revenue_yoy'][selected_stock].dropna()
            if len(rev_yoy) > 0:
                yoy = rev_yoy.iloc[-1]
                if yoy > 20:
                    growth_score += 8
                    growth_details.append(f'✅ 營收年增 {yoy:.1f}% (高成長)')
                elif yoy > 10:
                    growth_score += 6
                    growth_details.append(f'✅ 營收年增 {yoy:.1f}% (穩定成長)')
                elif yoy > 0:
                    growth_score += 3
                    growth_details.append(f'⚠️ 營收年增 {yoy:.1f}% (微幅成長)')
                else:
                    growth_details.append(f'❌ 營收年增 {yoy:.1f}% (衰退)')

        # EPS 成長
        if FINLAB_AVAILABLE:
            try:
                eps_data = load_finlab_data('financial_statement:每股盈餘')
                if eps_data is not None and selected_stock in eps_data.columns:
                    eps = eps_data[selected_stock].dropna()
                    if len(eps) >= 5:
                        eps_now = eps.iloc[-1]
                        eps_prev = eps.iloc[-5]  # 去年同期
                        if eps_prev != 0:
                            eps_growth = (eps_now / eps_prev - 1) * 100
                            if eps_growth > 20:
                                growth_score += 8
                                growth_details.append(f'✅ EPS年增 {eps_growth:.1f}% (高成長)')
                            elif eps_growth > 10:
                                growth_score += 6
                                growth_details.append(f'✅ EPS年增 {eps_growth:.1f}% (穩定成長)')
                            elif eps_growth > 0:
                                growth_score += 3
                                growth_details.append(f'⚠️ EPS年增 {eps_growth:.1f}% (微幅成長)')
                            else:
                                growth_details.append(f'❌ EPS年增 {eps_growth:.1f}% (衰退)')
            except Exception:
                pass

        # 股價動能
        if len(close_period) >= 60:
            price_change_1m = (close_period.iloc[-1] / close_period.iloc[-22] - 1) * 100
            price_change_3m = (close_period.iloc[-1] / close_period.iloc[-66] - 1) * 100 if len(close_period) >= 66 else 0

            if price_change_1m > 10:
                growth_score += 5
                growth_details.append(f'✅ 月漲幅 {price_change_1m:.1f}% (強勢)')
            elif price_change_1m > 0:
                growth_score += 3
                growth_details.append(f'✅ 月漲幅 {price_change_1m:.1f}% (上漲)')
            elif price_change_1m > -10:
                growth_score += 1
                growth_details.append(f'⚠️ 月跌幅 {price_change_1m:.1f}%')
            else:
                growth_details.append(f'❌ 月跌幅 {price_change_1m:.1f}% (弱勢)')

            # 均線位置
            ma60 = close_period.rolling(60).mean().iloc[-1]
            if close_period.iloc[-1] > ma60:
                growth_score += 4
                growth_details.append(f'✅ 股價在60日均線之上')
            else:
                growth_details.append(f'⚠️ 股價在60日均線之下')

        scores['成長動能'] = min(growth_score, 25)
        details['成長動能'] = growth_details

        # ===== 4. 估值合理性評分 (25分) =====
        valuation_score = 0
        valuation_details = []

        # PE 評分
        if selected_stock in data['pe_ratio'].columns:
            pe = data['pe_ratio'][selected_stock].dropna()
            if len(pe) > 0:
                pe_val = pe.iloc[-1]
                if pe_val > 0:  # 排除負值
                    if pe_val < 10:
                        valuation_score += 10
                        valuation_details.append(f'✅ 本益比 {pe_val:.1f} (便宜)')
                    elif pe_val < 15:
                        valuation_score += 8
                        valuation_details.append(f'✅ 本益比 {pe_val:.1f} (合理)')
                    elif pe_val < 20:
                        valuation_score += 5
                        valuation_details.append(f'⚠️ 本益比 {pe_val:.1f} (略高)')
                    elif pe_val < 30:
                        valuation_score += 2
                        valuation_details.append(f'⚠️ 本益比 {pe_val:.1f} (偏高)')
                    else:
                        valuation_details.append(f'❌ 本益比 {pe_val:.1f} (過高)')

        # PB 評分
        if selected_stock in data['pb_ratio'].columns:
            pb = data['pb_ratio'][selected_stock].dropna()
            if len(pb) > 0:
                pb_val = pb.iloc[-1]
                if pb_val < 1:
                    valuation_score += 8
                    valuation_details.append(f'✅ 股價淨值比 {pb_val:.2f} (便宜)')
                elif pb_val < 2:
                    valuation_score += 6
                    valuation_details.append(f'✅ 股價淨值比 {pb_val:.2f} (合理)')
                elif pb_val < 3:
                    valuation_score += 3
                    valuation_details.append(f'⚠️ 股價淨值比 {pb_val:.2f} (略高)')
                else:
                    valuation_details.append(f'❌ 股價淨值比 {pb_val:.2f} (偏高)')

        # 殖利率評分
        if selected_stock in data['dividend_yield'].columns:
            dy = data['dividend_yield'][selected_stock].dropna()
            if len(dy) > 0:
                dy_val = dy.iloc[-1]
                if dy_val > 5:
                    valuation_score += 7
                    valuation_details.append(f'✅ 殖利率 {dy_val:.2f}% (高)')
                elif dy_val > 3:
                    valuation_score += 5
                    valuation_details.append(f'✅ 殖利率 {dy_val:.2f}% (中等)')
                elif dy_val > 1:
                    valuation_score += 2
                    valuation_details.append(f'⚠️ 殖利率 {dy_val:.2f}% (偏低)')
                else:
                    valuation_details.append(f'❌ 殖利率 {dy_val:.2f}% (低)')

        scores['估值合理'] = min(valuation_score, 25)
        details['估值合理'] = valuation_details

        # ==================== 顯示健診結果 ====================
        total_score = sum(scores.values())

        # 總分顯示
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # 評級
            if total_score >= 80:
                grade = 'A'
                grade_color = '#4CAF50'
                grade_text = '優質股票'
            elif total_score >= 65:
                grade = 'B'
                grade_color = '#8BC34A'
                grade_text = '良好股票'
            elif total_score >= 50:
                grade = 'C'
                grade_color = '#FFC107'
                grade_text = '普通股票'
            elif total_score >= 35:
                grade = 'D'
                grade_color = '#FF9800'
                grade_text = '需注意'
            else:
                grade = 'E'
                grade_color = '#f44336'
                grade_text = '風險較高'

            st.markdown(f"""
            <div style='text-align: center; padding: 20px;'>
                <h1 style='font-size: 4em; color: {grade_color}; margin: 0;'>{grade}</h1>
                <h2 style='color: {grade_color}; margin: 5px 0;'>{total_score} 分</h2>
                <p style='font-size: 1.2em;'>{grade_text}</p>
            </div>
            """, unsafe_allow_html=True)

        # 各維度評分
        st.markdown('---')
        st.markdown('#### 📊 各維度評分')

        score_cols = st.columns(4)
        categories = ['獲利能力', '財務安全', '成長動能', '估值合理']
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0']

        for i, (cat, color) in enumerate(zip(categories, colors)):
            with score_cols[i]:
                score = scores.get(cat, 0)
                pct = score / 25 * 100
                st.markdown(f"""
                <div style='text-align: center;'>
                    <h4>{cat}</h4>
                    <div style='font-size: 2em; color: {color}; font-weight: bold;'>{score}/25</div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(pct / 100)

        # 雷達圖
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[scores.get(cat, 0) for cat in categories] + [scores.get(categories[0], 0)],
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor='rgba(33, 150, 243, 0.3)',
            line=dict(color='#2196F3'),
            name=f'{selected_stock} {name}'
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 25])
            ),
            showlegend=False,
            height=350,
            title='健診雷達圖'
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # 詳細評分
        st.markdown('---')
        st.markdown('#### 📝 詳細評分項目')

        detail_cols = st.columns(2)
        for i, cat in enumerate(categories):
            with detail_cols[i % 2]:
                with st.expander(f'{cat} ({scores.get(cat, 0)}/25分)', expanded=True):
                    for item in details.get(cat, ['無資料']):
                        st.markdown(item)

        # 投資建議
        st.markdown('---')
        st.markdown('#### 💡 投資建議')

        if total_score >= 80:
            st.success(f"""
            **{selected_stock} {name}** 整體評分優秀，各項指標表現良好。
            - 獲利能力強、財務結構穩健
            - 適合長期投資觀察
            - 建議搭配技術面選擇進場時機
            """)
        elif total_score >= 65:
            st.info(f"""
            **{selected_stock} {name}** 整體表現良好，部分指標仍有進步空間。
            - 基本面表現穩定
            - 可列入觀察名單
            - 注意較弱的評分項目
            """)
        elif total_score >= 50:
            st.warning(f"""
            **{selected_stock} {name}** 表現普通，需要進一步觀察。
            - 部分指標表現不佳
            - 建議深入研究弱項原因
            - 投資前需謹慎評估
            """)
        else:
            st.error(f"""
            **{selected_stock} {name}** 評分偏低，存在較多風險因子。
            - 多項指標表現不佳
            - 短期不建議介入
            - 如要投資需做好風險控管
            """)

else:
    st.info('請在側邊欄選擇要分析的股票')

# ==================== 頁尾說明 ====================
with st.expander('📖 功能說明'):
    st.markdown('''
    ### 個股分析功能

    | 功能 | 說明 |
    |------|------|
    | 📈 走勢圖 | K線走勢、技術分析(RSI/MACD/KD)、成交彙整 |
    | 💰 籌碼分析 | 法人買賣、資券變化、外資持股、大戶籌碼(集保餘額) |
    | 📊 估價分析 | 本益比河流圖、股價淨值比河流圖、多空分析 |
    | 📋 財務分析 | 營收表、每股盈餘、獲利能力、財務健全、損益表、資產負債表、現金流量表 |
    | 🏢 基本資料 | 公司資訊、股利政策、同業比較 |
    | 🩺 健診 | 綜合評分(獲利能力/財務安全/成長動能/估值合理)、投資建議 |

    **評分說明**:
    - A級 (80分以上): 優質股票
    - B級 (65-79分): 良好股票
    - C級 (50-64分): 普通股票
    - D級 (35-49分): 需注意
    - E級 (35分以下): 風險較高

    **資料來源**: FinLab API、本地數據快取
    ''')
