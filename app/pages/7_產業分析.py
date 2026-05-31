"""
產業分析頁面 - 各產業強弱勢分析
"""
import streamlit as st
import pandas as pd
import numpy as np


from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error, create_error_boundary
from app.components.page_header import render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.session_manager import get_state, set_state, StateKeys
from app.components.charts import apply_dark_theme, CHART_CONFIG
from app.components.theme import (
    COLORS,
    create_page_title,
    create_section_header,
    render_kpi_row,
    render_data_table,
    format_number,
    format_change_value,
)

st.set_page_config(page_title='產業分析', page_icon='🏭', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='industry')

# 全域行情列（sidebar 後、標題前呼叫一次）
render_global_ticker_bar()

st.markdown(create_page_title("產業分析", subtitle="各產業強弱勢與輪動分析", icon="🏭"), unsafe_allow_html=True)

# 載入數據
@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner='載入數據中...')
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'volume': loader.get('volume'),
        'stock_info': loader.get_stock_info(),
        'benchmark': loader.get_benchmark(),
    }

try:
    data = load_data()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

close = data['close']
volume = data['volume']
stock_info = data['stock_info']
benchmark = data['benchmark']

# 取得活躍股票
active_stocks = get_active_stocks()

# 計算各產業報酬
@st.cache_data(ttl=CACHE_TTL['daily'])
def calculate_industry_returns(_close, _stock_info, _active_stocks, period_days):
    """計算各產業報酬"""
    close_period = _close.tail(period_days)

    # 按產業分組
    industry_returns = {}

    for category in _stock_info['category'].unique():
        if pd.isna(category):
            continue

        # 取得該產業的活躍股票
        industry_stocks = _stock_info[_stock_info['category'] == category]['stock_id'].tolist()
        industry_stocks = [s for s in industry_stocks if s in _active_stocks and s in close_period.columns]

        if len(industry_stocks) >= 3:  # 至少 3 檔股票
            # 計算等權重報酬
            industry_close = close_period[industry_stocks]
            daily_returns = industry_close.pct_change()
            industry_avg_return = daily_returns.mean(axis=1)

            # 累積報酬
            cumulative_return = (1 + industry_avg_return).cumprod()
            total_return = cumulative_return.iloc[-1] - 1

            # 波動率
            volatility = industry_avg_return.std() * np.sqrt(252)

            industry_returns[category] = {
                'return': total_return,
                'volatility': volatility,
                'stocks_count': len(industry_stocks),
                'cumulative': cumulative_return,
            }

    return industry_returns

# ========== 期間選擇 ==========
st.markdown(create_section_header('分析期間', icon='📅'), unsafe_allow_html=True)

col1, col2 = st.columns([1, 3])

with col1:
    period = st.selectbox(
        '選擇期間',
        ['1W', '1M', '3M', '6M', '1Y'],
        index=2,
        format_func=lambda x: {
            '1W': '近 1 週',
            '1M': '近 1 月',
            '3M': '近 3 月',
            '6M': '近 6 月',
            '1Y': '近 1 年',
        }[x],
    )

period_days = {'1W': 5, '1M': 22, '3M': 66, '6M': 132, '1Y': 252}[period]

# 計算產業報酬
industry_returns = calculate_industry_returns(
    close, stock_info, active_stocks, period_days
)

if not industry_returns:
    show_empty_state('無法計算產業報酬', icon='⚠️', suggestion='請確認資料是否已正常載入')
    st.stop()

# ========== 產業排行 ==========
st.markdown(create_section_header('產業強弱排行', icon='🏆'), unsafe_allow_html=True)

# 建立排行表
ranking_data = []
for category, metrics in industry_returns.items():
    ranking_data.append({
        '產業': category,
        '報酬率': metrics['return'],
        '波動率': metrics['volatility'],
        '股票數': metrics['stocks_count'],
    })

ranking_df = pd.DataFrame(ranking_data)
ranking_df = ranking_df.sort_values('報酬率', ascending=False).reset_index(drop=True)
ranking_df.index = ranking_df.index + 1

# KPI 摘要列
_top = ranking_df.iloc[0]
_bottom = ranking_df.iloc[-1]
_avg_ret = ranking_df['報酬率'].mean()
render_kpi_row([
    {'label': '最強產業', 'value': str(_top['產業']),
     'delta': format_number(_top['報酬率'] * 100, kind='pct', signed=True),
     'delta_color': 'up' if _top['報酬率'] >= 0 else 'down'},
    {'label': '最弱產業', 'value': str(_bottom['產業']),
     'delta': format_number(_bottom['報酬率'] * 100, kind='pct', signed=True),
     'delta_color': 'up' if _bottom['報酬率'] >= 0 else 'down'},
    {'label': '產業平均報酬', 'value': format_number(_avg_ret * 100, kind='pct', signed=True),
     'delta_color': 'up' if _avg_ret >= 0 else 'down'},
    {'label': '產業檔數', 'value': format_number(len(ranking_df), kind='int')},
])

st.markdown("<div style='margin:0.5rem 0'></div>", unsafe_allow_html=True)

# 格式化顯示
display_df = ranking_df.copy()
display_df['報酬率'] = display_df['報酬率'].apply(lambda x: format_number(x * 100, kind='pct', signed=True))
display_df['波動率'] = display_df['波動率'].apply(lambda x: format_number(x * 100, kind='pct'))

col1, col2 = st.columns(2)

with col1:
    # 強勢產業
    st.markdown('**🔥 強勢產業 (前 10)**')
    render_data_table(display_df.head(10), numeric_cols=['股票數'])

with col2:
    # 弱勢產業
    st.markdown('**❄️ 弱勢產業 (後 10)**')
    render_data_table(display_df.tail(10).iloc[::-1], numeric_cols=['股票數'])

# ========== 產業報酬分佈 ==========
st.markdown(create_section_header('產業報酬分佈', icon='📊'), unsafe_allow_html=True)

import plotly.express as px
import plotly.graph_objects as go

# 紅漲綠跌的發散色階（低報酬綠 → 高報酬紅）
_ret_scale = [COLORS['down'], COLORS['flat'], COLORS['up']]

with create_error_boundary('產業報酬分佈圖'):
    # 長條圖
    fig_bar = px.bar(
        ranking_df.head(20),
        x='產業',
        y='報酬率',
        color='報酬率',
        color_continuous_scale=_ret_scale,
        title=f'產業報酬率排行 ({period})',
    )

    fig_bar.update_layout(
        xaxis_tickangle=-45,
        yaxis_tickformat='.1%',
    )

    apply_dark_theme(fig_bar, height=CHART_CONFIG['height_md'])
    st.plotly_chart(fig_bar, use_container_width=True)

# ========== 產業風險報酬分析 ==========
st.markdown(create_section_header('風險報酬分析', icon='⚖️'), unsafe_allow_html=True)

with create_error_boundary('風險報酬散佈圖'):
    fig_scatter = px.scatter(
        ranking_df,
        x='波動率',
        y='報酬率',
        size='股票數',
        color='報酬率',
        color_continuous_scale=_ret_scale,
        hover_name='產業',
        title='產業風險報酬散佈圖',
    )

    fig_scatter.update_layout(
        xaxis_title='波動率 (年化)',
        yaxis_title='報酬率',
        xaxis_tickformat='.1%',
        yaxis_tickformat='.1%',
    )

    # 加入象限線
    avg_return = ranking_df['報酬率'].mean()
    avg_vol = ranking_df['波動率'].mean()

    fig_scatter.add_hline(y=avg_return, line_dash='dash', line_color=COLORS['text_muted'])
    fig_scatter.add_vline(x=avg_vol, line_dash='dash', line_color=COLORS['text_muted'])

    fig_scatter.add_annotation(x=avg_vol * 0.6, y=avg_return * 2, text='低風險高報酬', showarrow=False)
    fig_scatter.add_annotation(x=avg_vol * 1.5, y=avg_return * 2, text='高風險高報酬', showarrow=False)
    fig_scatter.add_annotation(x=avg_vol * 0.6, y=-avg_return, text='低風險低報酬', showarrow=False)
    fig_scatter.add_annotation(x=avg_vol * 1.5, y=-avg_return, text='高風險低報酬', showarrow=False)

    apply_dark_theme(fig_scatter, height=CHART_CONFIG['height_lg'])
    st.plotly_chart(fig_scatter, use_container_width=True)

# ========== 產業走勢比較 ==========
st.markdown(create_section_header('產業走勢比較', icon='📈'), unsafe_allow_html=True)

# 選擇要比較的產業
top_industries = ranking_df['產業'].head(10).tolist()
bottom_industries = ranking_df['產業'].tail(5).tolist()

selected_industries = st.multiselect(
    '選擇要比較的產業',
    list(industry_returns.keys()),
    default=top_industries[:5],
)

if selected_industries:
    with create_error_boundary('產業走勢比較圖'):
        fig_line = go.Figure()

        for industry in selected_industries:
            if industry in industry_returns:
                cumulative = industry_returns[industry]['cumulative']
                fig_line.add_trace(go.Scatter(
                    x=cumulative.index,
                    y=(cumulative - 1) * 100,
                    name=industry,
                    mode='lines',
                ))

        # 加入大盤
        benchmark_period = benchmark.tail(period_days)
        benchmark_return = benchmark_period / benchmark_period.iloc[0] - 1

        fig_line.add_trace(go.Scatter(
            x=benchmark_return.index,
            y=benchmark_return.values * 100,
            name='大盤',
            mode='lines',
            line=dict(color=COLORS['text_secondary'], width=2, dash='dash'),
        ))

        fig_line.update_layout(
            title='產業累積報酬比較',
            xaxis_title='日期',
            yaxis_title='累積報酬 (%)',
        )

        apply_dark_theme(fig_line, height=CHART_CONFIG['height_md'], unified_hover=True)
        st.plotly_chart(fig_line, use_container_width=True)

# ========== 產業輪動分析 ==========
st.markdown(create_section_header('產業輪動分析', icon='🔄'), unsafe_allow_html=True)

st.caption('觀察不同期間的產業排名變化')

# 計算不同期間的報酬
periods = {'1W': 5, '1M': 22, '3M': 66}

rotation_data = []

for industry in industry_returns.keys():
    row = {'產業': industry}
    for period_name, days in periods.items():
        period_returns = calculate_industry_returns(close, stock_info, active_stocks, days)
        if industry in period_returns:
            row[period_name] = period_returns[industry]['return']
        else:
            row[period_name] = np.nan
    rotation_data.append(row)

rotation_df = pd.DataFrame(rotation_data)

# 計算動能變化
rotation_df['短期動能'] = rotation_df['1W'] - rotation_df['1M']
rotation_df = rotation_df.sort_values('短期動能', ascending=False)

# 顯示動能轉強/轉弱的產業
col1, col2 = st.columns(2)

_pct_signed = lambda x: format_number(x * 100, kind='pct', signed=True) if pd.notna(x) else '-'

with col1:
    st.markdown('**📈 動能轉強產業**')
    momentum_up = rotation_df[rotation_df['短期動能'] > 0].head(10)
    if len(momentum_up) > 0:
        display_up = momentum_up[['產業', '1W', '1M', '短期動能']].copy()
        display_up['1W'] = display_up['1W'].apply(_pct_signed)
        display_up['1M'] = display_up['1M'].apply(_pct_signed)
        display_up['短期動能'] = display_up['短期動能'].apply(_pct_signed)
        render_data_table(display_up)
    else:
        show_empty_state('目前無明顯動能轉強的產業', icon='📈')

with col2:
    st.markdown('**📉 動能轉弱產業**')
    momentum_down = rotation_df[rotation_df['短期動能'] < 0].tail(10).iloc[::-1]
    if len(momentum_down) > 0:
        display_down = momentum_down[['產業', '1W', '1M', '短期動能']].copy()
        display_down['1W'] = display_down['1W'].apply(_pct_signed)
        display_down['1M'] = display_down['1M'].apply(_pct_signed)
        display_down['短期動能'] = display_down['短期動能'].apply(_pct_signed)
        render_data_table(display_down)
    else:
        show_empty_state('目前無明顯動能轉弱的產業', icon='📉')

# ========== 個別產業詳情 ==========
st.markdown(create_section_header('個別產業詳情', icon='🔍'), unsafe_allow_html=True)

selected_industry = st.selectbox(
    '選擇產業',
    list(industry_returns.keys()),
)

if selected_industry:
    # 取得該產業的股票
    industry_stocks = stock_info[stock_info['category'] == selected_industry]['stock_id'].tolist()
    industry_stocks = [s for s in industry_stocks if s in active_stocks and s in close.columns]

    if industry_stocks:
        # 計算各股票報酬
        stock_returns = []
        close_period = close[industry_stocks].tail(period_days)

        for stock_id in industry_stocks:
            stock_close = close_period[stock_id].dropna()
            if len(stock_close) > 1:
                ret = (stock_close.iloc[-1] / stock_close.iloc[0]) - 1
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''

                stock_returns.append({
                    '代號': stock_id,
                    '名稱': name,
                    '報酬率': ret,
                    '報酬率_raw': ret,
                    '最新股價': stock_close.iloc[-1],
                    '最新股價_raw': stock_close.iloc[-1],
                })

        stock_df = pd.DataFrame(stock_returns)
        stock_df = stock_df.sort_values('報酬率_raw', ascending=False).reset_index(drop=True)

        st.caption(f'{selected_industry} 共 {len(industry_stocks)} 檔股票，選擇個股查看詳細分析')

        # 股票列表（扁平資料表，移除逐列 st.columns 的巢狀層級）
        list_df = stock_df[['代號', '名稱', '報酬率_raw', '最新股價_raw']].copy()
        list_df['報酬率'] = list_df['報酬率_raw'].apply(lambda x: format_number(x * 100, kind='pct', signed=True))
        list_df['股價'] = list_df['最新股價_raw'].apply(lambda x: format_number(x, kind='price'))
        render_data_table(list_df[['代號', '名稱', '報酬率', '股價']])

        # 個股詳情選擇（取代逐列詳情按鈕，避免 3 層巢狀）
        stock_options = stock_df['代號'].tolist()
        option_labels = {r['代號']: f"{r['代號']} {r['名稱']}" for r in stock_returns}
        current_detail = get_state(StateKeys.SELECTED_STOCK_DETAIL)
        detail_index = stock_options.index(current_detail) if current_detail in stock_options else 0

        picked = st.selectbox(
            '選擇個股查看詳情',
            stock_options,
            index=detail_index,
            format_func=lambda x: option_labels.get(x, x),
            key='industry_detail_picker',
        )
        set_state(StateKeys.SELECTED_STOCK_DETAIL, picked)
        detail_stock_id = picked

        # 顯示選中股票的詳細分析
        if detail_stock_id and detail_stock_id in [r['代號'] for r in stock_returns]:
                # 取得股票資訊
                detail_info = stock_info[stock_info['stock_id'] == detail_stock_id]
                detail_name = detail_info['name'].values[0] if len(detail_info) > 0 else ''

                st.markdown(create_section_header(f'{detail_stock_id} {detail_name} 詳細分析', icon='📈'), unsafe_allow_html=True)

                # 取得完整數據
                detail_close = close[detail_stock_id].dropna()

                if len(detail_close) > 0:
                    latest_price = detail_close.iloc[-1]
                    prev_price = detail_close.iloc[-2] if len(detail_close) > 1 else latest_price
                    day_change = (latest_price / prev_price - 1) * 100

                    # 期間報酬
                    period_close = detail_close.tail(period_days)
                    if len(period_close) > 1:
                        period_ret = (period_close.iloc[-1] / period_close.iloc[0] - 1) * 100
                        period_ret_kpi = {'value': format_number(period_ret, kind='pct', signed=True),
                                          'delta_color': 'up' if period_ret >= 0 else 'down'}
                    else:
                        period_ret_kpi = {'value': '-'}

                    # 近一年報酬
                    if len(detail_close) >= 252:
                        year_ret = (detail_close.iloc[-1] / detail_close.iloc[-252] - 1) * 100
                        year_ret_kpi = {'value': format_number(year_ret, kind='pct', signed=True),
                                        'delta_color': 'up' if year_ret >= 0 else 'down'}
                    else:
                        year_ret_kpi = {'value': '-'}

                    # 波動率
                    returns = detail_close.pct_change().dropna()
                    vol_value = (format_number(returns.std() * np.sqrt(252) * 100, kind='pct')
                                 if len(returns) > 20 else '-')

                    # 基本資訊 KPI 列
                    render_kpi_row([
                        {'label': '最新股價', 'value': format_number(latest_price, kind='price'),
                         'delta': format_number(day_change, kind='pct', signed=True),
                         'delta_color': 'up' if day_change >= 0 else 'down'},
                        {'label': f'{period} 報酬', **period_ret_kpi},
                        {'label': '近一年報酬', **year_ret_kpi},
                        {'label': '年化波動率', 'value': vol_value},
                    ])

                    import plotly.graph_objects as go
                    from core.indicators import rsi, macd

                    # 詳情提為獨立 Tab（最多 2 層：tab → columns）
                    tab_trend, tab_tech, tab_bench = st.tabs(['📈 走勢與量', '🔍 技術指標', '📊 與大盤比較'])

                    # ----- Tab 1：走勢與成交量 -----
                    with tab_trend:
                        chart_col1, chart_col2 = st.columns(2)

                        with chart_col1:
                            st.markdown(f'**{period} 走勢**')

                            period_data = detail_close.tail(period_days)

                            fig_price = go.Figure()
                            fig_price.add_trace(go.Scatter(
                                x=period_data.index,
                                y=period_data.values,
                                mode='lines',
                                name='股價',
                                line=dict(color=COLORS['accent'], width=2),
                                fill='tozeroy',
                                fillcolor='rgba(59, 130, 246, 0.1)',
                            ))

                            if len(period_data) >= 20:
                                ma20 = period_data.rolling(20).mean()
                                fig_price.add_trace(go.Scatter(
                                    x=ma20.index,
                                    y=ma20.values,
                                    mode='lines',
                                    name='MA20',
                                    line=dict(color=COLORS['flow_trust'], width=1, dash='dash'),
                                ))

                            fig_price.update_layout(
                                margin=dict(l=0, r=0, t=0, b=0),
                                xaxis_title='',
                                yaxis_title='股價',
                            )

                            apply_dark_theme(fig_price, height=CHART_CONFIG['height_sm'])
                            st.plotly_chart(fig_price, use_container_width=True)

                        with chart_col2:
                            st.markdown('**成交量**')

                            if detail_stock_id in volume.columns:
                                vol_data = volume[detail_stock_id].dropna().tail(period_days)

                                fig_vol = go.Figure()
                                fig_vol.add_trace(go.Bar(
                                    x=vol_data.index,
                                    y=vol_data.values / 1000,  # 以千股顯示
                                    name='成交量',
                                    marker_color=COLORS['down_weak'],
                                ))

                                fig_vol.update_layout(
                                    margin=dict(l=0, r=0, t=0, b=0),
                                    xaxis_title='',
                                    yaxis_title='成交量 (千股)',
                                )

                                apply_dark_theme(fig_vol, height=CHART_CONFIG['height_sm'])
                                st.plotly_chart(fig_vol, use_container_width=True)
                            else:
                                show_empty_state('無成交量數據', icon='📊')

                    # ----- Tab 2：技術指標 -----
                    with tab_tech:
                        tech_col1, tech_col2, tech_col3, tech_col4 = st.columns(4)

                        # RSI
                        rsi_val = rsi(detail_close, 14).iloc[-1]
                        with tech_col1:
                            if pd.notna(rsi_val):
                                if rsi_val > 70:
                                    st.error(f'RSI(14): {rsi_val:.1f} 超買')
                                elif rsi_val < 30:
                                    st.success(f'RSI(14): {rsi_val:.1f} 超賣')
                                elif rsi_val > 50:
                                    st.info(f'RSI(14): {rsi_val:.1f} 偏多')
                                else:
                                    st.warning(f'RSI(14): {rsi_val:.1f} 偏空')
                            else:
                                st.info('RSI: -')

                        # MACD
                        macd_line, signal_line, hist = macd(detail_close)
                        with tech_col2:
                            if len(macd_line) > 0 and pd.notna(macd_line.iloc[-1]):
                                if macd_line.iloc[-1] > signal_line.iloc[-1]:
                                    st.success('MACD: 多頭排列')
                                else:
                                    st.warning('MACD: 空頭排列')
                            else:
                                st.info('MACD: -')

                        # 均線
                        with tech_col3:
                            if len(detail_close) >= 20:
                                ma20_val = detail_close.rolling(20).mean().iloc[-1]
                                if latest_price > ma20_val:
                                    st.success('站上 MA20')
                                else:
                                    st.warning('跌破 MA20')
                            else:
                                st.info('MA20: -')

                        # 與產業比較
                        with tech_col4:
                            industry_ret = industry_returns[selected_industry]['return']
                            stock_ret = next((r['報酬率_raw'] for r in stock_returns if r['代號'] == detail_stock_id), 0)

                            if stock_ret > industry_ret:
                                diff = (stock_ret - industry_ret) * 100
                                st.success(f'優於產業 +{diff:.1f}%')
                            else:
                                diff = (industry_ret - stock_ret) * 100
                                st.warning(f'落後產業 -{diff:.1f}%')

                    # ----- Tab 3：與大盤比較 -----
                    with tab_bench:
                        benchmark_period = benchmark.tail(period_days)
                        benchmark_return = (benchmark_period.iloc[-1] / benchmark_period.iloc[0] - 1)

                        stock_period_close = detail_close.tail(period_days)
                        stock_return = (stock_period_close.iloc[-1] / stock_period_close.iloc[0] - 1)

                        # 正規化走勢比較
                        fig_compare = go.Figure()

                        stock_normalized = stock_period_close / stock_period_close.iloc[0] * 100
                        benchmark_normalized = benchmark_period / benchmark_period.iloc[0] * 100

                        fig_compare.add_trace(go.Scatter(
                            x=stock_normalized.index,
                            y=stock_normalized.values,
                            name=f'{detail_stock_id} {detail_name}',
                            line=dict(color=COLORS['accent'], width=2),
                        ))

                        fig_compare.add_trace(go.Scatter(
                            x=benchmark_normalized.index,
                            y=benchmark_normalized.values,
                            name='大盤指數',
                            line=dict(color=COLORS['text_secondary'], width=1, dash='dash'),
                        ))

                        fig_compare.update_layout(
                            xaxis_title='',
                            yaxis_title='相對表現 (初始=100)',
                        )

                        compare_col1, compare_col2 = st.columns([3, 1])

                        apply_dark_theme(fig_compare, height=CHART_CONFIG['height_sm'])

                        with compare_col1:
                            st.plotly_chart(fig_compare, use_container_width=True)

                        with compare_col2:
                            st.metric('個股報酬', format_number(stock_return * 100, kind='pct', signed=True))
                            st.metric('大盤報酬', format_number(benchmark_return * 100, kind='pct', signed=True))

                            alpha = stock_return - benchmark_return
                            if alpha > 0:
                                st.success(f'Alpha: {format_number(alpha * 100, kind="pct", signed=True)}')
                            else:
                                st.error(f'Alpha: {format_number(alpha * 100, kind="pct", signed=True)}')

# ========== 說明 ==========
with st.expander('📖 指標說明'):
    st.markdown('''
    ### 產業報酬率

    各產業內所有活躍股票的等權重平均報酬率。

    ### 風險報酬象限

    - **左上（低風險高報酬）**：理想投資標的
    - **右上（高風險高報酬）**：適合積極型投資人
    - **左下（低風險低報酬）**：適合保守型投資人
    - **右下（高風險低報酬）**：應避免的區域

    ### 產業輪動

    比較不同時間週期的表現，找出動能轉強或轉弱的產業：
    - **短期動能 = 近 1 週報酬 - 近 1 月報酬**
    - 正值表示近期表現優於中期，動能轉強
    - 負值表示近期表現不如中期，動能轉弱
    ''')
