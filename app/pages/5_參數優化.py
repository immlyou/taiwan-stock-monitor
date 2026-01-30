"""
參數優化頁面 - Grid Search 找出最佳策略參數
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from core.strategies import ValueStrategy, GrowthStrategy, MomentumStrategy
from core.optimizer import GridSearchOptimizer, OptimizationResult
from app.components.sidebar import render_sidebar_mini

st.set_page_config(page_title='參數優化', page_icon='🎯', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='optimizer')

st.title('🎯 策略參數優化')
st.markdown('使用 Grid Search 自動找出最佳策略參數組合')
st.markdown('---')

# ========== 策略選擇 ==========
st.subheader('1️⃣ 選擇策略')

strategy_type = st.selectbox(
    '選擇要優化的策略',
    ['價值投資', '成長投資', '動能投資'],
    help='選擇要進行參數優化的策略類型'
)

strategy_class_map = {
    '價值投資': ValueStrategy,
    '成長投資': GrowthStrategy,
    '動能投資': MomentumStrategy,
}

st.markdown('---')

# ========== 參數範圍設定 ==========
st.subheader('2️⃣ 設定參數搜索範圍')

param_grid = {}

if strategy_type == '價值投資':
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('**本益比上限**')
        pe_min = st.number_input('最小值', 5.0, 50.0, 10.0, 1.0, key='pe_min')
        pe_max = st.number_input('最大值', 5.0, 50.0, 25.0, 1.0, key='pe_max')
        pe_step = st.number_input('間距', 1.0, 10.0, 5.0, 1.0, key='pe_step')
        param_grid['pe_max'] = list(np.arange(pe_min, pe_max + 0.1, pe_step))

    with col2:
        st.markdown('**股價淨值比上限**')
        pb_min = st.number_input('最小值', 0.5, 5.0, 1.0, 0.1, key='pb_min')
        pb_max = st.number_input('最大值', 0.5, 5.0, 2.5, 0.1, key='pb_max')
        pb_step = st.number_input('間距', 0.1, 1.0, 0.5, 0.1, key='pb_step')
        param_grid['pb_max'] = list(np.arange(pb_min, pb_max + 0.01, pb_step))

    with col3:
        st.markdown('**殖利率下限 (%)**')
        dy_min = st.number_input('最小值', 0.0, 10.0, 2.0, 0.5, key='dy_min')
        dy_max = st.number_input('最大值', 0.0, 10.0, 6.0, 0.5, key='dy_max')
        dy_step = st.number_input('間距', 0.5, 2.0, 1.0, 0.5, key='dy_step')
        param_grid['dividend_yield_min'] = list(np.arange(dy_min, dy_max + 0.01, dy_step))

elif strategy_type == '成長投資':
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('**營收年增率下限 (%)**')
        yoy_min = st.number_input('最小值', 0.0, 100.0, 10.0, 5.0, key='yoy_min')
        yoy_max = st.number_input('最大值', 0.0, 100.0, 50.0, 5.0, key='yoy_max')
        yoy_step = st.number_input('間距', 5.0, 20.0, 10.0, 5.0, key='yoy_step')
        param_grid['revenue_yoy_min'] = list(np.arange(yoy_min, yoy_max + 0.1, yoy_step))

    with col2:
        st.markdown('**營收月增率下限 (%)**')
        mom_min = st.number_input('最小值', 0.0, 50.0, 5.0, 5.0, key='mom_min')
        mom_max = st.number_input('最大值', 0.0, 50.0, 25.0, 5.0, key='mom_max')
        mom_step = st.number_input('間距', 5.0, 10.0, 5.0, 5.0, key='mom_step')
        param_grid['revenue_mom_min'] = list(np.arange(mom_min, mom_max + 0.1, mom_step))

    with col3:
        st.markdown('**連續成長月數**')
        months_options = st.multiselect(
            '選擇要測試的月數',
            [1, 2, 3, 4, 5, 6],
            default=[2, 3, 4],
        )
        param_grid['consecutive_months'] = months_options if months_options else [3]

elif strategy_type == '動能投資':
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('**突破天數**')
        breakout_options = st.multiselect(
            '選擇要測試的天數',
            [5, 10, 20, 40, 60],
            default=[10, 20, 40],
        )
        param_grid['breakout_days'] = breakout_options if breakout_options else [20]

    with col2:
        st.markdown('**量比下限**')
        vol_min = st.number_input('最小值', 1.0, 3.0, 1.2, 0.1, key='vol_min')
        vol_max = st.number_input('最大值', 1.0, 3.0, 2.0, 0.1, key='vol_max')
        vol_step = st.number_input('間距', 0.1, 0.5, 0.2, 0.1, key='vol_step')
        param_grid['volume_ratio_min'] = list(np.arange(vol_min, vol_max + 0.01, vol_step))

    with col3:
        st.markdown('**RSI 範圍**')
        rsi_min_options = st.multiselect('RSI 下限', [30, 40, 50, 60], default=[40, 50])
        rsi_max_options = st.multiselect('RSI 上限', [60, 70, 80, 90], default=[70, 80])
        param_grid['rsi_min'] = rsi_min_options if rsi_min_options else [50]
        param_grid['rsi_max'] = rsi_max_options if rsi_max_options else [80]

# 計算總組合數
total_combinations = 1
for values in param_grid.values():
    total_combinations *= len(values)

st.info(f'📊 總共 **{total_combinations}** 種參數組合')

st.markdown('---')

# ========== 評估指標設定 ==========
st.subheader('3️⃣ 評估設定')

col1, col2 = st.columns(2)

with col1:
    metric = st.selectbox(
        '評估指標',
        ['sharpe_ratio', 'annual_return', 'max_drawdown', 'win_rate'],
        format_func=lambda x: {
            'sharpe_ratio': 'Sharpe Ratio (風險調整報酬)',
            'annual_return': '年化報酬率',
            'max_drawdown': '最大回撤 (越小越好)',
            'win_rate': '勝率',
        }[x],
        help='選擇用來評估策略好壞的指標'
    )

with col2:
    backtest_period = st.selectbox(
        '回測期間',
        ['1Y', '2Y', '3Y', '5Y'],
        index=1,
        format_func=lambda x: {
            '1Y': '近 1 年',
            '2Y': '近 2 年',
            '3Y': '近 3 年',
            '5Y': '近 5 年',
        }[x],
    )

st.markdown('---')

# ========== 執行優化 ==========
st.subheader('4️⃣ 執行優化')

if st.button('🚀 開始優化', type='primary', use_container_width=True):
    if total_combinations > 500:
        st.warning(f'⚠️ 參數組合數量較多 ({total_combinations} 種)，優化可能需要較長時間...')

    progress_bar = st.progress(0)
    status_text = st.empty()

    with st.spinner('正在執行參數優化...'):
        try:
            # 載入數據
            status_text.text('載入數據中...')
            loader = get_loader()
            data = {
                'close': loader.get('close'),
                'volume': loader.get('volume'),
                'pe_ratio': loader.get('pe_ratio'),
                'pb_ratio': loader.get('pb_ratio'),
                'dividend_yield': loader.get('dividend_yield'),
                'revenue_yoy': loader.get('revenue_yoy'),
                'revenue_mom': loader.get('revenue_mom'),
            }

            # 根據回測期間篩選數據
            period_days = {'1Y': 252, '2Y': 504, '3Y': 756, '5Y': 1260}[backtest_period]
            for key in data:
                if isinstance(data[key], pd.DataFrame):
                    data[key] = data[key].tail(period_days)

            progress_bar.progress(20)
            status_text.text('開始參數搜索...')

            # 簡化的回測函數
            def simple_backtest(strategy, data):
                result = strategy.run(data)
                close = data['close']

                # 簡單計算策略報酬
                if len(result.stocks) > 0:
                    # 取得選股的平均報酬
                    selected = [s for s in result.stocks if s in close.columns]
                    if selected:
                        returns = close[selected].pct_change().mean(axis=1).dropna()
                        if len(returns) > 0:
                            annual_return = returns.mean() * 252
                            volatility = returns.std() * np.sqrt(252)
                            sharpe = annual_return / volatility if volatility > 0 else 0

                            # 最大回撤
                            cumulative = (1 + returns).cumprod()
                            rolling_max = cumulative.cummax()
                            drawdown = (cumulative - rolling_max) / rolling_max
                            max_dd = abs(drawdown.min())

                            # 勝率
                            win_rate = (returns > 0).sum() / len(returns)

                            class MockMetrics:
                                pass

                            metrics = MockMetrics()
                            metrics.sharpe_ratio = sharpe
                            metrics.annual_return = annual_return
                            metrics.max_drawdown = -max_dd
                            metrics.win_rate = win_rate

                            class MockResult:
                                pass

                            mock = MockResult()
                            mock.metrics = metrics
                            return mock

                # 若無有效結果
                class EmptyMetrics:
                    sharpe_ratio = -999
                    annual_return = -999
                    max_drawdown = -999
                    win_rate = 0

                class EmptyResult:
                    metrics = EmptyMetrics()

                return EmptyResult()

            # 執行 Grid Search
            strategy_class = strategy_class_map[strategy_type]
            higher_is_better = metric != 'max_drawdown'

            optimizer = GridSearchOptimizer(
                strategy_class,
                param_grid,
                metric,
                higher_is_better,
            )

            # 手動執行以更新進度
            combinations = optimizer._generate_combinations()
            results = []

            for i, params in enumerate(combinations):
                score = optimizer._evaluate_params(params, data, simple_backtest)
                results.append({**params, 'score': score})

                progress = 20 + int(70 * (i + 1) / len(combinations))
                progress_bar.progress(progress)
                status_text.text(f'測試參數組合 {i + 1}/{len(combinations)}...')

            results_df = pd.DataFrame(results)

            # 找出最佳結果
            if higher_is_better:
                best_idx = results_df['score'].idxmax()
            else:
                best_idx = results_df['score'].idxmin()

            best_row = results_df.loc[best_idx]
            best_params = {k: v for k, v in best_row.items() if k != 'score'}
            best_score = best_row['score']

            progress_bar.progress(100)
            status_text.text('優化完成！')

            # 顯示結果
            st.success('✅ 參數優化完成！')

            # 最佳參數
            st.markdown('### 🏆 最佳參數組合')

            col1, col2 = st.columns([2, 1])

            with col1:
                params_df = pd.DataFrame([best_params]).T
                params_df.columns = ['最佳值']
                params_df.index.name = '參數'
                st.dataframe(params_df, use_container_width=True)

            with col2:
                metric_names = {
                    'sharpe_ratio': 'Sharpe Ratio',
                    'annual_return': '年化報酬率',
                    'max_drawdown': '最大回撤',
                    'win_rate': '勝率',
                }
                st.metric(metric_names[metric], f'{best_score:.4f}')

            # 所有結果排行
            st.markdown('### 📊 參數組合排行')

            # 排序
            sorted_df = results_df.sort_values('score', ascending=not higher_is_better)
            sorted_df = sorted_df.reset_index(drop=True)
            sorted_df.index = sorted_df.index + 1
            sorted_df.index.name = '排名'

            st.dataframe(sorted_df.head(20), use_container_width=True)

            # 參數敏感度分析
            if len(param_grid) >= 2:
                st.markdown('### 🔍 參數敏感度分析')

                param_names = list(param_grid.keys())[:2]

                if len(param_grid[param_names[0]]) > 1 and len(param_grid[param_names[1]]) > 1:
                    # 建立熱力圖數據
                    pivot_df = results_df.pivot_table(
                        values='score',
                        index=param_names[0],
                        columns=param_names[1],
                        aggfunc='mean'
                    )

                    import plotly.express as px
                    fig = px.imshow(
                        pivot_df,
                        labels=dict(x=param_names[1], y=param_names[0], color='Score'),
                        title=f'{param_names[0]} vs {param_names[1]} 參數熱力圖',
                        color_continuous_scale='RdYlGn' if higher_is_better else 'RdYlGn_r',
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # 儲存結果
            st.session_state['optimization_result'] = {
                'best_params': best_params,
                'best_score': best_score,
                'all_results': results_df,
                'strategy_type': strategy_type,
                'metric': metric,
            }

            # 一鍵套用按鈕
            st.markdown('### 🎯 套用最佳參數')

            apply_col1, apply_col2 = st.columns(2)

            with apply_col1:
                if st.button('🚀 套用到選股篩選', type='primary', use_container_width=True):
                    strategy_type_map = {'價值投資': 'value', '成長投資': 'growth', '動能投資': 'momentum'}
                    st.session_state['apply_optimized_params'] = {
                        'strategy_type': strategy_type_map.get(strategy_type, 'value'),
                        'params': best_params,
                        'score': best_score,
                        'metric': metric,
                    }
                    st.switch_page('pages/1_選股篩選.py')

            with apply_col2:
                # 匯出按鈕
                csv = sorted_df.to_csv(index=True).encode('utf-8-sig')
                st.download_button(
                    '📥 下載完整結果 (CSV)',
                    csv,
                    f'優化結果_{strategy_type}_{pd.Timestamp.now().strftime("%Y%m%d_%H%M")}.csv',
                    'text/csv',
                    use_container_width=True,
                )

        except Exception as e:
            st.error(f'優化過程發生錯誤: {e}')
            import traceback
            st.code(traceback.format_exc())

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 什麼是參數優化？

    參數優化是透過系統性地測試不同的參數組合，找出在歷史數據中表現最佳的設定。

    ### Grid Search 方法

    Grid Search（網格搜索）會窮舉所有可能的參數組合：
    - 優點：保證找到搜索範圍內的最佳解
    - 缺點：組合數量多時耗時較長

    ### 評估指標說明

    | 指標 | 說明 | 越高/越低越好 |
    |------|------|--------------|
    | Sharpe Ratio | 風險調整報酬 | 越高越好 |
    | 年化報酬率 | 年化的報酬率 | 越高越好 |
    | 最大回撤 | 歷史最大虧損幅度 | 越小越好 |
    | 勝率 | 正報酬交易日比例 | 越高越好 |

    ### 注意事項

    ⚠️ **過度擬合警告**：最佳參數可能只是針對歷史數據的過度擬合，不代表未來表現。
    建議使用 Walk-Forward 分析或樣本外測試驗證參數的穩定性。
    ''')
