# -*- coding: utf-8 -*-
# Components module

from app.components.session_manager import (
    StateKeys,
    DEFAULT_VALUES,
    # 初始化
    init_session_state,
    init_all,
    # 基本存取
    get_state,
    set_state,
    update_state,
    delete_state,
    clear_state,
    reset_state,
    has_state,
    # 股票操作
    add_selected_stock,
    remove_selected_stock,
    clear_selected_stocks,
    # 分析結果
    set_analysis_result,
    get_analysis_result,
    # 使用者設定
    get_user_setting,
    set_user_setting,
    # 跨頁面傳遞
    navigate_to_stock_analysis,
    get_stock_to_analyze,
    pass_screening_results,
    get_screening_results,
    pass_optimized_params,
    # 工具
    get_all_states,
    debug_state,
)

__all__ = [
    'StateKeys',
    'DEFAULT_VALUES',
    'init_session_state',
    'init_all',
    'get_state',
    'set_state',
    'update_state',
    'delete_state',
    'clear_state',
    'reset_state',
    'has_state',
    'add_selected_stock',
    'remove_selected_stock',
    'clear_selected_stocks',
    'set_analysis_result',
    'get_analysis_result',
    'get_user_setting',
    'set_user_setting',
    'navigate_to_stock_analysis',
    'get_stock_to_analyze',
    'pass_screening_results',
    'get_screening_results',
    'pass_optimized_params',
    'get_all_states',
    'debug_state',
]
