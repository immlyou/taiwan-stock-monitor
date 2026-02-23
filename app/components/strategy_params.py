"""
策略參數 UI 共用組件

將選股篩選與回測分析頁面中重複的策略參數 slider/checkbox UI 抽取為共用函數。
"""
import streamlit as st
from typing import Dict, Optional


def render_strategy_params(
    strategy_type: str,
    strategy_presets: Dict,
    preset_key: str = 'standard',
    key_prefix: str = '',
    show_help: bool = False,
) -> Dict:
    """
    渲染策略參數 UI（slider + checkbox），回傳參數 dict。

    Parameters
    ----------
    strategy_type : str
        策略類型，如 '價值投資', '成長投資', '動能投資', '綜合策略'
    strategy_presets : dict
        STRATEGY_PRESETS 設定檔
    preset_key : str
        預設組合 key ('conservative', 'standard', 'aggressive')
    key_prefix : str
        Streamlit widget key 前綴（避免跨頁面 key 衝突）
    show_help : bool
        是否顯示 slider help 文字

    Returns
    -------
    dict
        策略參數字典
    """
    params: Dict = {}

    if strategy_type == '價值投資':
        defaults = strategy_presets.get('value', {}).get(preset_key, {}).get('params', {})

        col1, col2, col3 = st.columns(3)
        with col1:
            params['pe_max'] = st.slider(
                '本益比上限', 1.0, 50.0,
                defaults.get('pe_max', 15.0), 0.5,
                key=f'{key_prefix}pe',
                help='PE 越低代表股價相對盈餘越便宜' if show_help else None,
            )
            params['use_pe'] = st.checkbox(
                '使用本益比', value=defaults.get('use_pe', True),
                key=f'{key_prefix}use_pe',
            )
        with col2:
            params['pb_max'] = st.slider(
                '股價淨值比上限', 0.1, 5.0,
                defaults.get('pb_max', 1.5), 0.1,
                key=f'{key_prefix}pb',
                help='PB < 1 表示股價低於帳面價值' if show_help else None,
            )
            params['use_pb'] = st.checkbox(
                '使用股價淨值比', value=defaults.get('use_pb', True),
                key=f'{key_prefix}use_pb',
            )
        with col3:
            params['dividend_yield_min'] = st.slider(
                '殖利率下限 (%)', 0.0, 15.0,
                defaults.get('dividend_yield_min', 4.0), 0.5,
                key=f'{key_prefix}dy',
                help='殖利率越高，股息回報越好' if show_help else None,
            )
            params['use_dividend'] = st.checkbox(
                '使用殖利率', value=defaults.get('use_dividend', True),
                key=f'{key_prefix}use_dy',
            )

    elif strategy_type == '成長投資':
        defaults = strategy_presets.get('growth', {}).get(preset_key, {}).get('params', {})

        col1, col2, col3 = st.columns(3)
        with col1:
            params['revenue_yoy_min'] = st.slider(
                '營收年增率下限 (%)', -50.0, 200.0,
                defaults.get('revenue_yoy_min', 20.0), 5.0,
                key=f'{key_prefix}yoy',
                help='與去年同期相比的成長率' if show_help else None,
            )
            params['use_yoy'] = st.checkbox(
                '使用年增率', value=defaults.get('use_yoy', True),
                key=f'{key_prefix}use_yoy',
            )
        with col2:
            params['revenue_mom_min'] = st.slider(
                '營收月增率下限 (%)', -50.0, 100.0,
                defaults.get('revenue_mom_min', 10.0), 5.0,
                key=f'{key_prefix}mom',
                help='與上個月相比的成長率' if show_help else None,
            )
            params['use_mom'] = st.checkbox(
                '使用月增率', value=defaults.get('use_mom', True),
                key=f'{key_prefix}use_mom',
            )
        with col3:
            params['consecutive_months'] = st.slider(
                '連續成長月數', 1, 12,
                defaults.get('consecutive_months', 3), 1,
                key=f'{key_prefix}consec',
                help='確認成長趨勢的持續性' if show_help else None,
            )
            params['use_consecutive'] = st.checkbox(
                '使用連續成長', value=True,
                key=f'{key_prefix}use_consec',
            )

    elif strategy_type == '動能投資':
        defaults = strategy_presets.get('momentum', {}).get(preset_key, {}).get('params', {})

        col1, col2, col3 = st.columns(3)
        with col1:
            params['breakout_days'] = st.slider(
                '突破天數', 5, 120,
                defaults.get('breakout_days', 20), 5,
                key=f'{key_prefix}breakout',
                help='突破近N日高點' if show_help else None,
            )
            params['use_breakout'] = st.checkbox(
                '使用價格突破', value=defaults.get('use_breakout', True),
                key=f'{key_prefix}use_breakout',
            )
        with col2:
            params['volume_ratio_min'] = st.slider(
                '量比下限', 0.5, 5.0,
                defaults.get('volume_ratio', 1.5), 0.1,
                key=f'{key_prefix}vol',
                help='成交量相對於均量的倍數' if show_help else None,
            )
            params['use_volume'] = st.checkbox(
                '使用成交量', value=defaults.get('use_volume', True),
                key=f'{key_prefix}use_vol',
            )
        with col3:
            params['rsi_min'] = st.slider(
                'RSI 下限', 0, 100,
                defaults.get('rsi_min', 50), 5,
                key=f'{key_prefix}rsi_min',
            )
            params['rsi_max'] = st.slider(
                'RSI 上限', 0, 100,
                defaults.get('rsi_max', 80), 5,
                key=f'{key_prefix}rsi_max',
            )
            params['use_rsi'] = st.checkbox(
                '使用 RSI', value=defaults.get('use_rsi', True),
                key=f'{key_prefix}use_rsi',
            )

    elif strategy_type == '綜合策略':
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('**因子權重**')
            params['value_weight'] = st.slider(
                '價值因子', 0.0, 1.0, 0.4, 0.1, key=f'{key_prefix}val_w',
            )
            params['growth_weight'] = st.slider(
                '成長因子', 0.0, 1.0, 0.3, 0.1, key=f'{key_prefix}grow_w',
            )
            params['momentum_weight'] = st.slider(
                '動能因子', 0.0, 1.0, 0.3, 0.1, key=f'{key_prefix}mom_w',
            )
        with col2:
            st.markdown('**篩選條件**')
            params['top_n'] = st.slider(
                '選取前 N 名', 5, 50, 20, 5, key=f'{key_prefix}topn',
            )
            params['min_score'] = st.slider(
                '最低分數門檻', 0, 100, 50, 5, key=f'{key_prefix}min_score',
            )
            params['use_value'] = st.checkbox(
                '使用價值因子', value=True, key=f'{key_prefix}use_val',
            )
            params['use_growth'] = st.checkbox(
                '使用成長因子', value=True, key=f'{key_prefix}use_grow',
            )
            params['use_momentum'] = st.checkbox(
                '使用動能因子', value=True, key=f'{key_prefix}use_mom',
            )

    return params


def render_preset_selector(key_prefix: str = '', horizontal: bool = False) -> str:
    """
    渲染風險偏好選擇器，回傳 preset_key。

    Returns
    -------
    str
        'conservative', 'standard', or 'aggressive'
    """
    preset_type = st.radio(
        '風險偏好',
        ['保守型', '標準型', '積極型'],
        index=1,
        horizontal=horizontal,
        key=f'{key_prefix}preset_type',
    )
    preset_map = {'保守型': 'conservative', '標準型': 'standard', '積極型': 'aggressive'}
    return preset_map[preset_type]
