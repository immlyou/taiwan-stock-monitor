"""
回測分析頁面
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, load_benchmark, get_active_stocks
from core.strategies import ValueStrategy, GrowthStrategy, MomentumStrategy, CompositeStrategy
from core.backtest.engine import BacktestEngine, quick_backtest
from app.components.charts import (
    create_portfolio_chart,
    create_drawdown_chart,
    create_monthly_returns_heatmap,
)
from config import STRATEGY_PRESETS
from app.components.sidebar import render_sidebar_mini
from app.components.session_manager import (
    init_session_state, get_state, set_state, StateKeys
)

st.set_page_config(page_title='回測分析', page_icon='📊', layout='wide')

# 初始化 Session State
init_session_state()

# 渲染側邊欄
render_sidebar_mini(current_page='backtest')

st.title('📊 回測分析')

# 顯示資料日期
try:
    loader = get_loader()
    data_start = loader.get('close').index.min().strftime('%Y-%m-%d')
    data_end = loader.get('close').index.max().strftime('%Y-%m-%d')
    st.caption(f'📅 可用資料期間: {data_start} ~ {data_end}')
except:
    st.caption('📅 資料日期: 載入中...')

st.markdown('---')

# ========== 1. 策略選擇 ==========
st.subheader('1️⃣ 選擇策略')

strategy_cols = st.columns(4)
strategy_options = {
    '價值投資': {'icon': '💎', 'desc': '低本益比、高殖利率'},
    '成長投資': {'icon': '🚀', 'desc': '營收高速成長'},
    '動能投資': {'icon': '📈', 'desc': '價量動能突破'},
    '綜合策略': {'icon': '🎯', 'desc': '多因子綜合'},
}

for i, (name, info) in enumerate(strategy_options.items()):
    with strategy_cols[i]:
        current_strategy = get_state(StateKeys.BACKTEST_STRATEGY)
        if st.button(
            f"{info['icon']} {name}",
            use_container_width=True,
            type='primary' if current_strategy == name else 'secondary',
            key=f'strat_btn_{name}'
        ):
            set_state(StateKeys.BACKTEST_STRATEGY, name)
            st.rerun()
        st.caption(info['desc'])

strategy_type = get_state(StateKeys.BACKTEST_STRATEGY)

st.markdown('---')

# ========== 2. 回測設定 ==========
st.subheader('2️⃣ 回測設定')

setting_col1, setting_col2, setting_col3 = st.columns(3)

with setting_col1:
    st.markdown('**📆 回測期間**')

    # 快速選擇
    period_option = st.radio(
        '期間',
        ['近1年', '近3年', '近5年', '自訂'],
        index=1,
        horizontal=True
    )

    if period_option == '自訂':
        start_date = st.date_input(
            '開始日期',
            value=datetime.now() - timedelta(days=365*3),
            min_value=datetime(2007, 1, 1)
        )
        end_date = st.date_input(
            '結束日期',
            value=datetime.now()
        )
    else:
        end_date = datetime.now()
        years = {'近1年': 1, '近3年': 3, '近5年': 5}[period_option]
        start_date = end_date - timedelta(days=365 * years)

    st.caption(f'回測期間: {start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date} ~ {end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date}')

with setting_col2:
    st.markdown('**💰 資金與持股**')

    initial_capital = st.number_input(
        '初始資金 (萬)',
        min_value=10,
        max_value=10000,
        value=100,
        step=10,
        help='初始投資金額'
    )
    initial_capital = initial_capital * 10000  # 轉換為元

    max_stocks = st.slider(
        '最大持股數',
        5, 30, 10, 1,
        help='同時持有的最大股票數量'
    )

    rebalance_freq = st.selectbox(
        '換股頻率',
        ['每月', '每季', '每半年'],
        index=0,
        help='重新篩選並調整持股的頻率'
    )
    freq_map = {'每月': 'M', '每季': 'Q', '每半年': '2Q'}

with setting_col3:
    st.markdown('**⚙️ 進階設定**')

    weight_method = st.selectbox(
        '權重方法',
        ['等權重', '市值加權', '評分加權'],
        index=0,
        help='資金分配到各股票的方式'
    )
    weight_map = {'等權重': 'equal', '市值加權': 'market_cap', '評分加權': 'score'}

    commission_discount = st.slider(
        '手續費折扣',
        0.1, 1.0, 0.6, 0.1,
        help='券商手續費折扣，0.6 = 六折'
    )

st.markdown('---')

# ========== 3. 風險控制 ==========
st.subheader('3️⃣ 風險控制')

risk_col1, risk_col2, risk_col3 = st.columns(3)

with risk_col1:
    use_stop_loss = st.checkbox('啟用停損', value=False, help='當個股虧損達到設定比例時賣出')
    if use_stop_loss:
        stop_loss_pct = st.slider('停損比例 (%)', 5, 30, 10, 1)
    else:
        stop_loss_pct = None

with risk_col2:
    use_take_profit = st.checkbox('啟用停利', value=False, help='當個股獲利達到設定比例時賣出')
    if use_take_profit:
        take_profit_pct = st.slider('停利比例 (%)', 10, 100, 30, 5)
    else:
        take_profit_pct = None

with risk_col3:
    use_trailing_stop = st.checkbox('啟用移動停損', value=False, help='當股價從高點回落達到設定比例時賣出')
    if use_trailing_stop:
        trailing_stop_pct = st.slider('移動停損 (%)', 5, 20, 10, 1)
    else:
        trailing_stop_pct = None

st.markdown('---')

# ========== 4. 策略參數 ==========
with st.expander('📋 策略參數設定', expanded=False):

    preset_type = st.radio(
        '快速選擇',
        ['保守型', '標準型', '積極型'],
        index=1,
        horizontal=True
    )
    preset_map = {'保守型': 'conservative', '標準型': 'standard', '積極型': 'aggressive'}

    params = {}

    if strategy_type == '價值投資':
        preset_key = preset_map[preset_type]
        defaults = STRATEGY_PRESETS.get('value', {}).get(preset_key, {}).get('params', {})

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            params['pe_max'] = st.slider('本益比上限', 1.0, 50.0, defaults.get('pe_max', 15.0), 0.5, key='bt_pe')
            params['use_pe'] = st.checkbox('使用本益比', value=True, key='bt_use_pe')
        with p_col2:
            params['pb_max'] = st.slider('股價淨值比上限', 0.1, 5.0, defaults.get('pb_max', 1.5), 0.1, key='bt_pb')
            params['use_pb'] = st.checkbox('使用股價淨值比', value=True, key='bt_use_pb')
        with p_col3:
            params['dividend_yield_min'] = st.slider('殖利率下限 (%)', 0.0, 15.0, defaults.get('dividend_yield_min', 4.0), 0.5, key='bt_dy')
            params['use_dividend'] = st.checkbox('使用殖利率', value=True, key='bt_use_dy')

    elif strategy_type == '成長投資':
        preset_key = preset_map[preset_type]
        defaults = STRATEGY_PRESETS.get('growth', {}).get(preset_key, {}).get('params', {})

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            params['revenue_yoy_min'] = st.slider('營收年增率下限 (%)', -50.0, 200.0, defaults.get('revenue_yoy_min', 20.0), 5.0, key='bt_yoy')
            params['use_yoy'] = st.checkbox('使用年增率', value=True, key='bt_use_yoy')
        with p_col2:
            params['revenue_mom_min'] = st.slider('營收月增率下限 (%)', -50.0, 100.0, defaults.get('revenue_mom_min', 10.0), 5.0, key='bt_mom')
            params['use_mom'] = st.checkbox('使用月增率', value=True, key='bt_use_mom')
        with p_col3:
            params['consecutive_months'] = st.slider('連續成長月數', 1, 12, defaults.get('consecutive_months', 3), 1, key='bt_consec')
            params['use_consecutive'] = st.checkbox('使用連續成長', value=True, key='bt_use_consec')

    elif strategy_type == '動能投資':
        preset_key = preset_map[preset_type]
        defaults = STRATEGY_PRESETS.get('momentum', {}).get(preset_key, {}).get('params', {})

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            params['breakout_days'] = st.slider('突破天數', 5, 120, defaults.get('breakout_days', 20), 5, key='bt_breakout')
            params['use_breakout'] = st.checkbox('使用價格突破', value=True, key='bt_use_breakout')
        with p_col2:
            params['volume_ratio_min'] = st.slider('量比下限', 0.5, 5.0, defaults.get('volume_ratio', 1.5), 0.1, key='bt_vol')
            params['use_volume'] = st.checkbox('使用成交量', value=True, key='bt_use_vol')
        with p_col3:
            params['rsi_min'] = st.slider('RSI 下限', 0, 100, defaults.get('rsi_min', 50), 5, key='bt_rsi_min')
            params['rsi_max'] = st.slider('RSI 上限', 0, 100, defaults.get('rsi_max', 80), 5, key='bt_rsi_max')
            params['use_rsi'] = st.checkbox('使用 RSI', value=True, key='bt_use_rsi')

    elif strategy_type == '綜合策略':
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            params['value_weight'] = st.slider('價值因子權重', 0.0, 1.0, 0.4, 0.1, key='bt_val_w')
            params['growth_weight'] = st.slider('成長因子權重', 0.0, 1.0, 0.3, 0.1, key='bt_grow_w')
            params['momentum_weight'] = st.slider('動能因子權重', 0.0, 1.0, 0.3, 0.1, key='bt_mom_w')
        with p_col2:
            params['top_n'] = st.slider('選取前 N 名', 5, 50, 20, 5, key='bt_topn')
            params['min_score'] = st.slider('最低分數門檻', 0, 100, 50, 5, key='bt_min_score')
            params['use_value'] = st.checkbox('使用價值因子', value=True, key='bt_use_val')
            params['use_growth'] = st.checkbox('使用成長因子', value=True, key='bt_use_grow')
            params['use_momentum'] = st.checkbox('使用動能因子', value=True, key='bt_use_mom')

st.markdown('---')

# ========== 5. 執行回測 ==========
st.subheader('4️⃣ 執行回測')

# 設定摘要
summary_col1, summary_col2 = st.columns([2, 1])

with summary_col1:
    st.markdown(f'''
    **回測設定摘要：**
    - 策略: {strategy_type}
    - 期間: {start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date} ~ {end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date}
    - 初始資金: {initial_capital:,.0f} 元
    - 最大持股: {max_stocks} 檔
    - 換股頻率: {rebalance_freq}
    - 風險控制: {'停損 ' + str(stop_loss_pct) + '%' if use_stop_loss else ''} {'停利 ' + str(take_profit_pct) + '%' if use_take_profit else ''} {'移動停損 ' + str(trailing_stop_pct) + '%' if use_trailing_stop else ''} {'無' if not (use_stop_loss or use_take_profit or use_trailing_stop) else ''}
    ''')

with summary_col2:
    run_button = st.button('🚀 開始回測', type='primary', use_container_width=True)

if run_button:
    with st.spinner('正在執行回測，請稍候...'):
        try:
            # 載入數據 (清除快取)
            loader = get_loader()
            loader.clear_cache()

            # 取得活躍股票列表 (排除已下市)
            active_stocks = get_active_stocks()

            # 過濾函數：只保留活躍股票
            def filter_active(df):
                if df is None:
                    return None
                cols = [c for c in df.columns if c in active_stocks]
                return df[cols] if cols else df

            data = {
                'close': filter_active(loader.get('close')),
                'volume': filter_active(loader.get('volume')),
                'pe_ratio': filter_active(loader.get('pe_ratio')),
                'pb_ratio': filter_active(loader.get('pb_ratio')),
                'dividend_yield': filter_active(loader.get('dividend_yield')),
                'revenue_yoy': filter_active(loader.get('revenue_yoy')),
                'revenue_mom': filter_active(loader.get('revenue_mom')),
                'market_value': filter_active(loader.get('market_value')),
                'benchmark': loader.get('benchmark'),  # benchmark 不需要過濾
            }

            # 建立策略
            strategy_map = {
                '價值投資': ValueStrategy(params),
                '成長投資': GrowthStrategy(params),
                '動能投資': MomentumStrategy(params),
                '綜合策略': CompositeStrategy(params),
            }

            strategy = strategy_map[strategy_type]

            # 建立回測引擎
            engine = BacktestEngine(
                initial_capital=initial_capital,
                commission_discount=commission_discount,
            )

            # 執行回測
            def strategy_func(data, date):
                return strategy.filter(data, date)

            benchmark_series = load_benchmark()

            result = engine.run(
                strategy_func=strategy_func,
                data=data,
                start_date=pd.Timestamp(start_date),
                end_date=pd.Timestamp(end_date),
                rebalance_freq=freq_map[rebalance_freq],
                max_stocks=max_stocks,
                weight_method=weight_map.get(weight_method, 'equal'),
                benchmark=benchmark_series,
            )

            # 儲存結果
            st.session_state['backtest_result'] = result
            st.session_state['result_strategy'] = strategy_type

            st.success('✅ 回測完成！')

        except Exception as e:
            st.error(f'回測時發生錯誤: {e}')
            import traceback
            st.code(traceback.format_exc())

# ========== 顯示回測結果 ==========
if 'backtest_result' in st.session_state:
    result = st.session_state['backtest_result']
    strategy_name = st.session_state.get('result_strategy', '')

    st.markdown('---')
    st.subheader(f'📈 {strategy_name} 回測結果')

    # 績效指標
    metrics = result.metrics

    st.markdown('#### 績效指標')

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric('總報酬率', f'{metrics.total_return:.2f}%',
                  delta=f'{metrics.total_return:+.2f}%' if metrics.total_return >= 0 else None)
        st.metric('年化報酬率', f'{metrics.annualized_return:.2f}%')

    with metric_col2:
        st.metric('最大回撤', f'{metrics.max_drawdown:.2f}%')
        st.metric('波動率', f'{metrics.volatility:.2f}%')

    with metric_col3:
        sharpe_color = 'normal' if metrics.sharpe_ratio >= 1 else 'off'
        st.metric('夏普比率', f'{metrics.sharpe_ratio:.2f}')
        st.metric('索提諾比率', f'{metrics.sortino_ratio:.2f}')

    with metric_col4:
        st.metric('勝率', f'{metrics.win_rate:.1f}%')
        st.metric('總交易次數', metrics.total_trades)

    # 與大盤比較
    if result.benchmark_comparison:
        st.markdown('#### 與大盤比較')
        comp = result.benchmark_comparison

        comp_col1, comp_col2, comp_col3 = st.columns(3)
        with comp_col1:
            excess = comp.get('excess_return', 0)
            st.metric(
                '超額報酬',
                f'{excess:.2f}%',
                delta=f'{excess:+.2f}%'
            )
        with comp_col2:
            st.metric('Alpha', f"{comp.get('alpha', 0):.2f}%")
        with comp_col3:
            st.metric('Beta', f"{comp.get('beta', 0):.2f}")

    # 淨值走勢圖
    st.markdown('#### 淨值走勢')

    benchmark_series = load_benchmark()
    fig = create_portfolio_chart(
        result.portfolio_values,
        benchmark=benchmark_series,
        title='投資組合 vs 大盤'
    )
    st.plotly_chart(fig, use_container_width=True)

    # 回撤與月報酬
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown('#### 回撤分析')
        fig_dd = create_drawdown_chart(result.portfolio_values)
        st.plotly_chart(fig_dd, use_container_width=True)

    with chart_col2:
        st.markdown('#### 月報酬率')
        try:
            returns = result.portfolio_values.pct_change().dropna()
            fig_monthly = create_monthly_returns_heatmap(returns)
            st.plotly_chart(fig_monthly, use_container_width=True)
        except Exception:
            st.info('月報酬率數據不足')

    # 交易記錄
    st.markdown('#### 交易記錄')

    if len(result.trades) > 0:
        trades_df = result.trades.copy()
        trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date']).dt.strftime('%Y-%m-%d')
        trades_df['exit_date'] = pd.to_datetime(trades_df['exit_date']).dt.strftime('%Y-%m-%d')
        trades_df['entry_price'] = trades_df['entry_price'].round(2)
        trades_df['exit_price'] = trades_df['exit_price'].round(2)
        trades_df['pnl'] = trades_df['pnl'].round(0)
        trades_df['return'] = trades_df['return'].round(2)

        trades_df.columns = ['股票', '買入日期', '買入價', '賣出日期', '賣出價',
                            '股數', '損益', '報酬率(%)', '持有天數']

        st.dataframe(
            trades_df,
            use_container_width=True,
            hide_index=True,
            height=300,
        )

        # 下載
        csv = trades_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label='📥 下載交易記錄',
            data=csv,
            file_name=f'回測交易記錄_{strategy_name}_{pd.Timestamp.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )
    else:
        st.info('無交易記錄')

# ========== 說明 ==========
with st.expander('📖 回測說明'):
    st.markdown('''
    ### 回測流程
    1. 根據選定的策略，在每個換股日篩選符合條件的股票
    2. 將資金分配到選中的股票
    3. 持有到下個換股日，重新篩選並調整持股
    4. 計算整個期間的績效指標

    ### 績效指標說明
    | 指標 | 說明 | 參考值 |
    |------|------|--------|
    | 總報酬率 | 期末淨值相對於期初的總報酬 | - |
    | 年化報酬率 | 換算成每年的報酬率 | > 10% 佳 |
    | 最大回撤 | 期間內從高點到低點的最大跌幅 | < 20% 佳 |
    | 波動率 | 報酬率的標準差，衡量風險 | 越低越穩定 |
    | 夏普比率 | 風險調整後報酬 | > 1 佳 |
    | 勝率 | 獲利交易佔總交易的比例 | > 50% 佳 |

    ### 風險控制
    - **停損**: 當個股虧損達到設定比例時賣出，控制單筆損失
    - **停利**: 當個股獲利達到設定比例時賣出，鎖定獲利
    - **移動停損**: 當股價從高點回落達到設定比例時賣出

    ### 交易成本
    - 手續費: 0.1425% × 折扣 (買賣各一次)
    - 交易稅: 0.3% (僅賣出時收取)
    - 最低手續費: 20 元

    ### 注意事項
    ⚠️ 回測結果不代表未來績效，實際交易可能有滑價、流動性等影響
    ''')
