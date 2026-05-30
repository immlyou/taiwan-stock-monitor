"""
比較分析頁面 - 多策略與多股票比較
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px


from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from core.strategies import ValueStrategy, GrowthStrategy, MomentumStrategy, CompositeStrategy
from core.risk import RiskAnalyzer
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error, create_error_boundary
from app.components.page_header import render_page_header, render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.theme import (
    COLORS,
    create_page_title,
    create_section_header,
    render_data_table,
    format_number,
)
from app.components.charts import apply_dark_theme, CHART_CONFIG

st.set_page_config(page_title='比較分析', page_icon='📊', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='compare')

# 全域行情列（sidebar 後、標題前呼叫一次）
render_global_ticker_bar()

st.markdown(create_page_title('比較分析', subtitle='多策略與多股票比較', icon='📊'), unsafe_allow_html=True)

# 載入數據
@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner='載入數據中...')
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'volume': loader.get('volume'),
        'pe_ratio': loader.get('pe_ratio'),
        'pb_ratio': loader.get('pb_ratio'),
        'dividend_yield': loader.get('dividend_yield'),
        'revenue_yoy': loader.get('revenue_yoy'),
        'revenue_mom': loader.get('revenue_mom'),
        'benchmark': loader.get_benchmark(),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
    close = data['close']
    benchmark = data['benchmark']
    stock_info = data['stock_info']
    active_stocks = get_active_stocks()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

# 股票選項
stock_options = {f"{row['stock_id']} {row['name']}": row['stock_id']
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks}

# Tab 選擇
tab1, tab2 = st.tabs(['📈 策略比較', '📊 股票比較'])

# ========== 策略比較 ==========
with tab1:
    st.markdown(create_section_header('策略績效比較', icon='📈'), unsafe_allow_html=True)
    st.caption('比較不同策略在相同期間的表現')

    col1, col2 = st.columns(2)

    with col1:
        strategies_to_compare = st.multiselect(
            '選擇要比較的策略',
            ['價值投資', '成長投資', '動能投資', '綜合策略'],
            default=['價值投資', '成長投資', '動能投資'],
        )

    with col2:
        compare_period = st.selectbox(
            '比較期間',
            ['近3個月', '近6個月', '近1年', '近2年'],
            index=2
        )

    period_days = {'近3個月': 63, '近6個月': 126, '近1年': 252, '近2年': 504}[compare_period]

    if st.button('🚀 執行策略比較', type='primary'):
        if len(strategies_to_compare) < 2:
            st.warning('請選擇至少 2 個策略進行比較')
        else:
            with st.spinner('正在計算策略績效...'):
                try:
                    strategy_map = {
                        '價值投資': ValueStrategy(),
                        '成長投資': GrowthStrategy(),
                        '動能投資': MomentumStrategy(),
                        '綜合策略': CompositeStrategy(),
                    }

                    results = {}
                    returns_data = {}

                    for strategy_name in strategies_to_compare:
                        strategy = strategy_map[strategy_name]
                        result = strategy.run(data)

                        # 過濾活躍股票
                        result.stocks = [s for s in result.stocks if s in active_stocks and s in close.columns]

                        if len(result.stocks) > 0:
                            # 計算策略報酬
                            selected_close = close[result.stocks].tail(period_days)
                            returns = selected_close.pct_change().mean(axis=1).dropna()
                            cumulative = (1 + returns).cumprod()

                            # 計算績效指標
                            analyzer = RiskAnalyzer()
                            total_return = (cumulative.iloc[-1] - 1) * 100 if len(cumulative) > 0 else 0
                            annual_return = returns.mean() * 252 * 100
                            volatility = returns.std() * np.sqrt(252) * 100
                            sharpe = annual_return / volatility if volatility > 0 else 0

                            # 最大回撤
                            rolling_max = cumulative.cummax()
                            drawdown = (cumulative - rolling_max) / rolling_max
                            max_dd = drawdown.min() * 100

                            results[strategy_name] = {
                                'stocks_count': len(result.stocks),
                                'total_return': total_return,
                                'annual_return': annual_return,
                                'volatility': volatility,
                                'sharpe_ratio': sharpe,
                                'max_drawdown': max_dd,
                            }
                            returns_data[strategy_name] = cumulative
                except Exception as e:
                    show_error(e, title='策略計算失敗', suggestion='請檢查策略設定或資料是否完整')
                    results = {}

                if results:
                    # 顯示績效比較表
                    st.markdown(create_section_header('績效比較表', icon='📋'), unsafe_allow_html=True)

                    comparison_df = pd.DataFrame(results).T
                    comparison_df.columns = ['選股數', '期間報酬%', '年化報酬%', '波動率%', 'Sharpe', '最大回撤%']

                    # 格式化
                    display_df = comparison_df.copy()
                    display_df.insert(0, '策略', display_df.index)
                    display_df['選股數'] = display_df['選股數'].astype(int)
                    for col in ['期間報酬%', '年化報酬%', '波動率%', '最大回撤%']:
                        display_df[col] = display_df[col].apply(lambda x: format_number(x, kind='pct', signed=True))
                    display_df['Sharpe'] = display_df['Sharpe'].apply(lambda x: format_number(x, kind='price'))

                    render_data_table(
                        display_df,
                        freeze_cols=1,
                        numeric_cols=['選股數', '期間報酬%', '年化報酬%', '波動率%', 'Sharpe', '最大回撤%'],
                    )

                    # 累積報酬走勢圖
                    st.markdown(create_section_header('累積報酬走勢', icon='📈'), unsafe_allow_html=True)

                    with create_error_boundary('累積報酬走勢圖'):
                        fig = go.Figure()

                        line_colors = [COLORS['accent'], COLORS['flow_trust'], COLORS['flow_dealer'], COLORS['up']]
                        for i, (name, cumulative) in enumerate(returns_data.items()):
                            fig.add_trace(go.Scatter(
                                x=cumulative.index,
                                y=(cumulative - 1) * 100,
                                name=name,
                                mode='lines',
                                line=dict(color=line_colors[i % len(line_colors)], width=2),
                            ))

                        # 加入大盤比較
                        benchmark_period = benchmark.tail(period_days)
                        benchmark_norm = benchmark_period / benchmark_period.iloc[0]
                        fig.add_trace(go.Scatter(
                            x=benchmark_norm.index,
                            y=(benchmark_norm - 1) * 100,
                            name='大盤',
                            mode='lines',
                            line=dict(color=COLORS['text_muted'], width=1, dash='dash'),
                        ))

                        apply_dark_theme(
                            fig,
                            height=CHART_CONFIG['height_md'],
                            unified_hover=True,
                            title=f'{compare_period} 累積報酬比較',
                            xaxis_title='日期',
                            yaxis_title='累積報酬 (%)',
                        )

                        st.plotly_chart(fig, use_container_width=True)

                    # 風險報酬散佈圖
                    st.markdown(create_section_header('風險報酬分析', icon='🎯'), unsafe_allow_html=True)

                    with create_error_boundary('風險報酬散佈圖'):
                        scatter_df = comparison_df[['年化報酬%', '波動率%', 'Sharpe']].astype(float)
                        scatter_df['策略'] = scatter_df.index

                        fig_scatter = px.scatter(
                            scatter_df,
                            x='波動率%',
                            y='年化報酬%',
                            text='策略',
                            size='Sharpe',
                            color='Sharpe',
                            color_continuous_scale=CHART_CONFIG['diverging_scale'],
                            title='風險報酬散佈圖 (圓點大小 = Sharpe Ratio)'
                        )

                        fig_scatter.update_traces(textposition='top center')
                        apply_dark_theme(fig_scatter, height=CHART_CONFIG['height_md'])

                        st.plotly_chart(fig_scatter, use_container_width=True)

                else:
                    st.warning('無法計算策略績效，請檢查數據')

# ========== 股票比較 ==========
with tab2:
    st.markdown(create_section_header('股票比較分析', icon='📊'), unsafe_allow_html=True)
    st.caption('比較多檔股票的技術面與基本面')

    col1, col2 = st.columns([3, 1])

    with col1:
        stocks_to_compare = st.multiselect(
            '選擇要比較的股票 (最多5檔)',
            list(stock_options.keys()),
            max_selections=5,
            help='選擇要並排比較的股票'
        )

    with col2:
        stock_period = st.selectbox(
            '分析期間',
            ['近1個月', '近3個月', '近6個月', '近1年'],
            index=2,
            key='stock_period'
        )

    stock_period_days = {'近1個月': 21, '近3個月': 63, '近6個月': 126, '近1年': 252}[stock_period]

    if stocks_to_compare and len(stocks_to_compare) >= 2:
        stock_ids = [stock_options[s] for s in stocks_to_compare]

        # 收集股票數據
        stock_data = []

        for stock_id in stock_ids:
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''
            category = info['category'].values[0] if len(info) > 0 else ''

            if stock_id in close.columns:
                stock_close = close[stock_id].dropna().tail(stock_period_days)

                if len(stock_close) > 1:
                    latest_price = stock_close.iloc[-1]
                    returns = stock_close.pct_change().dropna()

                    total_return = (stock_close.iloc[-1] / stock_close.iloc[0] - 1) * 100
                    volatility = returns.std() * np.sqrt(252) * 100

                    rolling_max = stock_close.cummax()
                    drawdown = (stock_close - rolling_max) / rolling_max
                    max_dd = drawdown.min() * 100

                    # 基本面數據
                    pe = data['pe_ratio'][stock_id].dropna().iloc[-1] if stock_id in data['pe_ratio'].columns else None
                    pb = data['pb_ratio'][stock_id].dropna().iloc[-1] if stock_id in data['pb_ratio'].columns else None
                    dy = data['dividend_yield'][stock_id].dropna().iloc[-1] if stock_id in data['dividend_yield'].columns else None

                    stock_data.append({
                        'stock_id': stock_id,
                        '代號': stock_id,
                        '名稱': name,
                        '產業': category,
                        '現價': latest_price,
                        '期間報酬%': total_return,
                        '波動率%': volatility,
                        '最大回撤%': max_dd,
                        'PE': pe,
                        'PB': pb,
                        '殖利率%': dy,
                        'close_series': stock_close,
                    })

        if stock_data:
            # 基本資料比較表
            st.markdown(create_section_header('基本面比較', icon='📋'), unsafe_allow_html=True)

            compare_df = pd.DataFrame([{k: v for k, v in d.items() if k != 'close_series'} for d in stock_data])

            display_cols = ['代號', '名稱', '產業', '現價', '期間報酬%', '波動率%', '最大回撤%', 'PE', 'PB', '殖利率%']
            display_df = compare_df[display_cols].copy()

            for col in ['現價', 'PE', 'PB']:
                display_df[col] = display_df[col].apply(lambda x: format_number(x, kind='price') if pd.notnull(x) else 'N/A')
            for col in ['期間報酬%', '最大回撤%']:
                display_df[col] = display_df[col].apply(lambda x: format_number(x, kind='pct', signed=True) if pd.notnull(x) else 'N/A')
            for col in ['波動率%', '殖利率%']:
                display_df[col] = display_df[col].apply(lambda x: format_number(x, kind='pct') if pd.notnull(x) else 'N/A')

            # 9 欄比較表水平捲動，sticky 表頭 + 凍結代號欄
            render_data_table(
                display_df,
                freeze_cols=1,
                numeric_cols=['現價', '期間報酬%', '波動率%', '最大回撤%', 'PE', 'PB', '殖利率%'],
            )

            # 價格走勢比較
            st.markdown(create_section_header('價格走勢比較 (標準化)', icon='📈'), unsafe_allow_html=True)

            fig_price = go.Figure()

            line_palette = [
                COLORS['accent'], COLORS['flow_trust'], COLORS['flow_dealer'],
                COLORS['up'], COLORS['down'],
            ]
            for i, d in enumerate(stock_data):
                normalized = d['close_series'] / d['close_series'].iloc[0] * 100
                fig_price.add_trace(go.Scatter(
                    x=normalized.index,
                    y=normalized.values,
                    name=f"{d['代號']} {d['名稱']}",
                    mode='lines',
                    line=dict(color=line_palette[i % len(line_palette)], width=2),
                ))

            apply_dark_theme(
                fig_price,
                height=CHART_CONFIG['height_md'],
                unified_hover=True,
                title=f'{stock_period} 標準化價格走勢 (起始=100)',
                xaxis_title='日期',
                yaxis_title='標準化價格',
            )

            st.plotly_chart(fig_price, use_container_width=True)

            # 報酬率長條圖比較
            st.markdown(create_section_header('報酬率比較', icon='📊'), unsafe_allow_html=True)

            returns_df = pd.DataFrame([{
                '股票': f"{d['代號']} {d['名稱']}",
                '期間報酬%': d['期間報酬%'],
            } for d in stock_data])

            fig_bar = px.bar(
                returns_df,
                x='股票',
                y='期間報酬%',
                color='期間報酬%',
                color_continuous_scale=CHART_CONFIG['diverging_scale'],
                title=f'{stock_period} 報酬率比較'
            )

            apply_dark_theme(fig_bar, height=CHART_CONFIG['height_md'])

            st.plotly_chart(fig_bar, use_container_width=True)

            # 基本面雷達圖
            if all(d.get('PE') and d.get('PB') and d.get('殖利率%') for d in stock_data):
                st.markdown(create_section_header('基本面雷達圖', icon='🎯'), unsafe_allow_html=True)

                # 標準化數據 (0-100)，缺值以 N/A（None）標記不參與標準化
                pe_values = [d['PE'] for d in stock_data]
                pb_values = [d['PB'] for d in stock_data]
                dy_values = [d['殖利率%'] for d in stock_data]
                return_values = [d['期間報酬%'] for d in stock_data]

                def normalize(values, inverse=False):
                    valid = [v for v in values if v is not None and pd.notnull(v)]
                    if not valid:
                        return ['N/A'] * len(values)
                    min_v, max_v = min(valid), max(valid)
                    if max_v == min_v:
                        return [50 if (v is not None and pd.notnull(v)) else 'N/A' for v in values]
                    out = []
                    for v in values:
                        if v is None or not pd.notnull(v):
                            out.append('N/A')
                        elif inverse:
                            out.append(100 - (v - min_v) / (max_v - min_v) * 100)
                        else:
                            out.append((v - min_v) / (max_v - min_v) * 100)
                    return out

                fig_radar = go.Figure()

                categories = ['PE (越低越好)', 'PB (越低越好)', '殖利率', '期間報酬']

                pe_n = normalize(pe_values, inverse=True)
                pb_n = normalize(pb_values, inverse=True)
                dy_n = normalize(dy_values)
                ret_n = normalize(return_values)

                for i, d in enumerate(stock_data):
                    fig_radar.add_trace(go.Scatterpolar(
                        r=[pe_n[i], pb_n[i], dy_n[i], ret_n[i]],
                        theta=categories,
                        fill='toself',
                        name=f"{d['代號']} {d['名稱']}",
                        line=dict(color=COLORS['accent']),
                    ))

                apply_dark_theme(
                    fig_radar,
                    height=CHART_CONFIG['height_md'],
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    showlegend=True,
                    title='基本面雷達圖比較',
                )

                st.plotly_chart(fig_radar, use_container_width=True)

    elif stocks_to_compare and len(stocks_to_compare) < 2:
        show_empty_state('請選擇至少 2 檔股票進行比較', icon='📊', suggestion='從上方選單中再選擇一檔股票')
    else:
        show_empty_state('尚未選擇比較股票', icon='📊', suggestion='請從上方選擇要比較的股票')

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 策略比較

    比較不同選股策略在相同期間的績效表現：
    - **期間報酬**：策略選出的股票在該期間的平均報酬
    - **年化報酬**：換算成年度的報酬率
    - **波動率**：報酬率的標準差，代表風險
    - **Sharpe Ratio**：風險調整後報酬，越高越好
    - **最大回撤**：歷史最大跌幅

    ### 股票比較

    比較多檔股票的各項指標：
    - **標準化價格**：將起始價格設為 100，便於比較漲跌幅度
    - **基本面雷達圖**：比較 PE、PB、殖利率等指標

    ### 注意事項

    - 歷史績效不代表未來表現
    - 選股策略採用等權重計算平均報酬
    ''')
