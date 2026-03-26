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
from app.components.strategy_params import render_strategy_params, render_preset_selector
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.session_manager import (
    init_session_state, get_state, set_state, StateKeys
)
from app.components.portfolio_utils import (
    get_portfolio_names, create_portfolio, add_holdings_batch, load_portfolios, save_portfolios
)

st.set_page_config(page_title='回測分析', page_icon='📊', layout='wide')

# 初始化 Session State
init_session_state()

# 渲染側邊欄
render_sidebar_mini(current_page='backtest')

render_page_header("回測分析", icon="📈")

# 顯示資料日期
try:
    loader = get_loader()
    data_start = loader.get('close').index.min().strftime('%Y-%m-%d')
    data_end = loader.get('close').index.max().strftime('%Y-%m-%d')
    st.caption(f'📅 可用資料期間: {data_start} ~ {data_end}')
except Exception:
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
    freq_map = {'每月': 'ME', '每季': 'QE', '每半年': '2QE'}

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

    preset_key = render_preset_selector(key_prefix='bt_', horizontal=True)

    params = render_strategy_params(
        strategy_type=strategy_type,
        strategy_presets=STRATEGY_PRESETS,
        preset_key=preset_key,
        key_prefix='bt_',
        show_help=False,
    )

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
            set_state(StateKeys.BACKTEST_RESULT, result)
            set_state(StateKeys.RESULT_STRATEGY, strategy_type)

            st.success('✅ 回測完成！')

        except Exception as e:
            show_error(e, title='回測時發生錯誤')
            import traceback
            st.code(traceback.format_exc())

# ========== 顯示回測結果 ==========
if get_state(StateKeys.BACKTEST_RESULT) is not None:
    result = get_state(StateKeys.BACKTEST_RESULT)
    strategy_name = get_state(StateKeys.RESULT_STRATEGY, '')

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
            show_empty_state('月報酬率數據不足', icon='📅')

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
        show_empty_state('無交易記錄', icon='📋')

    # ========== 以最後持倉建立投資組合 ==========
    st.markdown('---')
    st.markdown('#### 💼 以最後持倉建立投資組合')

    # 從交易記錄取得「尚未賣出」的持倉（exit_date 為 NaT 的記錄即為最後持倉）
    last_positions = []
    if len(result.trades) > 0:
        open_trades = result.trades[result.trades['exit_date'].isna()]
        if len(open_trades) > 0:
            for _, row in open_trades.iterrows():
                last_positions.append({
                    'stock_id': row['stock_id'],
                    'shares': int(row['shares']),
                    'cost_price': round(float(row['entry_price']), 2),
                })

    if last_positions:
        st.caption(f'回測結束時持有 {len(last_positions)} 檔股票，可將其匯入投資組合進行追蹤。')

        portfolio_col1, portfolio_col2 = st.columns([3, 1])

        with portfolio_col1:
            create_mode = st.radio(
                '建立方式',
                ['建立新投資組合', '加入現有投資組合'],
                horizontal=True,
                key='bt_portfolio_mode'
            )

        if create_mode == '建立新投資組合':
            with portfolio_col1:
                new_portfolio_name = st.text_input(
                    '新投資組合名稱',
                    value=f'回測_{strategy_name}_{pd.Timestamp.now().strftime("%Y%m%d")}',
                    key='bt_new_portfolio_name'
                )
            if st.button('💼 建立投資組合並匯入持倉', type='primary', key='bt_create_portfolio'):
                if new_portfolio_name:
                    try:
                        created = create_portfolio(new_portfolio_name)
                        if not created:
                            st.warning(f'投資組合「{new_portfolio_name}」已存在，將直接加入持股。')

                        prices = {p['stock_id']: p['cost_price'] for p in last_positions}
                        stocks = [p['stock_id'] for p in last_positions]

                        # 使用各自股數加入（需逐筆呼叫 add_holding）
                        portfolios = load_portfolios()
                        existing_stocks = [h['stock_id'] for h in portfolios[new_portfolio_name]['holdings']]
                        added = 0
                        for pos in last_positions:
                            if pos['stock_id'] not in existing_stocks:
                                portfolios[new_portfolio_name]['holdings'].append({
                                    'stock_id': pos['stock_id'],
                                    'shares': pos['shares'],
                                    'cost_price': pos['cost_price'],
                                    'buy_date': pd.Timestamp.now().strftime('%Y-%m-%d'),
                                })
                                added += 1
                        save_portfolios(portfolios)

                        st.success(f'✅ 已建立投資組合「{new_portfolio_name}」並匯入 {added} 檔持股')
                    except Exception as e:
                        st.error(f'建立投資組合失敗：{e}')
                else:
                    st.warning('請輸入投資組合名稱')

        else:  # 加入現有投資組合
            portfolio_names = get_portfolio_names()
            if portfolio_names:
                with portfolio_col1:
                    target_portfolio = st.selectbox('選擇投資組合', portfolio_names, key='bt_target_portfolio')
                if st.button('➕ 匯入持倉到投資組合', type='primary', key='bt_add_to_portfolio'):
                    try:
                        portfolios = load_portfolios()
                        existing_stocks = [h['stock_id'] for h in portfolios[target_portfolio]['holdings']]
                        added = 0
                        for pos in last_positions:
                            if pos['stock_id'] not in existing_stocks:
                                portfolios[target_portfolio]['holdings'].append({
                                    'stock_id': pos['stock_id'],
                                    'shares': pos['shares'],
                                    'cost_price': pos['cost_price'],
                                    'buy_date': pd.Timestamp.now().strftime('%Y-%m-%d'),
                                })
                                added += 1
                        save_portfolios(portfolios)
                        skipped = len(last_positions) - added
                        msg = f'✅ 已將 {added} 檔持股加入「{target_portfolio}」'
                        if skipped > 0:
                            msg += f'（{skipped} 檔已存在，略過）'
                        st.success(msg)
                    except Exception as e:
                        st.error(f'匯入持倉失敗：{e}')
            else:
                show_empty_state('尚未建立投資組合', icon='💼', suggestion='請選擇「建立新投資組合」')

        # 預覽最後持倉
        with st.expander('預覽最後持倉清單'):
            preview_df = pd.DataFrame(last_positions)
            preview_df.columns = ['股票代號', '股數', '成本價']
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
    else:
        st.info('回測結束時無未平倉持倉，無法匯入投資組合。（提示：若所有股票在回測結束前均已賣出，最後持倉為空。）')

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
