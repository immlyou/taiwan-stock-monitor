"""
產業分析頁面 - 各產業強弱勢分析
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error, safe_execute, create_error_boundary

st.set_page_config(page_title='產業分析', page_icon='🏭', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='industry')

st.title('🏭 產業分析')
st.markdown('分析各產業的強弱勢表現與輪動趨勢')
st.markdown('---')

# 載入數據
@st.cache_data(ttl=3600, show_spinner='載入數據中...')
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
@st.cache_data(ttl=3600)
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
st.subheader('📅 分析期間')

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

st.markdown('---')

# 計算產業報酬
industry_returns = calculate_industry_returns(
    close, stock_info, active_stocks, period_days
)

if not industry_returns:
    st.warning('無法計算產業報酬')
    st.stop()

# ========== 產業排行 ==========
st.subheader('🏆 產業強弱排行')

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

# 格式化顯示
display_df = ranking_df.copy()
display_df['報酬率'] = display_df['報酬率'].apply(lambda x: f'{x * 100:+.2f}%')
display_df['波動率'] = display_df['波動率'].apply(lambda x: f'{x * 100:.2f}%')

col1, col2 = st.columns([2, 1])

with col1:
    # 強勢產業
    st.markdown('**🔥 強勢產業 (前 10)**')
    st.dataframe(display_df.head(10), use_container_width=True)

with col2:
    # 弱勢產業
    st.markdown('**❄️ 弱勢產業 (後 10)**')
    st.dataframe(display_df.tail(10).iloc[::-1], use_container_width=True)

st.markdown('---')

# ========== 產業報酬分佈 ==========
st.subheader('📊 產業報酬分佈')

import plotly.express as px
import plotly.graph_objects as go

with create_error_boundary('產業報酬分佈圖'):
    # 長條圖
    fig_bar = px.bar(
        ranking_df.head(20),
        x='產業',
        y='報酬率',
        color='報酬率',
        color_continuous_scale=['red', 'yellow', 'green'],
        title=f'產業報酬率排行 ({period})',
    )

    fig_bar.update_layout(
        xaxis_tickangle=-45,
        height=400,
        yaxis_tickformat='.1%',
    )

    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown('---')

# ========== 產業風險報酬分析 ==========
st.subheader('⚖️ 風險報酬分析')

with create_error_boundary('風險報酬散佈圖'):
    fig_scatter = px.scatter(
        ranking_df,
        x='波動率',
        y='報酬率',
        size='股票數',
        color='報酬率',
        color_continuous_scale=['red', 'yellow', 'green'],
        hover_name='產業',
        title='產業風險報酬散佈圖',
    )

    fig_scatter.update_layout(
        xaxis_title='波動率 (年化)',
        yaxis_title='報酬率',
        xaxis_tickformat='.1%',
        yaxis_tickformat='.1%',
        height=500,
    )

    # 加入象限線
    avg_return = ranking_df['報酬率'].mean()
    avg_vol = ranking_df['波動率'].mean()

    fig_scatter.add_hline(y=avg_return, line_dash='dash', line_color='gray')
    fig_scatter.add_vline(x=avg_vol, line_dash='dash', line_color='gray')

    fig_scatter.add_annotation(x=avg_vol * 0.6, y=avg_return * 2, text='低風險高報酬', showarrow=False)
    fig_scatter.add_annotation(x=avg_vol * 1.5, y=avg_return * 2, text='高風險高報酬', showarrow=False)
    fig_scatter.add_annotation(x=avg_vol * 0.6, y=-avg_return, text='低風險低報酬', showarrow=False)
    fig_scatter.add_annotation(x=avg_vol * 1.5, y=-avg_return, text='高風險低報酬', showarrow=False)

    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown('---')

# ========== 產業走勢比較 ==========
st.subheader('📈 產業走勢比較')

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
            line=dict(color='black', width=2, dash='dash'),
        ))

        fig_line.update_layout(
            title='產業累積報酬比較',
            xaxis_title='日期',
            yaxis_title='累積報酬 (%)',
            hovermode='x unified',
            height=400,
        )

        st.plotly_chart(fig_line, use_container_width=True)

st.markdown('---')

# ========== 產業輪動分析 ==========
st.subheader('🔄 產業輪動分析')

st.markdown('觀察不同期間的產業排名變化')

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

with col1:
    st.markdown('**📈 動能轉強產業**')
    momentum_up = rotation_df[rotation_df['短期動能'] > 0].head(10)
    if len(momentum_up) > 0:
        display_up = momentum_up[['產業', '1W', '1M', '短期動能']].copy()
        display_up['1W'] = display_up['1W'].apply(lambda x: f'{x * 100:+.2f}%' if pd.notna(x) else '-')
        display_up['1M'] = display_up['1M'].apply(lambda x: f'{x * 100:+.2f}%' if pd.notna(x) else '-')
        display_up['短期動能'] = display_up['短期動能'].apply(lambda x: f'{x * 100:+.2f}%' if pd.notna(x) else '-')
        st.dataframe(display_up, use_container_width=True, hide_index=True)
    else:
        st.info('目前無明顯動能轉強的產業')

with col2:
    st.markdown('**📉 動能轉弱產業**')
    momentum_down = rotation_df[rotation_df['短期動能'] < 0].tail(10).iloc[::-1]
    if len(momentum_down) > 0:
        display_down = momentum_down[['產業', '1W', '1M', '短期動能']].copy()
        display_down['1W'] = display_down['1W'].apply(lambda x: f'{x * 100:+.2f}%' if pd.notna(x) else '-')
        display_down['1M'] = display_down['1M'].apply(lambda x: f'{x * 100:+.2f}%' if pd.notna(x) else '-')
        display_down['短期動能'] = display_down['短期動能'].apply(lambda x: f'{x * 100:+.2f}%' if pd.notna(x) else '-')
        st.dataframe(display_down, use_container_width=True, hide_index=True)
    else:
        st.info('目前無明顯動能轉弱的產業')

st.markdown('---')

# ========== 個別產業詳情 ==========
st.subheader('🔍 個別產業詳情')

selected_industry = st.selectbox(
    '選擇產業',
    list(industry_returns.keys()),
)

if selected_industry:
    # 取得該產業的股票
    industry_stocks = stock_info[stock_info['category'] == selected_industry]['stock_id'].tolist()
    industry_stocks = [s for s in industry_stocks if s in active_stocks and s in close.columns]

    if industry_stocks:
        st.markdown(f'**{selected_industry}** 共 {len(industry_stocks)} 檔股票')

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

        # 顯示股票列表（可點擊展開詳情）
        st.markdown('**點擊股票查看詳細分析：**')

        # 表頭
        header_cols = st.columns([1, 2, 1.5, 1.5, 1.5])
        header_cols[0].markdown('**代號**')
        header_cols[1].markdown('**名稱**')
        header_cols[2].markdown('**報酬率**')
        header_cols[3].markdown('**股價**')
        header_cols[4].markdown('**操作**')

        st.markdown('<hr style="margin: 5px 0;">', unsafe_allow_html=True)

        # 顯示股票列表
        for idx, row in stock_df.iterrows():
            cols = st.columns([1, 2, 1.5, 1.5, 1.5])
            cols[0].write(row['代號'])
            cols[1].write(row['名稱'])

            # 報酬率顏色
            ret_val = row['報酬率_raw']
            if ret_val > 0:
                cols[2].markdown(f'<span style="color: #4caf50;">{ret_val * 100:+.2f}%</span>', unsafe_allow_html=True)
            elif ret_val < 0:
                cols[2].markdown(f'<span style="color: #f44336;">{ret_val * 100:+.2f}%</span>', unsafe_allow_html=True)
            else:
                cols[2].write(f'{ret_val * 100:.2f}%')

            cols[3].write(f'{row["最新股價_raw"]:.2f}')

            # 展開詳情按鈕
            if cols[4].button('📊 詳情', key=f'detail_{row["代號"]}'):
                st.session_state.selected_stock_detail = row['代號']

        # 顯示選中股票的詳細分析
        if 'selected_stock_detail' in st.session_state and st.session_state.selected_stock_detail:
            detail_stock_id = st.session_state.selected_stock_detail

            # 確認是該產業的股票
            if detail_stock_id in [r['代號'] for r in stock_returns]:
                st.markdown('---')

                # 關閉按鈕
                close_col1, close_col2 = st.columns([4, 1])
                with close_col2:
                    if st.button('❌ 關閉', key='close_detail'):
                        del st.session_state.selected_stock_detail
                        st.rerun()

                # 取得股票資訊
                detail_info = stock_info[stock_info['stock_id'] == detail_stock_id]
                detail_name = detail_info['name'].values[0] if len(detail_info) > 0 else ''

                st.markdown(f'### 📈 {detail_stock_id} {detail_name} 詳細分析')

                # 取得完整數據
                detail_close = close[detail_stock_id].dropna()

                if len(detail_close) > 0:
                    # 基本資訊
                    info_col1, info_col2, info_col3, info_col4 = st.columns(4)

                    latest_price = detail_close.iloc[-1]
                    prev_price = detail_close.iloc[-2] if len(detail_close) > 1 else latest_price
                    day_change = (latest_price / prev_price - 1) * 100

                    with info_col1:
                        st.metric('最新股價', f'{latest_price:.2f}', f'{day_change:+.2f}%')

                    with info_col2:
                        # 計算期間報酬
                        period_close = detail_close.tail(period_days)
                        if len(period_close) > 1:
                            period_ret = (period_close.iloc[-1] / period_close.iloc[0] - 1) * 100
                            st.metric(f'{period} 報酬', f'{period_ret:+.2f}%')
                        else:
                            st.metric(f'{period} 報酬', '-')

                    with info_col3:
                        # 近一年報酬
                        if len(detail_close) >= 252:
                            year_ret = (detail_close.iloc[-1] / detail_close.iloc[-252] - 1) * 100
                            st.metric('近一年報酬', f'{year_ret:+.2f}%')
                        else:
                            st.metric('近一年報酬', '-')

                    with info_col4:
                        # 波動率
                        returns = detail_close.pct_change().dropna()
                        if len(returns) > 20:
                            vol = returns.std() * np.sqrt(252) * 100
                            st.metric('年化波動率', f'{vol:.1f}%')
                        else:
                            st.metric('年化波動率', '-')

                    # 走勢圖
                    chart_col1, chart_col2 = st.columns(2)

                    with chart_col1:
                        st.markdown(f'**📈 {period} 走勢**')

                        import plotly.graph_objects as go

                        period_data = detail_close.tail(period_days)

                        fig_price = go.Figure()
                        fig_price.add_trace(go.Scatter(
                            x=period_data.index,
                            y=period_data.values,
                            mode='lines',
                            name='股價',
                            line=dict(color='#2196F3', width=2),
                            fill='tozeroy',
                            fillcolor='rgba(33, 150, 243, 0.1)',
                        ))

                        # 加入均線
                        if len(period_data) >= 20:
                            ma20 = period_data.rolling(20).mean()
                            fig_price.add_trace(go.Scatter(
                                x=ma20.index,
                                y=ma20.values,
                                mode='lines',
                                name='MA20',
                                line=dict(color='orange', width=1, dash='dash'),
                            ))

                        fig_price.update_layout(
                            height=300,
                            margin=dict(l=0, r=0, t=0, b=0),
                            xaxis_title='',
                            yaxis_title='股價',
                            showlegend=True,
                            legend=dict(orientation='h', yanchor='bottom', y=1.02),
                        )

                        st.plotly_chart(fig_price, use_container_width=True)

                    with chart_col2:
                        st.markdown('**📊 成交量**')

                        if detail_stock_id in volume.columns:
                            vol_data = volume[detail_stock_id].dropna().tail(period_days)

                            fig_vol = go.Figure()
                            fig_vol.add_trace(go.Bar(
                                x=vol_data.index,
                                y=vol_data.values / 1000,  # 以千股顯示
                                name='成交量',
                                marker_color='rgba(76, 175, 80, 0.6)',
                            ))

                            fig_vol.update_layout(
                                height=300,
                                margin=dict(l=0, r=0, t=0, b=0),
                                xaxis_title='',
                                yaxis_title='成交量 (千股)',
                            )

                            st.plotly_chart(fig_vol, use_container_width=True)
                        else:
                            st.info('無成交量數據')

                    # 技術指標分析
                    st.markdown('**🔍 技術指標**')

                    from core.indicators import rsi, macd

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
                                st.success(f'站上 MA20')
                            else:
                                st.warning(f'跌破 MA20')
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

                    # 與大盤比較
                    st.markdown('**📊 與大盤比較**')

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
                        line=dict(color='#2196F3', width=2),
                    ))

                    fig_compare.add_trace(go.Scatter(
                        x=benchmark_normalized.index,
                        y=benchmark_normalized.values,
                        name='大盤指數',
                        line=dict(color='gray', width=1, dash='dash'),
                    ))

                    fig_compare.update_layout(
                        height=300,
                        xaxis_title='',
                        yaxis_title='相對表現 (初始=100)',
                        legend=dict(orientation='h', yanchor='bottom', y=1.02),
                    )

                    compare_col1, compare_col2 = st.columns([3, 1])

                    with compare_col1:
                        st.plotly_chart(fig_compare, use_container_width=True)

                    with compare_col2:
                        st.metric('個股報酬', f'{stock_return * 100:+.2f}%')
                        st.metric('大盤報酬', f'{benchmark_return * 100:+.2f}%')

                        alpha = stock_return - benchmark_return
                        if alpha > 0:
                            st.success(f'Alpha: +{alpha * 100:.2f}%')
                        else:
                            st.error(f'Alpha: {alpha * 100:.2f}%')

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
