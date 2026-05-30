"""
策略管理頁面
"""
import streamlit as st
import pandas as pd
import json
from pathlib import Path


from config import STRATEGY_PARAMS
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error
from app.components.page_header import render_page_header, render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.session_manager import set_state, StateKeys
from app.components.theme import COLORS, create_page_title, create_section_header

st.set_page_config(page_title='策略管理', page_icon='⚙️', layout='wide')
render_sidebar_mini(current_page='strategy')

render_global_ticker_bar()
st.markdown(create_page_title('策略管理', subtitle='建立、管理與比較自訂選股策略', icon='🎯'), unsafe_allow_html=True)

# 策略設定檔路徑
STRATEGIES_FILE = Path(__file__).parent.parent.parent / 'saved_strategies.json'


def load_saved_strategies():
    """載入已儲存的策略"""
    if STRATEGIES_FILE.exists():
        with open(STRATEGIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_strategies(strategies):
    """儲存策略"""
    with open(STRATEGIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)


# 載入已儲存的策略
saved_strategies = load_saved_strategies()

# 分頁
tab1, tab2, tab3 = st.tabs(['建立策略', '已儲存策略', '策略比較'])

# ==================== 建立策略 ====================
with tab1:
    st.markdown(create_section_header('建立自訂策略', icon='🛠️'), unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        # 基本設定
        strategy_name = st.text_input('策略名稱', value='我的策略')
        strategy_type = st.selectbox(
            '策略類型',
            ['價值投資', '成長投資', '動能投資', '綜合策略']
        )
        strategy_description = st.text_area(
            '策略描述',
            value='自訂策略描述...',
            height=100
        )

    with col2:
        st.markdown(create_section_header('參數設定', icon='⚙️'), unsafe_allow_html=True)

        params = {}

        if strategy_type == '價值投資':
            c1, c2 = st.columns(2)
            with c1:
                params['pe_max'] = st.number_input('本益比上限', 1.0, 100.0, 15.0, 0.5)
                params['pb_max'] = st.number_input('股價淨值比上限', 0.1, 10.0, 1.5, 0.1)
            with c2:
                params['dividend_yield_min'] = st.number_input('殖利率下限 (%)', 0.0, 20.0, 4.0, 0.5)

            st.markdown('**條件開關**')
            c1, c2, c3 = st.columns(3)
            with c1:
                params['use_pe'] = st.checkbox('使用本益比', value=True, key='v_pe')
            with c2:
                params['use_pb'] = st.checkbox('使用股價淨值比', value=True, key='v_pb')
            with c3:
                params['use_dividend'] = st.checkbox('使用殖利率', value=True, key='v_dy')

        elif strategy_type == '成長投資':
            c1, c2 = st.columns(2)
            with c1:
                params['revenue_yoy_min'] = st.number_input('營收年增率下限 (%)', -100.0, 500.0, 20.0, 5.0)
                params['revenue_mom_min'] = st.number_input('營收月增率下限 (%)', -100.0, 200.0, 10.0, 5.0)
            with c2:
                params['consecutive_months'] = st.number_input('連續成長月數', 1, 24, 3, 1)

            st.markdown('**條件開關**')
            c1, c2, c3 = st.columns(3)
            with c1:
                params['use_yoy'] = st.checkbox('使用年增率', value=True, key='g_yoy')
            with c2:
                params['use_mom'] = st.checkbox('使用月增率', value=True, key='g_mom')
            with c3:
                params['use_consecutive'] = st.checkbox('使用連續成長', value=True, key='g_cons')

        elif strategy_type == '動能投資':
            c1, c2 = st.columns(2)
            with c1:
                params['breakout_days'] = st.number_input('突破天數', 5, 250, 20, 5)
                params['volume_ratio_min'] = st.number_input('量比下限', 0.5, 10.0, 1.5, 0.1)
            with c2:
                params['rsi_min'] = st.number_input('RSI 下限', 0, 100, 50, 5)
                params['rsi_max'] = st.number_input('RSI 上限', 0, 100, 80, 5)

            st.markdown('**條件開關**')
            c1, c2, c3 = st.columns(3)
            with c1:
                params['use_breakout'] = st.checkbox('使用價格突破', value=True, key='m_br')
            with c2:
                params['use_volume'] = st.checkbox('使用成交量', value=True, key='m_vol')
            with c3:
                params['use_rsi'] = st.checkbox('使用 RSI', value=True, key='m_rsi')

        elif strategy_type == '綜合策略':
            st.markdown('**因子權重**')
            c1, c2, c3 = st.columns(3)
            with c1:
                params['value_weight'] = st.number_input('價值因子權重', 0.0, 1.0, 0.4, 0.1)
            with c2:
                params['growth_weight'] = st.number_input('成長因子權重', 0.0, 1.0, 0.3, 0.1)
            with c3:
                params['momentum_weight'] = st.number_input('動能因子權重', 0.0, 1.0, 0.3, 0.1)

            st.markdown('**篩選設定**')
            c1, c2 = st.columns(2)
            with c1:
                params['top_n'] = st.number_input('選取前 N 名', 5, 100, 20, 5)
            with c2:
                params['min_score'] = st.number_input('最低分數門檻', 0, 100, 50, 5)

            st.markdown('**因子開關**')
            c1, c2, c3 = st.columns(3)
            with c1:
                params['use_value'] = st.checkbox('使用價值因子', value=True, key='c_val')
            with c2:
                params['use_growth'] = st.checkbox('使用成長因子', value=True, key='c_gro')
            with c3:
                params['use_momentum'] = st.checkbox('使用動能因子', value=True, key='c_mom')

    # 儲存按鈕
    st.markdown(create_section_header('儲存', icon='💾'), unsafe_allow_html=True)

    if st.button('儲存策略', type='primary', use_container_width=True):
        if strategy_name:
            saved_strategies[strategy_name] = {
                'type': strategy_type,
                'description': strategy_description,
                'params': params,
            }
            save_strategies(saved_strategies)
            st.success(f'策略 "{strategy_name}" 已儲存！')
            st.rerun()
        else:
            show_error(Exception('請輸入策略名稱'), title='缺少策略名稱')

# ==================== 已儲存策略 ====================
with tab2:
    st.markdown(create_section_header('已儲存的策略', icon='📚'), unsafe_allow_html=True)

    if saved_strategies:
        for name, strategy in saved_strategies.items():
            with st.expander(f'📋 {name}'):
                # 策略資訊卡片（深色 token 樣式）
                st.markdown(
                    f'''
                    <div style="
                        background:{COLORS['secondary']};
                        border:1px solid {COLORS['border']};
                        border-left:3px solid {COLORS['accent']};
                        border-radius:8px;
                        padding:12px 14px;
                        margin-bottom:10px;
                    ">
                        <div style="color:{COLORS['text_muted']};font-size:0.78rem;margin-bottom:2px">類型</div>
                        <div style="color:{COLORS['text_primary']};font-size:0.95rem;font-weight:600;margin-bottom:8px">{strategy['type']}</div>
                        <div style="color:{COLORS['text_muted']};font-size:0.78rem;margin-bottom:2px">描述</div>
                        <div style="color:{COLORS['text_secondary']};font-size:0.9rem">{strategy['description']}</div>
                    </div>
                    ''',
                    unsafe_allow_html=True,
                )

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f'**參數:**')
                    st.json(strategy['params'])

                with col2:
                    # 載入：主要動作，primary 樣式
                    if st.button('🚀 載入策略', key=f'load_{name}', type='primary', use_container_width=True):
                        set_state(StateKeys.LOADED_STRATEGY, strategy)
                        st.toast(f'已載入策略 "{name}"')
                        st.switch_page('pages/1_選股篩選.py')

                    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

                    # 刪除：危險動作，二次確認避免誤觸
                    confirm_key = f'confirm_delete_{name}'
                    if not st.session_state.get(confirm_key):
                        if st.button('🗑️ 刪除', key=f'delete_{name}', use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        st.markdown(
                            f'<div style="color:{COLORS["danger"]};font-size:0.82rem;font-weight:600;'
                            f'margin-bottom:4px">⚠️ 確定刪除「{name}」？此動作無法復原</div>',
                            unsafe_allow_html=True,
                        )
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            if st.button('確認刪除', key=f'delete_confirm_{name}', type='primary', use_container_width=True):
                                del saved_strategies[name]
                                save_strategies(saved_strategies)
                                st.session_state.pop(confirm_key, None)
                                st.warning(f'已刪除策略 "{name}"')
                                st.rerun()
                        with dc2:
                            if st.button('取消', key=f'delete_cancel_{name}', use_container_width=True):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
    else:
        show_empty_state('尚未儲存任何策略', icon='📋', suggestion='請在「建立策略」分頁中建立並儲存策略')

# ==================== 策略比較 ====================
with tab3:
    st.markdown(create_section_header('策略比較', icon='⚖️'), unsafe_allow_html=True)

    if len(saved_strategies) >= 2:
        strategies_to_compare = st.multiselect(
            '選擇要比較的策略',
            options=list(saved_strategies.keys()),
            default=list(saved_strategies.keys())[:2]
        )

        if len(strategies_to_compare) >= 2:
            # 建立比較表格
            comparison_data = []

            for name in strategies_to_compare:
                strategy = saved_strategies[name]
                row = {
                    '策略名稱': name,
                    '類型': strategy['type'],
                }

                # 根據類型添加關鍵參數
                params = strategy['params']
                if strategy['type'] == '價值投資':
                    row['PE上限'] = params.get('pe_max', '-')
                    row['PB上限'] = params.get('pb_max', '-')
                    row['殖利率下限'] = params.get('dividend_yield_min', '-')

                elif strategy['type'] == '成長投資':
                    row['年增率下限'] = params.get('revenue_yoy_min', '-')
                    row['月增率下限'] = params.get('revenue_mom_min', '-')

                elif strategy['type'] == '動能投資':
                    row['突破天數'] = params.get('breakout_days', '-')
                    row['量比下限'] = params.get('volume_ratio_min', '-')

                elif strategy['type'] == '綜合策略':
                    row['價值權重'] = params.get('value_weight', '-')
                    row['成長權重'] = params.get('growth_weight', '-')
                    row['動能權重'] = params.get('momentum_weight', '-')

                comparison_data.append(row)

            df = pd.DataFrame(comparison_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        show_empty_state('需要至少儲存 2 個策略才能進行比較', icon='⚖️', suggestion='請先在「建立策略」分頁中建立更多策略')

# 預設策略說明
st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
st.markdown(create_section_header('預設策略參數', icon='🧾'), unsafe_allow_html=True)

with st.expander('查看系統預設參數'):
    st.json(STRATEGY_PARAMS)
