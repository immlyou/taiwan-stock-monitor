"""
選股篩選頁面
"""
import streamlit as st
import pandas as pd
from pathlib import Path


from core.data_loader import get_loader, get_active_stocks
from core.strategies import ValueStrategy, GrowthStrategy, MomentumStrategy, CompositeStrategy, CustomStrategy
from core.strategies.custom import (
    AVAILABLE_FIELDS, OPERATORS, FilterCondition,
    save_custom_strategy, load_all_custom_strategies, delete_custom_strategy,
)
from config import STRATEGY_PRESETS
from app.components.sidebar import render_sidebar_mini
from app.components.strategy_params import render_strategy_params, render_preset_selector
from app.components.portfolio_utils import get_portfolio_names, add_holdings_batch
from app.components.error_handler import show_error, safe_execute
from core.alerts import AlertEngine
from app.components.page_header import render_page_header, render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.theme import (
    create_page_title, create_section_header, render_kpi_row,
    render_data_table, responsive_columns, format_number, COLORS,
)
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

render_global_ticker_bar()

st.markdown(create_page_title('選股篩選', subtitle='多因子策略篩選台股標的', icon='🔍'),
            unsafe_allow_html=True)

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

# ========== 策略選擇區 ==========
st.markdown(create_section_header('選擇策略', icon='1️⃣'), unsafe_allow_html=True)

strategy_cols = responsive_columns(5)

strategy_options = {
    '價值投資': {'icon': '💎', 'desc': '尋找被低估的好公司', 'color': 'blue'},
    '成長投資': {'icon': '🚀', 'desc': '尋找高速成長的公司', 'color': 'green'},
    '動能投資': {'icon': '📈', 'desc': '追蹤價量動能強勁股', 'color': 'orange'},
    '綜合策略': {'icon': '🎯', 'desc': '多因子綜合評分選股', 'color': 'purple'},
    '自訂篩選': {'icon': '🔧', 'desc': '自訂條件組合篩選', 'color': 'red'},
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

# ========== 參數設定區 ==========
st.markdown(create_section_header('參數設定', icon='2️⃣'), unsafe_allow_html=True)

# 預設組合選擇
preset_col, custom_col = st.columns([1, 3])

with preset_col:
    st.markdown('**快速選擇**')
    preset_key = render_preset_selector(key_prefix='screen_')

with custom_col:
    st.markdown('**自訂參數**')

    if strategy_type in ('價值投資', '成長投資', '動能投資', '綜合策略'):
        params = render_strategy_params(
            strategy_type=strategy_type,
            strategy_presets=STRATEGY_PRESETS,
            preset_key=preset_key,
            key_prefix='screen_',
            show_help=True,
        )
    elif strategy_type == '自訂篩選':
        params = {}
    else:
        params = {}

    if strategy_type == '自訂篩選':
        st.markdown('**動態條件組合**')

        # 條件組合模式
        combine_mode = st.radio(
            '條件組合方式', ['AND (全部符合)', 'OR (任一符合)'],
            horizontal=True, key='custom_combine_mode'
        )
        params['combine_mode'] = 'AND' if 'AND' in combine_mode else 'OR'

        # 載入/管理已儲存策略
        saved = load_all_custom_strategies()
        saved_col1, saved_col2 = st.columns([2, 1])
        with saved_col1:
            load_name = st.selectbox(
                '載入已儲存策略', ['(新策略)'] + list(saved.keys()),
                key='custom_load_select'
            )
        with saved_col2:
            if load_name != '(新策略)' and st.button('🗑️ 刪除', key='custom_del_btn'):
                delete_custom_strategy(load_name)
                st.rerun()

        # 初始化條件列表
        if 'custom_conditions' not in st.session_state:
            st.session_state.custom_conditions = []

        # 載入已儲存策略的條件
        if load_name != '(新策略)' and load_name in saved:
            saved_strategy = saved[load_name]
            st.session_state.custom_conditions = saved_strategy.get('conditions', [])
            params['combine_mode'] = saved_strategy.get('combine_mode', 'AND')

        # 新增條件按鈕
        if st.button('➕ 新增條件', key='custom_add_condition'):
            st.session_state.custom_conditions.append({
                'field_name': list(AVAILABLE_FIELDS.keys())[0],
                'operator': '>=',
                'value': 10.0,
                'enabled': True,
            })
            st.rerun()

        # 顯示條件列表
        conditions_to_keep = []
        for i, cond in enumerate(st.session_state.custom_conditions):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
            with c1:
                field_name = st.selectbox(
                    '欄位', list(AVAILABLE_FIELDS.keys()),
                    index=list(AVAILABLE_FIELDS.keys()).index(cond['field_name'])
                        if cond['field_name'] in AVAILABLE_FIELDS else 0,
                    key=f'cond_field_{i}'
                )
            with c2:
                operator = st.selectbox(
                    '運算子', list(OPERATORS.keys()),
                    index=list(OPERATORS.keys()).index(cond['operator'])
                        if cond['operator'] in OPERATORS else 0,
                    key=f'cond_op_{i}'
                )
            with c3:
                field_info = AVAILABLE_FIELDS.get(field_name, {})
                default_val = cond.get('value', field_info.get('default_val', 10.0))
                value = st.number_input(
                    f'值 ({field_info.get("unit", "")})',
                    value=float(default_val),
                    key=f'cond_val_{i}'
                )
            with c4:
                enabled = st.checkbox('啟用', value=cond.get('enabled', True), key=f'cond_en_{i}')
            with c5:
                remove = st.button('❌', key=f'cond_rm_{i}')

            if not remove:
                conditions_to_keep.append({
                    'field_name': field_name,
                    'operator': operator,
                    'value': value,
                    'enabled': enabled,
                })

        if len(conditions_to_keep) != len(st.session_state.custom_conditions):
            st.session_state.custom_conditions = conditions_to_keep
            st.rerun()

        # 將條件寫入 params
        params['conditions'] = conditions_to_keep

        # 儲存策略
        st.markdown('---')
        save_col1, save_col2 = st.columns([2, 1])
        with save_col1:
            save_name = st.text_input('策略名稱', value='', key='custom_save_name')
        with save_col2:
            st.markdown('<br>', unsafe_allow_html=True)
            if st.button('💾 儲存策略', key='custom_save_btn'):
                if save_name and conditions_to_keep:
                    save_custom_strategy(
                        save_name,
                        [FilterCondition.from_dict(c) for c in conditions_to_keep],
                        params['combine_mode']
                    )
                    st.success(f'已儲存策略「{save_name}」')
                elif not save_name:
                    st.warning('請輸入策略名稱')
                else:
                    st.warning('請至少新增一個條件')

# ========== 執行選股 ==========
st.markdown(create_section_header('執行選股', icon='3️⃣'), unsafe_allow_html=True)

# 即時命中筆數（執行前的潛在母體 / 上次結果）
exec_col1, exec_col2, exec_col3 = st.columns([1, 1, 1])

with exec_col1:
    run_button = st.button('🚀 執行選股', type='primary', use_container_width=True)

with exec_col2:
    try:
        _universe = len(get_active_stocks())
    except Exception:
        _universe = None
    st.metric('可選母體', f'{_universe} 檔' if _universe else '-')

with exec_col3:
    _prev = get_state(StateKeys.SELECTION_RESULT)
    _prev_n = len(_prev.stocks) if _prev is not None else 0
    st.metric('上次命中', f'{_prev_n} 檔')

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
                '自訂篩選': CustomStrategy(params),
            }

            strategy = strategy_map[strategy_type]
            result = strategy.run(data)

            # 過濾掉已下市股票
            active_stocks = get_active_stocks()
            original_count = len(result.stocks)
            result.stocks = [s for s in result.stocks if s in active_stocks]
            filtered_count = original_count - len(result.stocks)

            # 儲存結果到 session state
            set_state(StateKeys.SELECTION_RESULT, result)
            set_state(StateKeys.RESULT_STRATEGY_TYPE, strategy_type)
            set_state(StateKeys.RESULT_PARAMS, params.copy())

            if filtered_count > 0:
                st.success(f'✅ 篩選完成！找到 {len(result.stocks)} 檔股票 (已排除 {filtered_count} 檔下市股票)')
            else:
                st.success(f'✅ 篩選完成！找到 {len(result.stocks)} 檔股票')

        except Exception as e:
            show_error(e, title='選股時發生錯誤')
            import traceback
            st.code(traceback.format_exc())

# ========== 顯示結果 ==========
if get_state(StateKeys.SELECTION_RESULT) is not None:
    result = get_state(StateKeys.SELECTION_RESULT)
    result_strategy = get_state(StateKeys.RESULT_STRATEGY_TYPE, '')

    st.markdown(create_section_header(f'{result_strategy} 選股結果', icon='4️⃣'),
                unsafe_allow_html=True)

    if len(result.stocks) > 0:
        # 取得股票資訊
        loader = get_loader()
        stock_info = loader.get_stock_info()
        close = loader.get('close')

        # KPI 統計列
        kpi_items = [{'label': '符合條件', 'value': format_number(len(result.stocks), kind='int')}]
        if result.scores is not None and len(result.scores) > 0:
            kpi_items.append({'label': '平均評分', 'value': format_number(result.scores.mean(), kind='price')})
            kpi_items.append({'label': '最高評分', 'value': format_number(result.scores.max(), kind='price')})
            kpi_items.append({'label': '最低評分', 'value': format_number(result.scores.min(), kind='price')})
        render_kpi_row(kpi_items)

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

        # ===== 結果表（統一表格元件，內建虛擬捲動 / sticky 表頭）=====
        st.markdown(create_section_header('篩選清單', icon='📋'), unsafe_allow_html=True)
        render_data_table(
            df,
            freeze_cols=1,
            dense=True,
            height=400,
            column_config={
                '代號': st.column_config.TextColumn('代號', width='small'),
                '名稱': st.column_config.TextColumn('名稱', width='small'),
                '產業': st.column_config.TextColumn('產業'),
                '股價': st.column_config.TextColumn('股價', width='small'),
                '評分': st.column_config.TextColumn('評分', width='small'),
            },
        )

        # ===== 個股快速分析（從清單挑選）=====
        st.markdown(create_section_header('個股快速分析', icon='🔬'), unsafe_allow_html=True)
        pick_col, btn_col = st.columns([3, 1])
        with pick_col:
            picked = st.selectbox(
                '選擇要分析的股票',
                options=df['代號'].tolist(),
                format_func=lambda x: f"{x} - {df[df['代號']==x]['名稱'].values[0] if len(df[df['代號']==x]) else ''}",
                key='screen_analyze_pick',
                label_visibility='collapsed',
            )
        with btn_col:
            if st.button('📊 分析', use_container_width=True, key='screen_analyze_btn'):
                _name_row = df[df['代號'] == picked]
                set_state(StateKeys.ANALYZE_STOCK, picked)
                set_state(StateKeys.ANALYZE_STOCK_NAME,
                          _name_row['名稱'].values[0] if len(_name_row) else '')

        # 顯示選中股票的詳細分析
        if get_state(StateKeys.ANALYZE_STOCK):
                detail_stock_id = get_state(StateKeys.ANALYZE_STOCK)
                detail_stock_name = get_state(StateKeys.ANALYZE_STOCK_NAME, '')

                st.markdown(create_section_header(f'{detail_stock_id} {detail_stock_name} 詳細分析', icon='📋'),
                            unsafe_allow_html=True)

                # 關閉按鈕
                if st.button('❌ 關閉分析'):
                    set_state(StateKeys.ANALYZE_STOCK, None)
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
                                st.success('MACD: 多頭排列')
                            else:
                                st.warning('MACD: 空頭排列')

                        # 均線
                        ma20 = stock_close.rolling(20).mean().iloc[-1]
                        with tech_col3:
                            if latest_price > ma20:
                                st.success('站上 20 日均線')
                            else:
                                st.warning('跌破 20 日均線')

        # 產業分佈和匯出
        chart_col, export_col = st.columns([2, 1])

        with chart_col:
            if len(df) > 0:
                st.markdown(create_section_header('產業分佈', icon='🏭'), unsafe_allow_html=True)
                industry_counts = df['產業'].value_counts().head(10)
                st.bar_chart(industry_counts)

        with export_col:
            st.markdown(create_section_header('匯出結果', icon='📥'), unsafe_allow_html=True)

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
                    params=get_state(StateKeys.RESULT_PARAMS, {}),
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
        st.markdown(create_section_header('加入投資組合', icon='💼'), unsafe_allow_html=True)

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
                        show_empty_state('所選股票已在投資組合中', icon='ℹ️')
                else:
                    st.warning('請選擇要加入的股票')
        else:
            show_empty_state('尚未建立投資組合', icon='💼', suggestion='請先到「投資組合」頁面建立')
            if st.button('前往建立投資組合'):
                st.switch_page('pages/8_投資組合.py')

        # ========== 批次設定警報功能 ==========
        st.markdown(create_section_header('批次設定警報', icon='🔔'), unsafe_allow_html=True)

        ALERT_TYPES = {
            'price_above': {'name': '價格突破上方', 'icon': '📈'},
            'price_below': {'name': '價格跌破下方', 'icon': '📉'},
            'rsi_above':   {'name': 'RSI 超買',     'icon': '🔥'},
            'rsi_below':   {'name': 'RSI 超賣',     'icon': '❄️'},
            'volume_spike':{'name': '成交量爆量',   'icon': '💥'},
            'new_high':    {'name': '創新高',       'icon': '🏆'},
            'new_low':     {'name': '創新低',       'icon': '📊'},
        }

        ALERTS_FILE = AlertEngine.ALERTS_FILE
        ALERTS_FILE.parent.mkdir(exist_ok=True)

        alert_col1, alert_col2, alert_col3 = st.columns([2, 1, 1])

        with alert_col1:
            batch_alert_type = st.selectbox(
                '警報類型',
                list(ALERT_TYPES.keys()),
                format_func=lambda x: f"{ALERT_TYPES[x]['icon']} {ALERT_TYPES[x]['name']}",
                key='batch_alert_type'
            )

        with alert_col2:
            if batch_alert_type in ['price_above', 'price_below']:
                batch_alert_value = st.number_input('偏移 (%)', -20.0, 20.0, 5.0, 1.0,
                    help='以當前股價為基準，設定觸發價格的偏移百分比', key='batch_alert_offset')
                alert_value_mode = 'price_pct'
            elif batch_alert_type in ['rsi_above', 'rsi_below']:
                default_rsi = 70 if batch_alert_type == 'rsi_above' else 30
                batch_alert_value = st.number_input('RSI 門檻', 0, 100, default_rsi, 5, key='batch_alert_rsi')
                alert_value_mode = 'fixed'
            elif batch_alert_type == 'volume_spike':
                batch_alert_value = st.number_input('量能倍數', 1.0, 10.0, 2.0, 0.5, key='batch_alert_vol')
                alert_value_mode = 'fixed'
            else:  # new_high / new_low
                batch_alert_value = st.number_input('天數範圍', 5, 252, 20, 5, key='batch_alert_days')
                alert_value_mode = 'fixed'

        with alert_col3:
            batch_alert_note = st.text_input('備註', placeholder='選股警報', key='batch_alert_note')

        stocks_for_alert = st.multiselect(
            '選擇要設定警報的股票',
            result.stocks,
            default=result.stocks[:10] if len(result.stocks) > 10 else result.stocks,
            format_func=lambda x: f"{x} - {stock_info[stock_info['stock_id']==x]['name'].values[0] if len(stock_info[stock_info['stock_id']==x]) > 0 else ''}",
            key='batch_alert_stocks'
        )

        if st.button('🔔 批次設定警報', type='secondary', key='batch_set_alerts'):
            if stocks_for_alert:
                try:
                    import uuid as _uuid
                    if ALERTS_FILE.exists():
                        with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                            alerts_data = json.load(f)
                    else:
                        alerts_data = {'alerts': []}

                    added_alerts = 0
                    for stock_id in stocks_for_alert:
                        # 計算觸發價格
                        if alert_value_mode == 'price_pct':
                            if stock_id in close.columns:
                                current_price = float(close[stock_id].dropna().iloc[-1])
                            else:
                                current_price = 0
                            if batch_alert_type == 'price_above':
                                trigger_value = round(current_price * (1 + batch_alert_value / 100), 2)
                            else:
                                trigger_value = round(current_price * (1 - batch_alert_value / 100), 2)
                        else:
                            trigger_value = batch_alert_value

                        new_alert = {
                            'id': str(_uuid.uuid4())[:8],
                            'stock_id': stock_id,
                            'type': batch_alert_type,
                            'value': trigger_value,
                            'note': batch_alert_note or f'選股篩選 - {result_strategy}',
                            'enabled': True,
                            'triggered': False,
                            'created_at': datetime.now().isoformat(),
                            'triggered_at': None,
                        }
                        alerts_data['alerts'].append(new_alert)
                        added_alerts += 1

                    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(alerts_data, f, ensure_ascii=False, indent=2, default=str)

                    st.success(f'✅ 已為 {added_alerts} 檔股票設定「{ALERT_TYPES[batch_alert_type]["name"]}」警報')
                except Exception as e:
                    st.error(f'設定警報失敗：{e}')
            else:
                st.warning('請選擇要設定警報的股票')

        # 儲存最新選股結果
        SCREENING_FILE = Path(__file__).parent.parent.parent / 'data' / 'latest_screening.json'
        SCREENING_FILE.parent.mkdir(exist_ok=True)
        screening_result = {
            'date': datetime.now().isoformat(),
            'strategy': result_strategy,
            'params': get_state(StateKeys.RESULT_PARAMS, {}),
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
