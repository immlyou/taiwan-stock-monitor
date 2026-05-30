"""
個股分析頁面
功能：走勢圖、技術分析、籌碼、法人買賣、資券變化、估價(河流圖)、財務、基本、同業比較
"""
import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots


from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks, reset_all_caches
from core.indicators import rsi, macd, resample_ohlcv, get_timeframe_label, get_ma_periods_for_timeframe
from app.components.theme import (
    DEFAULT_PLOTLY_LAYOUT, COLORS,
    create_page_title, create_section_header, render_kpi_row,
    responsive_columns, create_kpi_card, format_number,
)
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_global_ticker_bar
from app.components.session_manager import (
    init_session_state, get_state, set_state, StateKeys,
    get_stock_to_analyze
)
from app.components.error_handler import show_error
from core.ai_models import StockChatAssistant

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

render_sidebar_mini(current_page='stock')

# ==================== 資料載入 ====================
@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner="載入股票數據中...")
def load_data():
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
    data = load_data()
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

# 全域行情列 + 命令列搜尋（個股頁傳入當前股票代號）
render_global_ticker_bar(active_stock=selected_stock)

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
    latest_price = close_period.iloc[-1]
    prev_price = close_period.iloc[-2] if len(close_period) > 1 else latest_price
    change = latest_price - prev_price
    change_pct = (change / prev_price) * 100

    title_col, action_col = st.columns([4, 1])
    with title_col:
        st.markdown(
            create_page_title(
                f'{selected_stock} {name}',
                subtitle=f'{category} | {market}',
                icon='📈',
            ),
            unsafe_allow_html=True,
        )
    with action_col:
        watchlists = load_watchlists()
        if not watchlists:
            watchlists['預設清單'] = {'created_at': datetime.now().isoformat(), 'stocks': [], 'notes': {}}
        if st.button('⭐ 加入自選', use_container_width=True, type='secondary'):
            if '預設清單' not in watchlists:
                watchlists['預設清單'] = {'created_at': datetime.now().isoformat(), 'stocks': [], 'notes': {}}
            if selected_stock not in watchlists['預設清單']['stocks']:
                watchlists['預設清單']['stocks'].append(selected_stock)
                save_watchlists(watchlists)
                st.success('已加入自選股')
            else:
                st.info('已在自選股中')

    # 頂部 KPI 列（紅漲綠跌 + ▲▼ + 正負號）
    _price_delta_color = 'up' if change > 0 else 'down' if change < 0 else 'flat'
    _pe_txt = '-'
    if selected_stock in data['pe_ratio'].columns:
        _pe = data['pe_ratio'][selected_stock].dropna()
        _pe_txt = format_number(_pe.iloc[-1]) if len(_pe) > 0 else '-'
    _pb_txt = '-'
    if selected_stock in data['pb_ratio'].columns:
        _pb = data['pb_ratio'][selected_stock].dropna()
        _pb_txt = format_number(_pb.iloc[-1]) if len(_pb) > 0 else '-'
    _dy_txt = '-'
    if selected_stock in data['dividend_yield'].columns:
        _dy = data['dividend_yield'][selected_stock].dropna()
        _dy_txt = format_number(_dy.iloc[-1], kind='pct') if len(_dy) > 0 else '-'

    render_kpi_row([
        {
            'label': '股價',
            'value': format_number(latest_price),
            'delta': f'{format_number(change, signed=True)} ({format_number(change_pct, kind="pct", signed=True)})',
            'delta_color': _price_delta_color,
            'sparkline': list(close_period.tail(30).values),
        },
        {'label': '本益比', 'value': _pe_txt},
        {'label': '股價淨值比', 'value': _pb_txt},
        {'label': '殖利率', 'value': _dy_txt},
    ])

    # ==================== 多空診斷卡 ====================
    st.markdown(create_section_header('多空診斷', icon='🧭'), unsafe_allow_html=True)

    def _diag_card(label, verdict, color_key):
        """以 KPI 卡呈現單一維度多空評級（紅漲綠跌語意，中性灰）。"""
        arrow = '▲' if color_key == 'up' else '▼' if color_key == 'down' else '—'
        delta_color = color_key if color_key in ('up', 'down') else 'flat'
        return {'label': label, 'value': verdict, 'delta': arrow, 'delta_color': delta_color}

    _diag_items = []

    # 技術：RSI + MACD 綜合
    try:
        _rsi_v = rsi(close_period, 14).iloc[-1]
        _macd_l, _sig_l, _ = macd(close_period)
        _tech_bull = 0
        if not pd.isna(_rsi_v):
            _tech_bull += 1 if _rsi_v < 70 and _rsi_v > 50 else (-1 if _rsi_v > 70 or _rsi_v < 30 else 0)
        if not pd.isna(_macd_l.iloc[-1]):
            _tech_bull += 1 if _macd_l.iloc[-1] > _sig_l.iloc[-1] else -1
        _tech_v = '偏多' if _tech_bull > 0 else '偏空' if _tech_bull < 0 else '中性'
        _diag_items.append(_diag_card('技術', _tech_v, 'up' if _tech_bull > 0 else 'down' if _tech_bull < 0 else 'flat'))
    except Exception:
        _diag_items.append(_diag_card('技術', 'N/A', 'flat'))

    # 趨勢：均線排列
    try:
        _ma5 = close_period.rolling(5).mean().iloc[-1]
        _ma20 = close_period.rolling(20).mean().iloc[-1]
        _ma60 = close_period.rolling(60).mean().iloc[-1] if len(close_period) >= 60 else _ma20
        if latest_price > _ma5 > _ma20 > _ma60:
            _diag_items.append(_diag_card('趨勢', '多頭排列', 'up'))
        elif latest_price < _ma5 < _ma20 < _ma60:
            _diag_items.append(_diag_card('趨勢', '空頭排列', 'down'))
        else:
            _diag_items.append(_diag_card('趨勢', '盤整', 'flat'))
    except Exception:
        _diag_items.append(_diag_card('趨勢', 'N/A', 'flat'))

    # 量能：相對20日均量
    try:
        if volume_period is not None and len(volume_period) >= 20:
            _vol_ma = volume_period.rolling(20).mean().iloc[-1]
            _vol_ratio = volume_period.iloc[-1] / _vol_ma if _vol_ma > 0 else 1
            if _vol_ratio > 1.5:
                _diag_items.append(_diag_card('量能', '放量', 'up'))
            elif _vol_ratio < 0.5:
                _diag_items.append(_diag_card('量能', '縮量', 'down'))
            else:
                _diag_items.append(_diag_card('量能', '正常', 'flat'))
        else:
            _diag_items.append(_diag_card('量能', 'N/A', 'flat'))
    except Exception:
        _diag_items.append(_diag_card('量能', 'N/A', 'flat'))

    # 財務：營收年增率
    try:
        if selected_stock in data['revenue_yoy'].columns:
            _yoy = data['revenue_yoy'][selected_stock].dropna()
            if len(_yoy) > 0:
                _yoy_v = _yoy.iloc[-1]
                if _yoy_v > 5:
                    _diag_items.append(_diag_card('財務', '成長', 'up'))
                elif _yoy_v < 0:
                    _diag_items.append(_diag_card('財務', '衰退', 'down'))
                else:
                    _diag_items.append(_diag_card('財務', '持平', 'flat'))
            else:
                _diag_items.append(_diag_card('財務', 'N/A', 'flat'))
        else:
            _diag_items.append(_diag_card('財務', 'N/A', 'flat'))
    except Exception:
        _diag_items.append(_diag_card('財務', 'N/A', 'flat'))

    # 法人：外資近5日買賣超（FinLab）
    _inst_done = False
    if FINLAB_AVAILABLE:
        try:
            _foreign = load_finlab_data('institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)')
            if _foreign is not None and selected_stock in _foreign.columns:
                _f5 = _foreign[selected_stock].dropna().tail(5).sum()
                if _f5 > 0:
                    _diag_items.append(_diag_card('法人', '買超', 'up'))
                elif _f5 < 0:
                    _diag_items.append(_diag_card('法人', '賣超', 'down'))
                else:
                    _diag_items.append(_diag_card('法人', '中性', 'flat'))
                _inst_done = True
        except Exception:
            pass
    if not _inst_done:
        _diag_items.append(_diag_card('法人', 'N/A', 'flat'))

    # 估值：本益比水位
    try:
        if selected_stock in data['pe_ratio'].columns:
            _pe_s = data['pe_ratio'][selected_stock].dropna()
            if len(_pe_s) > 0 and _pe_s.iloc[-1] > 0:
                _pe_now = _pe_s.iloc[-1]
                if _pe_now < 15:
                    _diag_items.append(_diag_card('估值', '便宜', 'up'))
                elif _pe_now > 25:
                    _diag_items.append(_diag_card('估值', '偏貴', 'down'))
                else:
                    _diag_items.append(_diag_card('估值', '合理', 'flat'))
            else:
                _diag_items.append(_diag_card('估值', 'N/A', 'flat'))
        else:
            _diag_items.append(_diag_card('估值', 'N/A', 'flat'))
    except Exception:
        _diag_items.append(_diag_card('估值', 'N/A', 'flat'))

    render_kpi_row(_diag_items, cols=len(_diag_items))
    st.caption('診斷為頁內既有指標的簡易彙整，標示 N/A 者為資料不足或中性占位')

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

    # ==================== 主要 Tabs（兩層結構：頂層 tabs + 層內 radio）====================
    tab_chart, tab_chip, tab_valuation, tab_finance, tab_basic, tab_health = st.tabs([
        '📈 行情', '💰 籌碼', '📊 估價', '📋 財報', '🏢 基本', '🩺 健診'
    ])

    # ==================== Tab 1: 行情（K線 / 技術 / 成交，radio 切換）====================
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

        # 維度切換改用 radio（取代再開一層 tabs）
        _chart_view = st.radio(
            '檢視',
            options=['K線走勢', '技術分析', '成交彙整'],
            horizontal=True,
            label_visibility='collapsed',
            key='chart_view_radio',
        )

        if _chart_view == 'K線走勢':
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

        elif _chart_view == '技術分析':
            st.markdown(create_section_header(f'技術指標分析 ({tf_label})', icon='📐'), unsafe_allow_html=True)

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

        elif _chart_view == '成交彙整':
            st.markdown(create_section_header(f'成交彙整 ({tf_label})', icon='📊'), unsafe_allow_html=True)
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

    # ==================== Tab 2: 籌碼分析（radio 切換維度）====================
    with tab_chip:
        _chip_view = st.radio(
            '籌碼維度',
            options=['法人買賣', '資券變化', '外資持股', '大戶籌碼'],
            horizontal=True,
            label_visibility='collapsed',
            key='chip_view_radio',
        )

        if _chip_view == '法人買賣':
            st.markdown(create_section_header('三大法人買賣超', icon='🏦'), unsafe_allow_html=True)
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

        elif _chip_view == '資券變化':
            st.markdown(create_section_header('融資融券變化', icon='💳'), unsafe_allow_html=True)
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

        elif _chip_view == '外資持股':
            st.markdown(create_section_header('外資持股比率', icon='🌐'), unsafe_allow_html=True)
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

        elif _chip_view == '大戶籌碼':
            st.markdown(create_section_header('大戶籌碼集中度', icon='🐳'), unsafe_allow_html=True)
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
                            st.markdown(create_section_header('股東分級分布', icon='👥'), unsafe_allow_html=True)

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
                            st.markdown(create_section_header('籌碼集中度評估', icon='🎯'), unsafe_allow_html=True)
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

    # ==================== Tab 3: 估價分析（radio 切換維度）====================
    with tab_valuation:
        _val_view = st.radio(
            '估價維度',
            options=['本益比河流圖', '股價淨值比河流圖', '多空分析'],
            horizontal=True,
            label_visibility='collapsed',
            key='valuation_view_radio',
        )

        if _val_view == '本益比河流圖':
            st.markdown(create_section_header('本益比河流圖', icon='🌊'), unsafe_allow_html=True)
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

        elif _val_view == '股價淨值比河流圖':
            st.markdown(create_section_header('股價淨值比河流圖', icon='🌊'), unsafe_allow_html=True)
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

        elif _val_view == '多空分析':
            st.markdown(create_section_header('多空分析', icon='⚖️'), unsafe_allow_html=True)
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

    # ==================== Tab 4: 財報（精簡摘要 + 前往財報分析）====================
    with tab_finance:
        st.markdown(create_section_header('財報摘要', icon='📋'), unsafe_allow_html=True)
        st.caption('完整財報（損益表 / 資產負債表 / 現金流量 / 獲利能力）請前往「財報分析」頁，避免重複維護')

        # 精簡摘要：最新月營收、年增率、近四季 EPS、累計營收
        _fin_items = []
        if selected_stock in data['monthly_revenue'].columns:
            _rev = data['monthly_revenue'][selected_stock].dropna().tail(24)
            if len(_rev) > 0:
                _fin_items.append({'label': '最新月營收', 'value': format_number(_rev.iloc[-1], kind='amount')})
                _fin_items.append({'label': '近12月累計', 'value': format_number(_rev.tail(12).sum(), kind='amount')})
        if selected_stock in data['revenue_yoy'].columns:
            _ry = data['revenue_yoy'][selected_stock].dropna()
            if len(_ry) > 0:
                _yoy = _ry.iloc[-1]
                _fin_items.append({
                    'label': '營收年增率',
                    'value': format_number(_yoy, kind='pct', signed=True),
                    'delta': '成長' if _yoy > 0 else '衰退' if _yoy < 0 else '持平',
                    'delta_color': 'up' if _yoy > 0 else 'down' if _yoy < 0 else 'flat',
                })

        _eps_ttm = None
        if FINLAB_AVAILABLE:
            try:
                _eps_data = load_finlab_data('financial_statement:每股盈餘')
                if _eps_data is not None and selected_stock in _eps_data.columns:
                    _eps = _eps_data[selected_stock].dropna()
                    if len(_eps) >= 4:
                        _eps_ttm = _eps.tail(4).sum()
                        _fin_items.append({'label': '近四季 EPS', 'value': format_number(_eps_ttm)})
            except Exception:
                pass

        if _fin_items:
            render_kpi_row(_fin_items, cols=min(len(_fin_items), 4))
        else:
            st.info('無財報摘要資料')

        st.markdown('')
        if st.button('📊 前往財報分析（完整財報）', use_container_width=True, type='primary', key='goto_finance_page'):
            st.switch_page('pages/14_財報分析.py')

    # ==================== Tab 5: 基本資料（radio 切換維度）====================
    with tab_basic:
        _basic_view = st.radio(
            '基本維度',
            options=['公司資訊', '股利政策', '同業比較'],
            horizontal=True,
            label_visibility='collapsed',
            key='basic_view_radio',
        )

        if _basic_view == '公司資訊':
            st.markdown(create_section_header('公司基本資訊', icon='🏢'), unsafe_allow_html=True)
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

        elif _basic_view == '股利政策':
            st.markdown(create_section_header('股利政策', icon='💵'), unsafe_allow_html=True)
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

        elif _basic_view == '同業比較':
            st.markdown(create_section_header('同業比較', icon='⚔️'), unsafe_allow_html=True)
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
        st.markdown(create_section_header('綜合健診報告', icon='🩺'), unsafe_allow_html=True)

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
                growth_details.append('✅ 股價在60日均線之上')
            else:
                growth_details.append('⚠️ 股價在60日均線之下')

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
            # 評級（使用主題狀態色 token，深色底）
            if total_score >= 80:
                grade = 'A'
                grade_color = COLORS['success']
                grade_text = '優質股票'
            elif total_score >= 65:
                grade = 'B'
                grade_color = COLORS['success']
                grade_text = '良好股票'
            elif total_score >= 50:
                grade = 'C'
                grade_color = COLORS['warning']
                grade_text = '普通股票'
            elif total_score >= 35:
                grade = 'D'
                grade_color = COLORS['warning']
                grade_text = '需注意'
            else:
                grade = 'E'
                grade_color = COLORS['danger']
                grade_text = '風險較高'

            st.markdown(f"""
            <div style='text-align:center;padding:20px;background:{COLORS['secondary']};
                        border:1px solid {COLORS['border']};border-radius:12px'>
                <h1 style='font-size:4em;color:{grade_color};margin:0'>{grade}</h1>
                <h2 style='color:{grade_color};margin:5px 0'>{total_score} 分</h2>
                <p style='font-size:1.2em;color:{COLORS['text_secondary']}'>{grade_text}</p>
            </div>
            """, unsafe_allow_html=True)

        # 各維度評分
        st.markdown(create_section_header('各維度評分', icon='📊'), unsafe_allow_html=True)

        score_cols = responsive_columns(4)
        categories = ['獲利能力', '財務安全', '成長動能', '估值合理']

        for i, cat in enumerate(categories):
            with score_cols[i]:
                score = scores.get(cat, 0)
                pct = score / 25 * 100
                st.markdown(create_kpi_card(cat, f'{score}/25'), unsafe_allow_html=True)
                st.progress(pct / 100)

        # 雷達圖
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[scores.get(cat, 0) for cat in categories] + [scores.get(categories[0], 0)],
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor='rgba(59, 130, 246, 0.3)',
            line=dict(color=COLORS['accent']),
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
        st.markdown(create_section_header('詳細評分項目', icon='📝'), unsafe_allow_html=True)

        detail_cols = st.columns(2)
        for i, cat in enumerate(categories):
            with detail_cols[i % 2]:
                with st.expander(f'{cat} ({scores.get(cat, 0)}/25分)', expanded=True):
                    for item in details.get(cat, ['無資料']):
                        st.markdown(item)

        # 投資建議
        st.markdown(create_section_header('投資建議', icon='💡'), unsafe_allow_html=True)

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

    # ==================== AI 對話 ====================
    st.markdown(create_section_header('AI 個股問答', icon='🤖'), unsafe_allow_html=True)
    st.caption(f'詢問任何關於 {stock_id} 的問題，AI 將根據當前數據回答')

    # 初始化對話歷史
    chat_key = f'stock_chat_{stock_id}'
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    # 構建數據上下文
    _chat_context_parts = []
    try:
        _close = data['close']
        if _close is not None and stock_id in _close.columns:
            _prices = _close[stock_id].dropna()
            if len(_prices) > 0:
                _latest = float(_prices.iloc[-1])
                _prev = float(_prices.iloc[-2]) if len(_prices) > 1 else _latest
                _chg = (_latest / _prev - 1) * 100
                _high_52w = float(_prices.iloc[-252:].max()) if len(_prices) >= 252 else float(_prices.max())
                _low_52w = float(_prices.iloc[-252:].min()) if len(_prices) >= 252 else float(_prices.min())
                _chat_context_parts.append(f"收盤價: {_latest:.2f} (漲跌: {_chg:+.2f}%)")
                _chat_context_parts.append(f"52週高低: {_high_52w:.2f} / {_low_52w:.2f}")
    except Exception:
        pass
    try:
        _pe = data.get('pe_ratio')
        if _pe is not None and stock_id in _pe.columns:
            _pe_val = _pe[stock_id].dropna().iloc[-1]
            _chat_context_parts.append(f"本益比: {_pe_val:.1f}")
    except Exception:
        pass
    try:
        _pb = data.get('pb_ratio')
        if _pb is not None and stock_id in _pb.columns:
            _pb_val = _pb[stock_id].dropna().iloc[-1]
            _chat_context_parts.append(f"股價淨值比: {_pb_val:.2f}")
    except Exception:
        pass
    try:
        _dy = data.get('dividend_yield')
        if _dy is not None and stock_id in _dy.columns:
            _dy_val = _dy[stock_id].dropna().iloc[-1]
            _chat_context_parts.append(f"殖利率: {_dy_val:.2f}%")
    except Exception:
        pass
    try:
        _rev = data.get('revenue_yoy')
        if _rev is not None and stock_id in _rev.columns:
            _rev_val = _rev[stock_id].dropna().iloc[-1]
            _chat_context_parts.append(f"營收年增率: {_rev_val:.1f}%")
    except Exception:
        pass
    _data_context = "\n".join(_chat_context_parts) if _chat_context_parts else "暫無數據"

    # 顯示對話歷史
    for msg in st.session_state[chat_key]:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    # 輸入框
    if user_input := st.chat_input(f'問關於 {stock_id} 的問題...'):
        # 顯示用戶訊息
        st.session_state[chat_key].append({'role': 'user', 'content': user_input})
        with st.chat_message('user'):
            st.markdown(user_input)

        # AI 回覆
        with st.chat_message('assistant'):
            with st.spinner('思考中...'):
                _name = stock_id
                try:
                    _info_row = stock_info[stock_info['stock_id'] == stock_id]
                    if len(_info_row) > 0:
                        _name = _info_row['name'].values[0]
                except Exception:
                    pass
                assistant = StockChatAssistant()
                reply = assistant.chat(
                    stock_id=stock_id,
                    name=_name,
                    data_context=_data_context,
                    question=user_input,
                    history=st.session_state[chat_key][:-1],
                )
                st.markdown(reply)
        st.session_state[chat_key].append({'role': 'assistant', 'content': reply})

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
