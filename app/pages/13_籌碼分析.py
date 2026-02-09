"""
籌碼分析頁面 - 融資融券、法人買賣超分析
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error, safe_execute, create_error_boundary
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state

st.set_page_config(page_title='籌碼分析', page_icon='💰', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='margin')

render_page_header('籌碼分析', icon='🏦')

# 載入數據
@st.cache_data(ttl=CACHE_TTL['daily'])
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'volume': loader.get('volume'),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
    close = data['close']
    volume = data['volume']
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
tab1, tab2, tab3, tab4 = st.tabs(['🔍 個股籌碼', '📊 籌碼指標', '🏆 籌碼排行', '📈 策略選股'])

# ========== 個股籌碼分析 ==========
with tab1:
    st.markdown('### 個股籌碼分析')

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_stock = st.selectbox(
            '選擇股票',
            stock_options,
            index=0 if stock_options else None
        )

    with col2:
        analysis_days = st.selectbox(
            '分析天數',
            [20, 40, 60, 120, 252],
            index=2
        )

    if selected_stock:
        stock_id = selected_stock.split(' ')[0]
        stock_name = selected_stock.split(' ')[1] if len(selected_stock.split(' ')) > 1 else ''

        if stock_id in close.columns:
            stock_close = close[stock_id].dropna().tail(analysis_days)
            stock_volume = volume[stock_id].dropna().tail(analysis_days) if stock_id in volume.columns else None

            # 價量分析
            st.markdown(f'#### {stock_id} {stock_name} 價量分析')

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                current_price = stock_close.iloc[-1]
                price_change = (stock_close.iloc[-1] / stock_close.iloc[0] - 1) * 100
                st.metric(
                    '收盤價',
                    f'{current_price:.2f}',
                    f'{price_change:+.2f}%'
                )

            with col2:
                if stock_volume is not None and len(stock_volume) > 0:
                    avg_volume = stock_volume.mean() / 1000  # 轉換為張
                    st.metric('平均成交量', f'{avg_volume:,.0f} 張')
                else:
                    st.metric('平均成交量', 'N/A')

            with col3:
                volatility = stock_close.pct_change().std() * np.sqrt(252) * 100
                st.metric('年化波動率', f'{volatility:.1f}%')

            with col4:
                # 計算 RSI
                delta = stock_close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 0
                st.metric('RSI(14)', f'{current_rsi:.1f}')

            # 價格走勢圖
            st.markdown('##### 價格走勢')
            st.line_chart(stock_close)

            # 成交量走勢圖
            if stock_volume is not None and len(stock_volume) > 0:
                st.markdown('##### 成交量走勢')
                volume_df = pd.DataFrame({
                    '成交量(張)': stock_volume / 1000
                })
                st.bar_chart(volume_df)

            # 籌碼指標模擬 (實際需要融資融券數據)
            st.markdown('##### 籌碼指標 (模擬)')
            st.info('實際籌碼數據需要融資融券、法人買賣超等數據源支援')

            # 模擬籌碼指標
            np.random.seed(int(stock_id) if stock_id.isdigit() else 42)

            col1, col2, col3 = st.columns(3)

            with col1:
                margin_ratio = np.random.uniform(5, 25)
                margin_change = np.random.uniform(-2, 2)
                st.metric(
                    '融資使用率',
                    f'{margin_ratio:.1f}%',
                    f'{margin_change:+.2f}%'
                )

            with col2:
                short_ratio = np.random.uniform(1, 10)
                short_change = np.random.uniform(-1, 1)
                st.metric(
                    '融券餘額率',
                    f'{short_ratio:.1f}%',
                    f'{short_change:+.2f}%'
                )

            with col3:
                margin_short_ratio = margin_ratio / short_ratio if short_ratio > 0 else 0
                st.metric(
                    '券資比',
                    f'{margin_short_ratio:.2f}'
                )

            # 法人買賣超模擬
            st.markdown('##### 法人買賣超 (模擬)')

            institutional_data = pd.DataFrame({
                '日期': pd.date_range(end=datetime.now(), periods=10, freq='B'),
                '外資': np.random.randint(-5000, 5000, 10),
                '投信': np.random.randint(-1000, 1000, 10),
                '自營商': np.random.randint(-2000, 2000, 10),
            })
            institutional_data['合計'] = institutional_data['外資'] + institutional_data['投信'] + institutional_data['自營商']
            institutional_data = institutional_data.set_index('日期')

            st.dataframe(institutional_data, use_container_width=True)

            # 法人買賣超走勢
            st.bar_chart(institutional_data[['外資', '投信', '自營商']])

        else:
            st.warning(f'找不到股票 {stock_id} 的數據')

# ========== 籌碼指標 ==========
with tab2:
    st.markdown('### 籌碼指標說明')

    st.markdown('''
    #### 融資融券指標

    | 指標 | 說明 | 多頭訊號 | 空頭訊號 |
    |------|------|----------|----------|
    | 融資餘額 | 投資人借錢買股票的金額 | 減少 | 增加 |
    | 融券餘額 | 投資人借股票賣出的數量 | 增加 | 減少 |
    | 券資比 | 融券/融資 | > 30% | < 10% |
    | 融資使用率 | 融資餘額/融資限額 | < 20% | > 40% |

    #### 法人買賣超指標

    | 法人 | 特性 | 參考價值 |
    |------|------|----------|
    | 外資 | 資金充沛，中長期布局 | 高 |
    | 投信 | 追蹤績效，波段操作 | 中 |
    | 自營商 | 短線交易，避險為主 | 低 |

    #### 籌碼分析原則

    1. **量價配合**: 上漲放量、下跌縮量為健康型態
    2. **主力動向**: 觀察大戶與散戶籌碼變化
    3. **融資減碼**: 融資大減通常是築底訊號
    4. **法人連買**: 三大法人連續買超為正向訊號
    ''')

    # 籌碼指標計算器
    st.markdown('---')
    st.markdown('#### 籌碼指標計算器')

    col1, col2 = st.columns(2)

    with col1:
        margin_balance = st.number_input('融資餘額 (張)', 0, 1000000, 10000)
        margin_limit = st.number_input('融資限額 (張)', 0, 1000000, 50000)

    with col2:
        short_balance = st.number_input('融券餘額 (張)', 0, 1000000, 2000)
        volume_input = st.number_input('今日成交量 (張)', 0, 10000000, 5000)

    if margin_limit > 0:
        usage_rate = margin_balance / margin_limit * 100
        st.markdown(f'**融資使用率**: {usage_rate:.2f}%')

    if margin_balance > 0:
        ratio = short_balance / margin_balance * 100
        st.markdown(f'**券資比**: {ratio:.2f}%')

# ========== 籌碼排行 ==========
with tab3:
    st.markdown('### 籌碼排行榜')

    ranking_type = st.selectbox(
        '排行類型',
        ['成交量排行', '漲幅排行', '跌幅排行', '波動率排行', '量能變化排行']
    )

    ranking_days = st.selectbox(
        '統計天數',
        [1, 5, 20, 60],
        index=1
    )

    if st.button('計算排行', type='primary'):
        with st.spinner('計算中...'):
            try:
                # 取得最近數據
                recent_close = close[active_stocks].tail(ranking_days + 1)
                recent_volume = volume[active_stocks].tail(ranking_days)

                results = []

                for stock_id in active_stocks:
                    if stock_id not in recent_close.columns:
                        continue

                    stock_data = recent_close[stock_id].dropna()
                    if len(stock_data) < 2:
                        continue

                    # 計算指標
                    price_change = (stock_data.iloc[-1] / stock_data.iloc[0] - 1) * 100
                    volatility = stock_data.pct_change().std() * 100

                    # 成交量
                    if stock_id in recent_volume.columns:
                        vol_data = recent_volume[stock_id].dropna()
                        avg_volume = vol_data.mean() / 1000 if len(vol_data) > 0 else 0
                        # 量能變化 (最近5日 vs 前5日)
                        if len(vol_data) >= 10:
                            recent_vol = vol_data.tail(5).mean()
                            prev_vol = vol_data.head(5).mean()
                            vol_change = (recent_vol / prev_vol - 1) * 100 if prev_vol > 0 else 0
                        else:
                            vol_change = 0
                    else:
                        avg_volume = 0
                        vol_change = 0

                    # 股票名稱
                    info = stock_info[stock_info['stock_id'] == stock_id]
                    name = info['name'].values[0] if len(info) > 0 else ''

                    results.append({
                        '股票代碼': stock_id,
                        '股票名稱': name,
                        '收盤價': stock_data.iloc[-1],
                        '漲跌幅(%)': price_change,
                        '波動率(%)': volatility,
                        '平均成交量(張)': avg_volume,
                        '量能變化(%)': vol_change,
                    })

                df = pd.DataFrame(results)
            except Exception as e:
                show_error(e, title='計算排行失敗', suggestion='請檢查資料是否完整')
                df = pd.DataFrame()

            if len(df) > 0:
                # 根據排行類型排序
                if ranking_type == '成交量排行':
                    df = df.sort_values('平均成交量(張)', ascending=False)
                elif ranking_type == '漲幅排行':
                    df = df.sort_values('漲跌幅(%)', ascending=False)
                elif ranking_type == '跌幅排行':
                    df = df.sort_values('漲跌幅(%)', ascending=True)
                elif ranking_type == '波動率排行':
                    df = df.sort_values('波動率(%)', ascending=False)
                elif ranking_type == '量能變化排行':
                    df = df.sort_values('量能變化(%)', ascending=False)

                # 顯示前 30 名
                st.dataframe(
                    df.head(30).style.format({
                        '收盤價': '{:.2f}',
                        '漲跌幅(%)': '{:+.2f}',
                        '波動率(%)': '{:.2f}',
                        '平均成交量(張)': '{:,.0f}',
                        '量能變化(%)': '{:+.2f}',
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning('沒有符合條件的數據')

# ========== 策略選股 ==========
with tab4:
    st.markdown('### 籌碼策略選股')

    st.markdown('''
    基於籌碼指標的選股策略：

    1. **量增價漲**: 成交量放大且價格上漲
    2. **量縮價穩**: 成交量萎縮但價格持穩
    3. **突破均量**: 成交量突破近期均量
    ''')

    strategy = st.selectbox(
        '選擇策略',
        ['量增價漲', '量縮價穩', '突破均量', '爆量長紅']
    )

    col1, col2 = st.columns(2)

    with col1:
        lookback = st.number_input('回看天數', 5, 60, 20)

    with col2:
        volume_threshold = st.number_input('量能倍數', 1.0, 5.0, 1.5)

    if st.button('執行選股', type='primary', key='margin_screening'):
        with st.spinner('選股中...'):
            try:
                selected_stocks = []

                for stock_id in active_stocks:
                    if stock_id not in close.columns or stock_id not in volume.columns:
                        continue

                    stock_close = close[stock_id].dropna().tail(lookback + 1)
                    stock_volume = volume[stock_id].dropna().tail(lookback + 1)

                    if len(stock_close) < lookback or len(stock_volume) < lookback:
                        continue

                    # 計算指標
                    price_change = (stock_close.iloc[-1] / stock_close.iloc[-2] - 1) * 100
                    period_change = (stock_close.iloc[-1] / stock_close.iloc[0] - 1) * 100
                    avg_volume = stock_volume.iloc[:-1].mean()
                    today_volume = stock_volume.iloc[-1]
                    volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0

                    # 策略判斷
                    selected = False

                    if strategy == '量增價漲':
                        # 今日上漲且量能放大
                        selected = price_change > 0 and volume_ratio > volume_threshold

                    elif strategy == '量縮價穩':
                        # 價格波動小且量能萎縮
                        volatility = stock_close.pct_change().std()
                        selected = abs(price_change) < 1 and volume_ratio < 0.7 and volatility < 0.02

                    elif strategy == '突破均量':
                        # 成交量突破均量
                        selected = volume_ratio > volume_threshold

                    elif strategy == '爆量長紅':
                        # 大漲且爆量
                        selected = price_change > 3 and volume_ratio > 2

                    if selected:
                        info = stock_info[stock_info['stock_id'] == stock_id]
                        name = info['name'].values[0] if len(info) > 0 else ''

                        selected_stocks.append({
                            '股票代碼': stock_id,
                            '股票名稱': name,
                            '收盤價': stock_close.iloc[-1],
                            '今日漲跌(%)': price_change,
                            '區間漲跌(%)': period_change,
                            '量能倍數': volume_ratio,
                        })
            except Exception as e:
                show_error(e, title='選股執行失敗', suggestion='請檢查選股條件或資料是否完整')
                selected_stocks = []

            if selected_stocks:
                df = pd.DataFrame(selected_stocks)
                df = df.sort_values('量能倍數', ascending=False)

                st.success(f'找到 {len(df)} 檔符合條件的股票')

                st.dataframe(
                    df.style.format({
                        '收盤價': '{:.2f}',
                        '今日漲跌(%)': '{:+.2f}',
                        '區間漲跌(%)': '{:+.2f}',
                        '量能倍數': '{:.2f}',
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                show_empty_state('沒有符合條件的股票', icon='🔍', suggestion='請嘗試調整篩選條件')

# ========== 說明 ==========
with st.expander('📖 籌碼分析說明'):
    st.markdown('''
    ### 籌碼分析的重要性

    籌碼分析是技術分析的重要組成部分，透過觀察市場參與者的行為來預測價格走勢。

    ### 主要觀察指標

    1. **融資融券**
       - 融資增加：散戶看多
       - 融券增加：市場看空
       - 券資比上升：軋空機會

    2. **法人買賣超**
       - 外資：國際資金動向
       - 投信：國內基金動向
       - 自營商：短線交易參考

    3. **量能分析**
       - 量價配合是趨勢延續的重要指標
       - 量能萎縮可能是變盤前兆

    ### 注意事項

    - 籌碼分析需要配合其他分析方法
    - 單一指標可能產生誤導
    - 建議結合基本面和技術面分析
    ''')
