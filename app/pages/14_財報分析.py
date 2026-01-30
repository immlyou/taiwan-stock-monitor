"""
財報分析頁面 - 基本面分析工具
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error, safe_execute, create_error_boundary

st.set_page_config(page_title='財報分析', page_icon='📑', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='financial')

st.title('📑 財報分析')
st.markdown('基本面數據分析與估值計算')
st.markdown('---')

# 載入數據
@st.cache_data(ttl=3600)
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'pe_ratio': loader.get('pe_ratio'),
        'pb_ratio': loader.get('pb_ratio'),
        'dividend_yield': loader.get('dividend_yield'),
        'monthly_revenue': loader.get('monthly_revenue'),
        'revenue_yoy': loader.get('revenue_yoy'),
        'revenue_mom': loader.get('revenue_mom'),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
    close = data['close']
    pe_ratio = data['pe_ratio']
    pb_ratio = data['pb_ratio']
    dividend_yield = data['dividend_yield']
    monthly_revenue = data['monthly_revenue']
    revenue_yoy = data['revenue_yoy']
    revenue_mom = data['revenue_mom']
    stock_info = data['stock_info']
    active_stocks = get_active_stocks()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

# 股票選擇
stock_options = [f"{row['stock_id']} {row['name']}"
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks]

# Tab 選擇
tab1, tab2, tab3, tab4 = st.tabs(['🔍 個股分析', '📊 估值比較', '📈 營收分析', '🎯 價值選股'])

# ========== 個股分析 ==========
with tab1:
    st.markdown('### 個股基本面分析')

    selected_stock = st.selectbox(
        '選擇股票',
        stock_options,
        index=0 if stock_options else None,
        key='financial_stock_select'
    )

    if selected_stock:
        stock_id = selected_stock.split(' ')[0]
        stock_name = selected_stock.split(' ')[1] if len(selected_stock.split(' ')) > 1 else ''

        st.markdown(f'#### {stock_id} {stock_name}')

        # 估值指標
        st.markdown('##### 估值指標')

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if pe_ratio is not None and stock_id in pe_ratio.columns:
                current_pe = pe_ratio[stock_id].dropna().iloc[-1] if len(pe_ratio[stock_id].dropna()) > 0 else None
                if current_pe is not None:
                    st.metric('本益比 (P/E)', f'{current_pe:.2f}')
                else:
                    st.metric('本益比 (P/E)', 'N/A')
            else:
                st.metric('本益比 (P/E)', 'N/A')

        with col2:
            if pb_ratio is not None and stock_id in pb_ratio.columns:
                current_pb = pb_ratio[stock_id].dropna().iloc[-1] if len(pb_ratio[stock_id].dropna()) > 0 else None
                if current_pb is not None:
                    st.metric('股價淨值比 (P/B)', f'{current_pb:.2f}')
                else:
                    st.metric('股價淨值比 (P/B)', 'N/A')
            else:
                st.metric('股價淨值比 (P/B)', 'N/A')

        with col3:
            if dividend_yield is not None and stock_id in dividend_yield.columns:
                current_yield = dividend_yield[stock_id].dropna().iloc[-1] if len(dividend_yield[stock_id].dropna()) > 0 else None
                if current_yield is not None:
                    st.metric('殖利率', f'{current_yield:.2f}%')
                else:
                    st.metric('殖利率', 'N/A')
            else:
                st.metric('殖利率', 'N/A')

        with col4:
            if close is not None and stock_id in close.columns:
                current_price = close[stock_id].dropna().iloc[-1] if len(close[stock_id].dropna()) > 0 else None
                if current_price is not None:
                    st.metric('收盤價', f'{current_price:.2f}')
                else:
                    st.metric('收盤價', 'N/A')
            else:
                st.metric('收盤價', 'N/A')

        # 估值歷史走勢
        st.markdown('##### 估值歷史走勢')

        col1, col2 = st.columns(2)

        with col1:
            if pe_ratio is not None and stock_id in pe_ratio.columns:
                pe_data = pe_ratio[stock_id].dropna().tail(252)
                if len(pe_data) > 0:
                    st.markdown('**本益比走勢**')
                    st.line_chart(pe_data)

                    # 本益比統計
                    pe_mean = pe_data.mean()
                    pe_std = pe_data.std()
                    pe_current = pe_data.iloc[-1]

                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric('平均', f'{pe_mean:.2f}')
                    col_b.metric('標準差', f'{pe_std:.2f}')

                    # 判斷目前位置
                    if pe_current < pe_mean - pe_std:
                        position = '偏低'
                    elif pe_current > pe_mean + pe_std:
                        position = '偏高'
                    else:
                        position = '合理'
                    col_c.metric('目前位置', position)

        with col2:
            if pb_ratio is not None and stock_id in pb_ratio.columns:
                pb_data = pb_ratio[stock_id].dropna().tail(252)
                if len(pb_data) > 0:
                    st.markdown('**股價淨值比走勢**')
                    st.line_chart(pb_data)

                    # 股價淨值比統計
                    pb_mean = pb_data.mean()
                    pb_std = pb_data.std()
                    pb_current = pb_data.iloc[-1]

                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric('平均', f'{pb_mean:.2f}')
                    col_b.metric('標準差', f'{pb_std:.2f}')

                    if pb_current < pb_mean - pb_std:
                        position = '偏低'
                    elif pb_current > pb_mean + pb_std:
                        position = '偏高'
                    else:
                        position = '合理'
                    col_c.metric('目前位置', position)

        # 月營收分析
        st.markdown('##### 月營收分析')

        if monthly_revenue is not None and stock_id in monthly_revenue.columns:
            rev_data = monthly_revenue[stock_id].dropna().tail(24)

            if len(rev_data) > 0:
                st.markdown('**月營收走勢 (近24個月)**')

                # 轉換為億元
                rev_chart = pd.DataFrame({
                    '營收(億)': rev_data / 100000000
                })
                st.bar_chart(rev_chart)

                # 營收統計
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    latest_rev = rev_data.iloc[-1] / 100000000
                    st.metric('最新月營收', f'{latest_rev:.2f} 億')

                with col2:
                    if revenue_yoy is not None and stock_id in revenue_yoy.columns:
                        yoy = revenue_yoy[stock_id].dropna().iloc[-1] if len(revenue_yoy[stock_id].dropna()) > 0 else None
                        if yoy is not None:
                            st.metric('年增率 (YoY)', f'{yoy:+.2f}%')
                        else:
                            st.metric('年增率 (YoY)', 'N/A')
                    else:
                        st.metric('年增率 (YoY)', 'N/A')

                with col3:
                    if revenue_mom is not None and stock_id in revenue_mom.columns:
                        mom = revenue_mom[stock_id].dropna().iloc[-1] if len(revenue_mom[stock_id].dropna()) > 0 else None
                        if mom is not None:
                            st.metric('月增率 (MoM)', f'{mom:+.2f}%')
                        else:
                            st.metric('月增率 (MoM)', 'N/A')
                    else:
                        st.metric('月增率 (MoM)', 'N/A')

                with col4:
                    # 累計年營收
                    current_year = datetime.now().year
                    ytd_rev = rev_data[rev_data.index.year == current_year].sum() / 100000000
                    st.metric('本年累計營收', f'{ytd_rev:.2f} 億')

# ========== 估值比較 ==========
with tab2:
    st.markdown('### 估值比較分析')

    st.markdown('選擇多檔股票進行估值比較')

    compare_stocks = st.multiselect(
        '選擇比較股票 (最多 10 檔)',
        stock_options,
        max_selections=10
    )

    if compare_stocks:
        compare_ids = [s.split(' ')[0] for s in compare_stocks]

        # 收集估值數據
        valuation_data = []

        for stock_id in compare_ids:
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''

            row = {
                '股票代碼': stock_id,
                '股票名稱': name,
            }

            # 收盤價
            if close is not None and stock_id in close.columns:
                row['收盤價'] = close[stock_id].dropna().iloc[-1] if len(close[stock_id].dropna()) > 0 else None

            # 本益比
            if pe_ratio is not None and stock_id in pe_ratio.columns:
                row['本益比'] = pe_ratio[stock_id].dropna().iloc[-1] if len(pe_ratio[stock_id].dropna()) > 0 else None

            # 股價淨值比
            if pb_ratio is not None and stock_id in pb_ratio.columns:
                row['股價淨值比'] = pb_ratio[stock_id].dropna().iloc[-1] if len(pb_ratio[stock_id].dropna()) > 0 else None

            # 殖利率
            if dividend_yield is not None and stock_id in dividend_yield.columns:
                row['殖利率(%)'] = dividend_yield[stock_id].dropna().iloc[-1] if len(dividend_yield[stock_id].dropna()) > 0 else None

            # 營收年增率
            if revenue_yoy is not None and stock_id in revenue_yoy.columns:
                row['營收YoY(%)'] = revenue_yoy[stock_id].dropna().iloc[-1] if len(revenue_yoy[stock_id].dropna()) > 0 else None

            valuation_data.append(row)

        df = pd.DataFrame(valuation_data)

        st.dataframe(
            df.style.format({
                '收盤價': '{:.2f}',
                '本益比': '{:.2f}',
                '股價淨值比': '{:.2f}',
                '殖利率(%)': '{:.2f}',
                '營收YoY(%)': '{:+.2f}',
            }, na_rep='N/A'),
            use_container_width=True,
            hide_index=True
        )

        # 估值比較圖表
        st.markdown('##### 估值比較圖表')

        col1, col2 = st.columns(2)

        with col1:
            if '本益比' in df.columns:
                pe_chart = df[['股票代碼', '本益比']].dropna()
                if len(pe_chart) > 0:
                    st.markdown('**本益比比較**')
                    st.bar_chart(pe_chart.set_index('股票代碼'))

        with col2:
            if '股價淨值比' in df.columns:
                pb_chart = df[['股票代碼', '股價淨值比']].dropna()
                if len(pb_chart) > 0:
                    st.markdown('**股價淨值比比較**')
                    st.bar_chart(pb_chart.set_index('股票代碼'))

# ========== 營收分析 ==========
with tab3:
    st.markdown('### 營收分析')

    analysis_stock = st.selectbox(
        '選擇股票',
        stock_options,
        index=0 if stock_options else None,
        key='revenue_stock_select'
    )

    if analysis_stock:
        stock_id = analysis_stock.split(' ')[0]
        stock_name = analysis_stock.split(' ')[1] if len(analysis_stock.split(' ')) > 1 else ''

        st.markdown(f'#### {stock_id} {stock_name} 營收分析')

        # 營收數據
        if monthly_revenue is not None and stock_id in monthly_revenue.columns:
            rev_data = monthly_revenue[stock_id].dropna()

            if len(rev_data) > 0:
                # 選擇時間範圍
                period = st.selectbox(
                    '分析期間',
                    ['近12個月', '近24個月', '近36個月', '全部'],
                    index=1
                )

                if period == '近12個月':
                    rev_data = rev_data.tail(12)
                elif period == '近24個月':
                    rev_data = rev_data.tail(24)
                elif period == '近36個月':
                    rev_data = rev_data.tail(36)

                # 營收走勢
                st.markdown('##### 月營收走勢')

                rev_chart = pd.DataFrame({
                    '營收(億)': rev_data / 100000000
                })
                st.bar_chart(rev_chart)

                # 年度比較
                st.markdown('##### 年度營收比較')

                yearly_rev = rev_data.groupby(rev_data.index.year).sum() / 100000000
                yearly_df = pd.DataFrame({
                    '年度': yearly_rev.index,
                    '營收(億)': yearly_rev.values
                }).set_index('年度')

                col1, col2 = st.columns(2)

                with col1:
                    st.bar_chart(yearly_df)

                with col2:
                    # 計算年增率
                    yearly_growth = yearly_rev.pct_change() * 100
                    growth_df = pd.DataFrame({
                        '年度': [str(y) for y in yearly_growth.index],
                        '年增率(%)': yearly_growth.values
                    })
                    st.dataframe(growth_df, hide_index=True, use_container_width=True)

                # 季節性分析
                st.markdown('##### 季節性分析')

                monthly_avg = rev_data.groupby(rev_data.index.month).mean() / 100000000
                monthly_df = pd.DataFrame({
                    '月份': ['1月', '2月', '3月', '4月', '5月', '6月',
                            '7月', '8月', '9月', '10月', '11月', '12月'],
                    '平均營收(億)': [monthly_avg.get(i, 0) for i in range(1, 13)]
                }).set_index('月份')

                st.bar_chart(monthly_df)

                # 營收統計
                st.markdown('##### 營收統計')

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    avg_rev = rev_data.mean() / 100000000
                    st.metric('平均月營收', f'{avg_rev:.2f} 億')

                with col2:
                    max_rev = rev_data.max() / 100000000
                    st.metric('最高月營收', f'{max_rev:.2f} 億')

                with col3:
                    min_rev = rev_data.min() / 100000000
                    st.metric('最低月營收', f'{min_rev:.2f} 億')

                with col4:
                    std_rev = rev_data.std() / 100000000
                    cv = std_rev / avg_rev * 100 if avg_rev > 0 else 0
                    st.metric('變異係數', f'{cv:.1f}%')

# ========== 價值選股 ==========
with tab4:
    st.markdown('### 價值選股')

    st.markdown('根據基本面指標篩選價值股')

    col1, col2 = st.columns(2)

    with col1:
        max_pe = st.number_input('本益比上限', 1.0, 100.0, 15.0)
        max_pb = st.number_input('股價淨值比上限', 0.1, 10.0, 1.5)

    with col2:
        min_yield = st.number_input('殖利率下限 (%)', 0.0, 20.0, 4.0)
        min_yoy = st.number_input('營收年增率下限 (%)', -50.0, 100.0, 0.0)

    if st.button('執行選股', type='primary', key='value_screening'):
        with st.spinner('選股中...'):
            try:
                selected_stocks = []

                for stock_id in active_stocks:
                    # 檢查本益比
                    if pe_ratio is not None and stock_id in pe_ratio.columns:
                        pe = pe_ratio[stock_id].dropna().iloc[-1] if len(pe_ratio[stock_id].dropna()) > 0 else None
                        if pe is None or pe > max_pe or pe <= 0:
                            continue
                    else:
                        continue

                    # 檢查股價淨值比
                    if pb_ratio is not None and stock_id in pb_ratio.columns:
                        pb = pb_ratio[stock_id].dropna().iloc[-1] if len(pb_ratio[stock_id].dropna()) > 0 else None
                        if pb is None or pb > max_pb or pb <= 0:
                            continue
                    else:
                        continue

                    # 檢查殖利率
                    if dividend_yield is not None and stock_id in dividend_yield.columns:
                        dy = dividend_yield[stock_id].dropna().iloc[-1] if len(dividend_yield[stock_id].dropna()) > 0 else None
                        if dy is None or dy < min_yield:
                            continue
                    else:
                        continue

                    # 檢查營收年增率
                    if revenue_yoy is not None and stock_id in revenue_yoy.columns:
                        yoy = revenue_yoy[stock_id].dropna().iloc[-1] if len(revenue_yoy[stock_id].dropna()) > 0 else None
                        if yoy is None or yoy < min_yoy:
                            continue
                    else:
                        yoy = None

                    # 收盤價
                    price = None
                    if close is not None and stock_id in close.columns:
                        price = close[stock_id].dropna().iloc[-1] if len(close[stock_id].dropna()) > 0 else None

                    # 股票名稱
                    info = stock_info[stock_info['stock_id'] == stock_id]
                    name = info['name'].values[0] if len(info) > 0 else ''

                    selected_stocks.append({
                        '股票代碼': stock_id,
                        '股票名稱': name,
                        '收盤價': price,
                        '本益比': pe,
                        '股價淨值比': pb,
                        '殖利率(%)': dy,
                        '營收YoY(%)': yoy,
                    })
            except Exception as e:
                show_error(e, title='價值選股失敗', suggestion='請檢查篩選條件或資料是否完整')
                selected_stocks = []

            if selected_stocks:
                df = pd.DataFrame(selected_stocks)

                # 計算價值評分
                df['價值評分'] = (
                    (1 - df['本益比'] / max_pe) * 30 +
                    (1 - df['股價淨值比'] / max_pb) * 30 +
                    (df['殖利率(%)'] / 10) * 40
                ).clip(0, 100)

                df = df.sort_values('價值評分', ascending=False)

                st.success(f'找到 {len(df)} 檔價值股')

                st.dataframe(
                    df.style.format({
                        '收盤價': '{:.2f}',
                        '本益比': '{:.2f}',
                        '股價淨值比': '{:.2f}',
                        '殖利率(%)': '{:.2f}',
                        '營收YoY(%)': '{:+.2f}',
                        '價值評分': '{:.1f}',
                    }, na_rep='N/A'),
                    use_container_width=True,
                    hide_index=True
                )

                # 匯出按鈕
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    '📥 下載選股結果',
                    csv,
                    f'value_stocks_{datetime.now().strftime("%Y%m%d")}.csv',
                    'text/csv',
                )
            else:
                st.info('沒有符合條件的股票')

# ========== 說明 ==========
with st.expander('📖 財報分析說明'):
    st.markdown('''
    ### 估值指標說明

    #### 本益比 (P/E Ratio)
    - 公式: 股價 / 每股盈餘
    - 意義: 投資人願意為每元盈餘支付的價格
    - 一般標準: 10-20 倍為合理區間

    #### 股價淨值比 (P/B Ratio)
    - 公式: 股價 / 每股淨值
    - 意義: 股價相對於公司帳面價值的倍數
    - 一般標準: < 1 可能被低估

    #### 殖利率
    - 公式: 每股股利 / 股價
    - 意義: 投資報酬率的參考
    - 一般標準: > 4% 為高殖利率

    ### 營收分析重點

    1. **年增率 (YoY)**: 與去年同期比較，反映成長動能
    2. **月增率 (MoM)**: 與上月比較，反映短期變化
    3. **季節性**: 某些產業有明顯淡旺季

    ### 價值投資注意事項

    - 低本益比不代表一定被低估
    - 需考慮產業特性和成長性
    - 建議結合多項指標綜合判斷
    ''')
