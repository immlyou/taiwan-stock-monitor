"""
選股篩選頁面
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from core.strategies import ValueStrategy, GrowthStrategy, MomentumStrategy, CompositeStrategy
from config import STRATEGY_PRESETS
from app.components.sidebar import render_sidebar_mini
from app.components.portfolio_utils import load_portfolios, get_portfolio_names, add_holdings_batch
from app.components.error_handler import show_error, safe_execute, create_error_boundary
from app.components.session_manager import (
    init_session_state, get_state, set_state, StateKeys
)
from datetime import datetime
import json

st.set_page_config(page_title='選股篩選', page_icon='🔍', layout='wide')

# 初始化 Session State
init_session_state()

# 渲染側邊欄
render_sidebar_mini(current_page='screening')

st.title('🔍 選股篩選')

# 顯示資料日期
def get_latest_date():
    loader = get_loader()
    return loader.get('close').index.max().strftime('%Y-%m-%d')

latest_date = safe_execute(
    get_latest_date,
    default_return='載入中...',
    error_title='載入資料日期失敗',
    show_error_ui=False
)
st.caption(f'📅 資料更新至: {latest_date}')

st.markdown('---')

# ========== 策略選擇區 ==========
st.subheader('1️⃣ 選擇策略')

strategy_cols = st.columns(4)

strategy_options = {
    '價值投資': {'icon': '💎', 'desc': '尋找被低估的好公司', 'color': 'blue'},
    '成長投資': {'icon': '🚀', 'desc': '尋找高速成長的公司', 'color': 'green'},
    '動能投資': {'icon': '📈', 'desc': '追蹤價量動能強勁股', 'color': 'orange'},
    '綜合策略': {'icon': '🎯', 'desc': '多因子綜合評分選股', 'color': 'purple'},
}

# 檢查是否有從參數優化頁面傳來的參數
applied = get_state(StateKeys.APPLY_OPTIMIZED_PARAMS)
if applied:
    set_state(StateKeys.APPLY_OPTIMIZED_PARAMS, None)  # 清除已處理的參數
    strategy_type_map = {'value': '價值投資', 'growth': '成長投資', 'momentum': '動能投資'}
    set_state(StateKeys.SELECTED_STRATEGY, strategy_type_map.get(applied['strategy_type'], '價值投資'))
    set_state(StateKeys.OPTIMIZED_PARAMS, applied['params'])
    st.success(f"已套用優化參數：{applied['params']}")

for i, (name, info) in enumerate(strategy_options.items()):
    with strategy_cols[i]:
        current_strategy = get_state(StateKeys.SELECTED_STRATEGY)
        if st.button(
            f"{info['icon']} {name}",
            use_container_width=True,
            type='primary' if current_strategy == name else 'secondary'
        ):
            set_state(StateKeys.SELECTED_STRATEGY, name)
            st.rerun()
        st.caption(info['desc'])

strategy_type = get_state(StateKeys.SELECTED_STRATEGY)

st.markdown('---')

# ========== 參數設定區 ==========
st.subheader('2️⃣ 參數設定')

# 預設組合選擇
preset_col, custom_col = st.columns([1, 3])

with preset_col:
    st.markdown('**快速選擇**')
    preset_type = st.radio(
        '風險偏好',
        ['保守型', '標準型', '積極型'],
        index=1,
        horizontal=False,
        help='選擇預設參數組合'
    )

    preset_map = {'保守型': 'conservative', '標準型': 'standard', '積極型': 'aggressive'}

with custom_col:
    st.markdown('**自訂參數**')

    params = {}

    if strategy_type == '價值投資':
        # 載入預設值
        preset_key = preset_map[preset_type]
        defaults = STRATEGY_PRESETS.get('value', {}).get(preset_key, {}).get('params', {})

        col1, col2, col3 = st.columns(3)
        with col1:
            params['pe_max'] = st.slider(
                '本益比上限',
                1.0, 50.0,
                defaults.get('pe_max', 15.0),
                0.5,
                help='PE 越低代表股價相對盈餘越便宜'
            )
            params['use_pe'] = st.checkbox('使用本益比', value=defaults.get('use_pe', True))

        with col2:
            params['pb_max'] = st.slider(
                '股價淨值比上限',
                0.1, 5.0,
                defaults.get('pb_max', 1.5),
                0.1,
                help='PB < 1 表示股價低於帳面價值'
            )
            params['use_pb'] = st.checkbox('使用股價淨值比', value=defaults.get('use_pb', True))

        with col3:
            params['dividend_yield_min'] = st.slider(
                '殖利率下限 (%)',
                0.0, 15.0,
                defaults.get('dividend_yield_min', 4.0),
                0.5,
                help='殖利率越高，股息回報越好'
            )
            params['use_dividend'] = st.checkbox('使用殖利率', value=defaults.get('use_dividend', True))

    elif strategy_type == '成長投資':
        preset_key = preset_map[preset_type]
        defaults = STRATEGY_PRESETS.get('growth', {}).get(preset_key, {}).get('params', {})

        col1, col2, col3 = st.columns(3)
        with col1:
            params['revenue_yoy_min'] = st.slider(
                '營收年增率下限 (%)',
                -50.0, 200.0,
                defaults.get('revenue_yoy_min', 20.0),
                5.0,
                help='與去年同期相比的成長率'
            )
            params['use_yoy'] = st.checkbox('使用年增率', value=defaults.get('use_yoy', True))

        with col2:
            params['revenue_mom_min'] = st.slider(
                '營收月增率下限 (%)',
                -50.0, 100.0,
                defaults.get('revenue_mom_min', 10.0),
                5.0,
                help='與上個月相比的成長率'
            )
            params['use_mom'] = st.checkbox('使用月增率', value=defaults.get('use_mom', True))

        with col3:
            params['consecutive_months'] = st.slider(
                '連續成長月數',
                1, 12,
                defaults.get('consecutive_months', 3),
                1,
                help='確認成長趨勢的持續性'
            )
            params['use_consecutive'] = st.checkbox('使用連續成長', value=True)

    elif strategy_type == '動能投資':
        preset_key = preset_map[preset_type]
        defaults = STRATEGY_PRESETS.get('momentum', {}).get(preset_key, {}).get('params', {})

        col1, col2, col3 = st.columns(3)
        with col1:
            params['breakout_days'] = st.slider(
                '突破天數',
                5, 120,
                defaults.get('breakout_days', 20),
                5,
                help='突破近N日高點'
            )
            params['use_breakout'] = st.checkbox('使用價格突破', value=defaults.get('use_breakout', True))

        with col2:
            params['volume_ratio_min'] = st.slider(
                '量比下限',
                0.5, 5.0,
                defaults.get('volume_ratio', 1.5),
                0.1,
                help='成交量相對於均量的倍數'
            )
            params['use_volume'] = st.checkbox('使用成交量', value=defaults.get('use_volume', True))

        with col3:
            params['rsi_min'] = st.slider('RSI 下限', 0, 100, defaults.get('rsi_min', 50), 5)
            params['rsi_max'] = st.slider('RSI 上限', 0, 100, defaults.get('rsi_max', 80), 5)
            params['use_rsi'] = st.checkbox('使用 RSI', value=defaults.get('use_rsi', True))

    elif strategy_type == '綜合策略':
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('**因子權重**')
            params['value_weight'] = st.slider('價值因子', 0.0, 1.0, 0.4, 0.1)
            params['growth_weight'] = st.slider('成長因子', 0.0, 1.0, 0.3, 0.1)
            params['momentum_weight'] = st.slider('動能因子', 0.0, 1.0, 0.3, 0.1)

        with col2:
            st.markdown('**篩選條件**')
            params['top_n'] = st.slider('選取前 N 名', 5, 50, 20, 5)
            params['min_score'] = st.slider('最低分數門檻', 0, 100, 50, 5)
            params['use_value'] = st.checkbox('使用價值因子', value=True)
            params['use_growth'] = st.checkbox('使用成長因子', value=True)
            params['use_momentum'] = st.checkbox('使用動能因子', value=True)

st.markdown('---')

# ========== 執行選股 ==========
st.subheader('3️⃣ 執行選股')

exec_col1, exec_col2 = st.columns([1, 2])

with exec_col1:
    run_button = st.button('🚀 執行選股', type='primary', use_container_width=True)

with exec_col2:
    st.caption('點擊按鈕開始篩選符合條件的股票')

if run_button:
    with st.spinner('正在載入數據並執行選股...'):
        try:
            # 載入數據 (清除快取確保讀取最新資料)
            loader = get_loader()
            loader.clear_cache()
            data = {
                'close': loader.get('close'),
                'volume': loader.get('volume'),
                'pe_ratio': loader.get('pe_ratio'),
                'pb_ratio': loader.get('pb_ratio'),
                'dividend_yield': loader.get('dividend_yield'),
                'revenue_yoy': loader.get('revenue_yoy'),
                'revenue_mom': loader.get('revenue_mom'),
                'market_value': loader.get('market_value'),
            }

            # 建立策略
            strategy_map = {
                '價值投資': ValueStrategy(params),
                '成長投資': GrowthStrategy(params),
                '動能投資': MomentumStrategy(params),
                '綜合策略': CompositeStrategy(params),
            }

            strategy = strategy_map[strategy_type]
            result = strategy.run(data)

            # 過濾掉已下市股票
            active_stocks = get_active_stocks()
            original_count = len(result.stocks)
            result.stocks = [s for s in result.stocks if s in active_stocks]
            filtered_count = original_count - len(result.stocks)

            # 儲存結果到 session state
            st.session_state['selection_result'] = result
            st.session_state['result_strategy_type'] = strategy_type
            st.session_state['result_params'] = params.copy()

            if filtered_count > 0:
                st.success(f'✅ 篩選完成！找到 {len(result.stocks)} 檔股票 (已排除 {filtered_count} 檔下市股票)')
            else:
                st.success(f'✅ 篩選完成！找到 {len(result.stocks)} 檔股票')

        except Exception as e:
            st.error(f'選股時發生錯誤: {e}')
            import traceback
            st.code(traceback.format_exc())

# ========== 顯示結果 ==========
if 'selection_result' in st.session_state:
    result = st.session_state['selection_result']
    result_strategy = st.session_state.get('result_strategy_type', '')

    st.markdown('---')
    st.subheader(f'4️⃣ {result_strategy} 選股結果')

    if len(result.stocks) > 0:
        # 統計與結果並排
        stat_col, result_col = st.columns([1, 3])

        with stat_col:
            st.markdown('#### 📊 統計摘要')
            st.metric('符合條件', f'{len(result.stocks)} 檔')

            if result.scores is not None and len(result.scores) > 0:
                st.metric('平均評分', f'{result.scores.mean():.1f}')
                st.metric('最高評分', f'{result.scores.max():.1f}')

        with result_col:
            # 取得股票資訊
            loader = get_loader()
            stock_info = loader.get_stock_info()
            close = loader.get('close')

            # 建立結果表格
            result_data = []
            for stock_id in result.stocks:
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''
                category = info['category'].values[0] if len(info) > 0 else ''
                market = info['market'].values[0] if len(info) > 0 else ''

                # 取得最新股價
                if stock_id in close.columns:
                    price_data = close[stock_id].dropna()
                    latest_price = price_data.iloc[-1] if not price_data.empty else None
                else:
                    latest_price = None

                score = result.scores.get(stock_id, 0) if result.scores is not None and stock_id in result.scores.index else 0

                result_data.append({
                    '代號': stock_id,
                    '名稱': name,
                    '產業': category,
                    '股價': f'{latest_price:.2f}' if latest_price else '-',
                    '評分': f'{score:.1f}',
                })

            df = pd.DataFrame(result_data)

            # 顯示可點擊的股票列表
            st.markdown('點擊 **📊 分析** 按鈕查看個股詳情：')

            # 分頁顯示 (每頁 10 筆)
            items_per_page = 10
            total_pages = (len(df) - 1) // items_per_page + 1

            if 'stock_list_page' not in st.session_state:
                st.session_state.stock_list_page = 0

            # 分頁控制
            page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
            with page_col1:
                if st.button('⬅️ 上一頁', disabled=st.session_state.stock_list_page == 0):
                    st.session_state.stock_list_page -= 1
                    st.rerun()
            with page_col2:
                st.markdown(f"<center>第 {st.session_state.stock_list_page + 1} / {total_pages} 頁</center>", unsafe_allow_html=True)
            with page_col3:
                if st.button('下一頁 ➡️', disabled=st.session_state.stock_list_page >= total_pages - 1):
                    st.session_state.stock_list_page += 1
                    st.rerun()

            # 顯示當前頁的股票
            start_idx = st.session_state.stock_list_page * items_per_page
            end_idx = min(start_idx + items_per_page, len(df))
            page_df = df.iloc[start_idx:end_idx]

            # 表頭
            header_cols = st.columns([1, 2, 2, 1.5, 1, 1.5])
            header_cols[0].markdown('**代號**')
            header_cols[1].markdown('**名稱**')
            header_cols[2].markdown('**產業**')
            header_cols[3].markdown('**股價**')
            header_cols[4].markdown('**評分**')
            header_cols[5].markdown('**操作**')

            st.markdown('<hr style="margin: 5px 0;">', unsafe_allow_html=True)

            # 股票列表
            for idx, row in page_df.iterrows():
                cols = st.columns([1, 2, 2, 1.5, 1, 1.5])
                cols[0].write(row['代號'])
                cols[1].write(row['名稱'])
                cols[2].write(row['產業'])
                cols[3].write(row['股價'])
                cols[4].write(row['評分'])

                # 分析按鈕
                if cols[5].button('📊 分析', key=f"analyze_{row['代號']}"):
                    st.session_state.analyze_stock = row['代號']
                    st.session_state.analyze_stock_name = row['名稱']

            # 顯示選中股票的詳細分析
            if 'analyze_stock' in st.session_state and st.session_state.analyze_stock:
                detail_stock_id = st.session_state.analyze_stock
                detail_stock_name = st.session_state.get('analyze_stock_name', '')

                st.markdown('---')
                st.markdown(f'### 📋 {detail_stock_id} {detail_stock_name} 詳細分析')

                # 關閉按鈕
                if st.button('❌ 關閉分析'):
                    del st.session_state.analyze_stock
                    st.rerun()

                # 取得該股票資料
                if detail_stock_id in close.columns:
                    stock_close = close[detail_stock_id].dropna()

                    if len(stock_close) > 0:
                        # 基本資訊
                        detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)

                        latest_price = stock_close.iloc[-1]
                        prev_price = stock_close.iloc[-2] if len(stock_close) > 1 else latest_price
                        change_pct = ((latest_price / prev_price) - 1) * 100

                        with detail_col1:
                            st.metric('最新股價', f'{latest_price:.2f}', f'{change_pct:+.2f}%')

                        with detail_col2:
                            pe_data = loader.get('pe_ratio')
                            if detail_stock_id in pe_data.columns:
                                pe_val = pe_data[detail_stock_id].dropna()
                                st.metric('本益比', f'{pe_val.iloc[-1]:.2f}' if len(pe_val) > 0 else '-')
                            else:
                                st.metric('本益比', '-')

                        with detail_col3:
                            dy_data = loader.get('dividend_yield')
                            if detail_stock_id in dy_data.columns:
                                dy_val = dy_data[detail_stock_id].dropna()
                                st.metric('殖利率', f'{dy_val.iloc[-1]:.2f}%' if len(dy_val) > 0 else '-')
                            else:
                                st.metric('殖利率', '-')

                        with detail_col4:
                            if len(stock_close) >= 252:
                                year_return = ((stock_close.iloc[-1] / stock_close.iloc[-252]) - 1) * 100
                                st.metric('近一年報酬', f'{year_return:+.1f}%')
                            else:
                                st.metric('近一年報酬', '-')

                        # 走勢圖
                        chart_col1, chart_col2 = st.columns(2)

                        with chart_col1:
                            st.markdown('**📈 近 60 日走勢**')
                            st.line_chart(stock_close.tail(60), height=200)

                        with chart_col2:
                            st.markdown('**📊 近 60 日成交量**')
                            vol_data = loader.get('volume')
                            if detail_stock_id in vol_data.columns:
                                stock_vol = vol_data[detail_stock_id].dropna().tail(60)
                                st.bar_chart(stock_vol, height=200)

                        # 技術指標簡析
                        st.markdown('**🔍 技術指標快速分析**')

                        from core.indicators import rsi, macd

                        tech_col1, tech_col2, tech_col3 = st.columns(3)

                        # RSI
                        rsi_val = rsi(stock_close, 14).iloc[-1]
                        with tech_col1:
                            if rsi_val > 70:
                                st.error(f'RSI: {rsi_val:.1f} (超買)')
                            elif rsi_val < 30:
                                st.success(f'RSI: {rsi_val:.1f} (超賣)')
                            else:
                                st.info(f'RSI: {rsi_val:.1f} (正常)')

                        # MACD
                        macd_line, signal_line, hist = macd(stock_close)
                        with tech_col2:
                            if macd_line.iloc[-1] > signal_line.iloc[-1]:
                                st.success(f'MACD: 多頭排列')
                            else:
                                st.warning(f'MACD: 空頭排列')

                        # 均線
                        ma20 = stock_close.rolling(20).mean().iloc[-1]
                        with tech_col3:
                            if latest_price > ma20:
                                st.success(f'站上 20 日均線')
                            else:
                                st.warning(f'跌破 20 日均線')

        # 產業分佈和匯出
        chart_col, export_col = st.columns([2, 1])

        with chart_col:
            if len(df) > 0:
                st.markdown('#### 🏭 產業分佈')
                industry_counts = df['產業'].value_counts().head(10)
                st.bar_chart(industry_counts)

        with export_col:
            st.markdown('#### 📥 匯出結果')

            # CSV 下載
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label='下載 CSV 檔案',
                data=csv,
                file_name=f'選股結果_{result_strategy}_{pd.Timestamp.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                use_container_width=True,
            )

            # PDF 報告下載
            if st.button('匯出 PDF 報告', use_container_width=True, key='export_screening_pdf'):
                from core.report_generator import ReportGenerator

                generator = ReportGenerator()
                html_report = generator.generate_screening_html(
                    strategy_name=result_strategy,
                    params=st.session_state.get('result_params', {}),
                    stocks=result.stocks,
                    scores=result.scores,
                    stock_info=stock_info,
                    close=close,
                )

                st.download_button(
                    label='下載報告 (HTML)',
                    data=html_report.encode('utf-8'),
                    file_name=f'選股報告_{result_strategy}_{pd.Timestamp.now().strftime("%Y%m%d")}.html',
                    mime='text/html',
                    use_container_width=True,
                    help='下載 HTML 報告，可在瀏覽器開啟並列印為 PDF',
                    key='download_screening_html'
                )

            st.caption('可匯入 Excel 或在瀏覽器列印為 PDF')

        # ========== 加入投資組合功能 ==========
        st.markdown('---')
        st.markdown('#### 💼 加入投資組合')

        portfolio_names = get_portfolio_names()

        if portfolio_names:
            add_col1, add_col2, add_col3 = st.columns([2, 1, 1])

            with add_col1:
                target_portfolio = st.selectbox('選擇投資組合', portfolio_names)

            with add_col2:
                default_shares = st.number_input('預設股數', 100, 100000, 1000, 100)

            with add_col3:
                use_current_price = st.checkbox('以現價為成本', value=True)

            # 選擇要加入的股票
            stocks_to_add = st.multiselect(
                '選擇要加入的股票',
                result.stocks,
                default=result.stocks[:10] if len(result.stocks) > 10 else result.stocks,
                format_func=lambda x: f"{x} - {stock_info[stock_info['stock_id']==x]['name'].values[0] if len(stock_info[stock_info['stock_id']==x]) > 0 else ''}"
            )

            if st.button('➕ 批次加入投資組合', type='primary'):
                if stocks_to_add:
                    # 取得當前股價
                    prices = {}
                    if use_current_price:
                        for stock_id in stocks_to_add:
                            if stock_id in close.columns:
                                prices[stock_id] = close[stock_id].dropna().iloc[-1]

                    # 批次加入
                    added_count = add_holdings_batch(
                        target_portfolio,
                        stocks_to_add,
                        default_shares,
                        prices if use_current_price else None,
                        datetime.now().strftime('%Y-%m-%d')
                    )

                    if added_count > 0:
                        st.success(f'✅ 已將 {added_count} 檔股票加入「{target_portfolio}」投資組合')
                    else:
                        st.info('所選股票已在投資組合中')
                else:
                    st.warning('請選擇要加入的股票')
        else:
            st.info('尚未建立投資組合，請先到「💼 投資組合」頁面建立。')
            if st.button('前往建立投資組合'):
                st.switch_page('pages/8_投資組合.py')

        # 儲存最新選股結果
        SCREENING_FILE = Path(__file__).parent.parent.parent / 'data' / 'latest_screening.json'
        SCREENING_FILE.parent.mkdir(exist_ok=True)
        screening_result = {
            'date': datetime.now().isoformat(),
            'strategy': result_strategy,
            'params': st.session_state.get('result_params', {}),
            'stocks': result.stocks,
            'count': len(result.stocks),
        }
        with open(SCREENING_FILE, 'w', encoding='utf-8') as f:
            json.dump(screening_result, f, ensure_ascii=False, indent=2)

    else:
        st.warning('😕 沒有找到符合條件的股票，請調整篩選參數。')

# ========== 策略說明 ==========
with st.expander('📖 策略說明'):
    st.markdown('''
    ### 💎 價值投資策略
    尋找市場低估的股票：
    - **本益比 (PE)**：股價÷每股盈餘，越低表示越便宜
    - **股價淨值比 (PB)**：股價÷每股淨值，<1 表示股價低於帳面價值
    - **殖利率**：股息÷股價，越高表示股息回報越好

    ### 🚀 成長投資策略
    尋找營收高速成長的股票：
    - **營收年增率**：與去年同期相比的成長率
    - **營收月增率**：與上個月相比的成長率
    - **連續成長**：確認成長趨勢的持續性

    ### 📈 動能投資策略
    尋找價格與成交量動能強勁的股票：
    - **價格突破**：突破近期高點表示上漲動能
    - **成交量放大**：量能擴增支持價格上漲
    - **RSI 強勢區間**：相對強弱指標在適當範圍

    ### 🎯 綜合策略
    結合以上三種因子，透過加權評分選出綜合表現最佳的股票。
    ''')
