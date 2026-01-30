"""
風險分析頁面 - VaR、CVaR 及投資組合風險評估
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from core.risk import RiskAnalyzer, calculate_portfolio_var, stress_test, monte_carlo_simulation
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error, safe_execute, create_error_boundary

st.set_page_config(page_title='風險分析', page_icon='⚠️', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='risk')

st.title('⚠️ 風險分析')
st.markdown('分析投資組合的潛在風險與下行保護')
st.markdown('---')

# 載入數據
@st.cache_data(ttl=3600)
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'benchmark': loader.get_benchmark(),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

# ========== 分析模式選擇 ==========
st.subheader('1️⃣ 選擇分析模式')

analysis_mode = st.radio(
    '分析對象',
    ['單一股票', '投資組合'],
    horizontal=True,
)

st.markdown('---')

# ========== 股票/投資組合選擇 ==========
st.subheader('2️⃣ 選擇分析標的')

active_stocks = get_active_stocks()
stock_info = data['stock_info']
stock_options = {f"{row['stock_id']} {row['name']}": row['stock_id']
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks}

if analysis_mode == '單一股票':
    selected_option = st.selectbox(
        '選擇股票',
        list(stock_options.keys()),
        index=list(stock_options.keys()).index('2330 台積電') if '2330 台積電' in stock_options else 0,
    )
    selected_stocks = [stock_options[selected_option]]
    weights = {selected_stocks[0]: 1.0}

else:  # 投資組合
    st.markdown('**建立投資組合**')

    # 使用 session state 管理投資組合
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = {}

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        add_stock = st.selectbox('選擇股票', list(stock_options.keys()), key='add_stock')

    with col2:
        add_weight = st.number_input('權重 (%)', 1, 100, 20, key='add_weight')

    with col3:
        st.markdown('<br>', unsafe_allow_html=True)
        if st.button('➕ 加入'):
            stock_id = stock_options[add_stock]
            st.session_state.portfolio[stock_id] = add_weight / 100
            st.rerun()

    # 顯示目前投資組合
    if st.session_state.portfolio:
        st.markdown('**目前投資組合：**')

        portfolio_data = []
        for stock_id, weight in st.session_state.portfolio.items():
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''
            portfolio_data.append({
                '代號': stock_id,
                '名稱': name,
                '權重': f'{weight * 100:.1f}%',
            })

        portfolio_df = pd.DataFrame(portfolio_data)
        st.dataframe(portfolio_df, use_container_width=True, hide_index=True)

        total_weight = sum(st.session_state.portfolio.values())
        if abs(total_weight - 1.0) > 0.01:
            st.warning(f'⚠️ 權重總和為 {total_weight * 100:.1f}%，建議調整為 100%')

        if st.button('🗑️ 清空投資組合'):
            st.session_state.portfolio = {}
            st.rerun()

        selected_stocks = list(st.session_state.portfolio.keys())
        weights = st.session_state.portfolio
    else:
        st.info('請加入股票到投資組合')
        selected_stocks = []
        weights = {}

st.markdown('---')

# ========== 分析期間 ==========
st.subheader('3️⃣ 分析期間')

period = st.selectbox(
    '選擇分析期間',
    ['1Y', '2Y', '3Y', '5Y'],
    index=1,
    format_func=lambda x: {'1Y': '近 1 年', '2Y': '近 2 年', '3Y': '近 3 年', '5Y': '近 5 年'}[x],
)

period_days = {'1Y': 252, '2Y': 504, '3Y': 756, '5Y': 1260}[period]

st.markdown('---')

# ========== 執行分析 ==========
st.subheader('4️⃣ 風險分析結果')

if selected_stocks and weights:
    close = data['close']
    benchmark = data['benchmark']

    # 計算投資組合價值
    available_stocks = [s for s in selected_stocks if s in close.columns]

    if available_stocks:
        # 取得分析期間數據
        close_period = close[available_stocks].tail(period_days)
        benchmark_period = benchmark.tail(period_days)

        # 計算投資組合報酬
        weight_series = pd.Series({s: weights[s] for s in available_stocks})
        weight_series = weight_series / weight_series.sum()  # 正規化

        portfolio_returns = (close_period.pct_change() * weight_series).sum(axis=1).dropna()
        portfolio_value = (1 + portfolio_returns).cumprod()
        portfolio_value.iloc[0] = 1  # 初始值為 1

        # 風險分析
        analyzer = RiskAnalyzer()
        benchmark_returns = benchmark_period.pct_change().dropna()

        # VaR 與 CVaR
        var_95 = analyzer.calculate_var_historical(portfolio_returns, 0.95)
        var_99 = analyzer.calculate_var_historical(portfolio_returns, 0.99)
        cvar_95 = analyzer.calculate_cvar(portfolio_returns, 0.95)
        cvar_99 = analyzer.calculate_cvar(portfolio_returns, 0.99)

        # 波動率
        volatility = analyzer.calculate_volatility(portfolio_returns)
        downside_vol = analyzer.calculate_downside_volatility(portfolio_returns)

        # 最大回撤
        max_dd, peak_date, trough_date = analyzer.calculate_max_drawdown(portfolio_value)

        # Beta 與追蹤誤差
        beta = analyzer.calculate_beta(portfolio_returns, benchmark_returns)
        tracking_error = analyzer.calculate_tracking_error(portfolio_returns, benchmark_returns)

        # ========== 顯示結果 ==========

        # 主要風險指標
        st.markdown('### 📊 主要風險指標')

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric('95% VaR (日)', f'{var_95 * 100:.2f}%',
                      help='在 95% 信心水準下，單日最大可能損失')

        with col2:
            st.metric('95% CVaR (日)', f'{cvar_95 * 100:.2f}%',
                      help='超過 VaR 時的平均損失（更保守的風險估計）')

        with col3:
            st.metric('年化波動率', f'{volatility * 100:.2f}%',
                      help='報酬率的標準差（年化）')

        with col4:
            st.metric('最大回撤', f'{max_dd * 100:.2f}%',
                      help='歷史最大跌幅')

        # 進階風險指標
        st.markdown('### 📈 進階風險指標')

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric('99% VaR (日)', f'{var_99 * 100:.2f}%')

        with col2:
            st.metric('下行波動率', f'{downside_vol * 100:.2f}%',
                      help='只計算負報酬的波動率')

        with col3:
            st.metric('Beta', f'{beta:.2f}',
                      help='相對大盤的波動程度，>1 表示比大盤更劇烈')

        with col4:
            st.metric('追蹤誤差', f'{tracking_error * 100:.2f}%',
                      help='與大盤報酬的偏離程度')

        # 走勢圖
        st.markdown('### 📉 投資組合走勢')

        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        with create_error_boundary('投資組合走勢圖'):
            # 正規化基準
            benchmark_normalized = benchmark_period / benchmark_period.iloc[0]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=portfolio_value.index,
                y=portfolio_value.values,
                name='投資組合',
                line=dict(color='blue', width=2),
            ))
            fig.add_trace(go.Scatter(
                x=benchmark_normalized.index,
                y=benchmark_normalized.values,
                name='大盤指數',
                line=dict(color='gray', width=1, dash='dash'),
            ))

            fig.update_layout(
                title='投資組合 vs 大盤',
                xaxis_title='日期',
                yaxis_title='累積報酬 (初始=1)',
                hovermode='x unified',
                height=400,
            )

            st.plotly_chart(fig, use_container_width=True)

        # 回撤分析
        st.markdown('### 📉 回撤分析')

        with create_error_boundary('回撤分析圖'):
            drawdown = (portfolio_value - portfolio_value.cummax()) / portfolio_value.cummax()

            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=drawdown.index,
                y=drawdown.values * 100,
                fill='tozeroy',
                name='回撤',
                line=dict(color='red'),
            ))

            fig_dd.update_layout(
                title='歷史回撤',
                xaxis_title='日期',
                yaxis_title='回撤 (%)',
                height=300,
            )

            st.plotly_chart(fig_dd, use_container_width=True)

            if peak_date and trough_date:
                st.caption(f'最大回撤發生於 {peak_date.strftime("%Y-%m-%d")} 至 {trough_date.strftime("%Y-%m-%d")}')

        # 壓力測試
        st.markdown('### 🔥 壓力測試')

        scenarios = {
            '輕度下跌 (-5%)': -0.05,
            '中度下跌 (-10%)': -0.10,
            '大幅下跌 (-20%)': -0.20,
            '崩盤 (-30%)': -0.30,
            '小幅上漲 (+5%)': 0.05,
            '中幅上漲 (+10%)': 0.10,
        }

        current_value = portfolio_value.iloc[-1]
        initial_investment = 1000000  # 假設投資 100 萬

        stress_data = []
        for scenario_name, change in scenarios.items():
            new_value = current_value * (1 + change)
            pnl = initial_investment * (new_value - current_value)
            stress_data.append({
                '情境': scenario_name,
                '變動幅度': f'{change * 100:+.0f}%',
                '損益 (元)': f'{pnl:+,.0f}',
            })

        stress_df = pd.DataFrame(stress_data)
        st.dataframe(stress_df, use_container_width=True, hide_index=True)

        # 蒙地卡羅模擬
        st.markdown('### 🎲 蒙地卡羅模擬（未來 252 交易日）')

        with create_error_boundary('蒙地卡羅模擬'):
            with st.spinner('執行蒙地卡羅模擬...'):
                simulations = monte_carlo_simulation(
                    portfolio_returns,
                    days=252,
                    simulations=500,
                    initial_value=1.0,
                )

                # 計算統計
                final_values = simulations.iloc[-1]
                percentiles = [5, 25, 50, 75, 95]
                percentile_values = np.percentile(final_values, percentiles)

                sim_col1, sim_col2 = st.columns(2)

                with sim_col1:
                    st.markdown('**模擬結果分佈**')
                    percentile_df = pd.DataFrame({
                        '百分位': [f'{p}%' for p in percentiles],
                        '預期報酬': [f'{(v - 1) * 100:+.1f}%' for v in percentile_values],
                    })
                    st.dataframe(percentile_df, use_container_width=True, hide_index=True)

                with sim_col2:
                    st.markdown('**模擬走勢圖**')

                    fig_mc = go.Figure()

                    # 畫出部分模擬路徑
                    for i in range(min(50, len(simulations.columns))):
                        fig_mc.add_trace(go.Scatter(
                            y=simulations.iloc[:, i].values,
                            mode='lines',
                            line=dict(width=0.5, color='lightblue'),
                            showlegend=False,
                        ))

                    # 畫出中位數
                    median_path = simulations.median(axis=1)
                    fig_mc.add_trace(go.Scatter(
                        y=median_path.values,
                        mode='lines',
                        line=dict(width=2, color='blue'),
                        name='中位數',
                    ))

                    fig_mc.update_layout(
                        xaxis_title='交易日',
                        yaxis_title='投資組合價值',
                        height=300,
                    )

                    st.plotly_chart(fig_mc, use_container_width=True)

    else:
        st.warning('所選股票無可用數據')

else:
    st.info('請選擇要分析的股票或建立投資組合')

# ========== 說明 ==========
with st.expander('📖 風險指標說明'):
    st.markdown('''
    ### VaR (Value at Risk) 風險值

    VaR 表示在特定信心水準下，投資組合在單一時間段內可能遭受的最大損失。

    **例如：95% VaR = -2%** 表示有 95% 的機率，單日損失不會超過 2%。

    ### CVaR (Conditional VaR) 條件風險值

    CVaR 也稱為 Expected Shortfall，計算的是超過 VaR 時的平均損失。
    比 VaR 更保守，更適合評估極端風險。

    ### Beta 值

    衡量投資組合相對於大盤的波動程度：
    - Beta = 1: 與大盤同步
    - Beta > 1: 比大盤更劇烈（高風險高報酬）
    - Beta < 1: 比大盤穩定（低風險低報酬）

    ### 蒙地卡羅模擬

    基於歷史報酬的統計特性，模擬未來可能的價格走勢，
    用於評估不同情境下的風險和報酬。
    ''')
