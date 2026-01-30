# -*- coding: utf-8 -*-
"""
Session State 管理模組

提供統一的 Streamlit Session State 管理機制，包含：
- 預定義的 session state 鍵值
- 初始化函數
- 安全存取函數
- 類型驗證

使用方式:
    from app.components.session_manager import init_session_state, get_state, set_state

    # 在頁面開頭初始化
    init_session_state()

    # 存取狀態
    watchlist = get_state('watchlist')
    set_state('selected_stocks', ['2330', '2454'])
"""
import streamlit as st
from typing import Any, Dict, List, Optional, TypeVar, Callable
from dataclasses import dataclass, field
from datetime import datetime


# ========== 常數定義 ==========

# Session State 鍵值名稱
class StateKeys:
    """Session State 鍵值常數"""

    # 股票選擇相關
    SELECTED_STOCKS = 'selected_stocks'          # 當前選中的股票列表
    CURRENT_STOCK = 'current_stock'              # 當前分析的單一股票
    ANALYZE_STOCK = 'analyze_stock'              # 要分析的股票（跨頁傳遞用）

    # 自選股相關
    WATCHLIST = 'watchlist'                      # 自選股清單
    WATCHLIST_NAME = 'watchlist_name'            # 當前選中的自選股清單名稱

    # 分析結果
    ANALYSIS_RESULTS = 'analysis_results'        # 分析結果快取
    SCREENING_RESULTS = 'screening_results'      # 選股篩選結果
    BACKTEST_RESULTS = 'backtest_results'        # 回測結果

    # 策略相關
    SELECTED_STRATEGY = 'selected_strategy'      # 選中的策略類型
    BACKTEST_STRATEGY = 'backtest_strategy'      # 回測策略
    OPTIMIZED_PARAMS = 'optimized_params'        # 優化後的參數
    APPLY_OPTIMIZED_PARAMS = 'apply_optimized_params'  # 套用優化參數

    # 使用者設定
    USER_SETTINGS = 'user_settings'              # 使用者偏好設定
    THEME = 'theme'                              # 主題設定

    # UI 狀態
    SIDEBAR_STATE = 'sidebar_state'              # 側邊欄狀態
    CURRENT_PAGE = 'current_page'                # 當前頁面
    VIEW_MODE = 'view_mode'                      # 顯示模式（表格/卡片）

    # 投資組合
    PORTFOLIO = 'portfolio'                      # 投資組合
    PORTFOLIO_NAME = 'portfolio_name'            # 當前投資組合名稱

    # 警報設定
    ALERTS = 'alerts'                            # 警報列表

    # 暫存資料
    TEMP_DATA = 'temp_data'                      # 暫存資料
    LAST_UPDATE = 'last_update'                  # 最後更新時間


# 預設值定義
DEFAULT_VALUES: Dict[str, Any] = {
    StateKeys.SELECTED_STOCKS: [],
    StateKeys.CURRENT_STOCK: None,
    StateKeys.ANALYZE_STOCK: None,
    StateKeys.WATCHLIST: {},
    StateKeys.WATCHLIST_NAME: None,
    StateKeys.ANALYSIS_RESULTS: {},
    StateKeys.SCREENING_RESULTS: None,
    StateKeys.BACKTEST_RESULTS: None,
    StateKeys.SELECTED_STRATEGY: '價值投資',
    StateKeys.BACKTEST_STRATEGY: '價值投資',
    StateKeys.OPTIMIZED_PARAMS: None,
    StateKeys.APPLY_OPTIMIZED_PARAMS: None,
    StateKeys.USER_SETTINGS: {
        'default_period': '近3年',
        'default_top_n': 20,
        'chart_style': 'plotly',
        'show_benchmark': True,
        'commission_rate': 0.001425,
        'commission_discount': 0.6,
        'tax_rate': 0.003,
    },
    StateKeys.THEME: 'light',
    StateKeys.SIDEBAR_STATE: 'expanded',
    StateKeys.CURRENT_PAGE: 'home',
    StateKeys.VIEW_MODE: 'table',
    StateKeys.PORTFOLIO: {},
    StateKeys.PORTFOLIO_NAME: None,
    StateKeys.ALERTS: [],
    StateKeys.TEMP_DATA: {},
    StateKeys.LAST_UPDATE: None,
}


# ========== 初始化函數 ==========

def init_session_state(keys: Optional[List[str]] = None, force: bool = False) -> None:
    """
    初始化 Session State

    Args:
        keys: 要初始化的鍵值列表，None 表示初始化所有預定義的鍵值
        force: 是否強制重新初始化（覆蓋現有值）

    Example:
        # 初始化所有預設鍵值
        init_session_state()

        # 只初始化特定鍵值
        init_session_state([StateKeys.SELECTED_STOCKS, StateKeys.WATCHLIST])

        # 強制重新初始化
        init_session_state(force=True)
    """
    if keys is None:
        keys = list(DEFAULT_VALUES.keys())

    for key in keys:
        if key in DEFAULT_VALUES:
            if force or key not in st.session_state:
                st.session_state[key] = _deep_copy(DEFAULT_VALUES[key])


def init_all() -> None:
    """初始化所有 Session State（簡化版）"""
    init_session_state()


# ========== 存取函數 ==========

T = TypeVar('T')


def get_state(key: str, default: Optional[T] = None) -> Optional[T]:
    """
    安全取得 Session State 值

    Args:
        key: Session State 鍵值
        default: 若鍵值不存在時的預設值

    Returns:
        Session State 中的值，若不存在則返回 default

    Example:
        stocks = get_state(StateKeys.SELECTED_STOCKS, [])
        strategy = get_state('selected_strategy', '價值投資')
    """
    if key in st.session_state:
        return st.session_state[key]

    # 嘗試從預設值取得
    if key in DEFAULT_VALUES and default is None:
        return _deep_copy(DEFAULT_VALUES[key])

    return default


def set_state(key: str, value: Any) -> None:
    """
    設定 Session State 值

    Args:
        key: Session State 鍵值
        value: 要設定的值

    Example:
        set_state(StateKeys.SELECTED_STOCKS, ['2330', '2454'])
        set_state('current_stock', '2330')
    """
    st.session_state[key] = value


def update_state(key: str, updates: Dict[str, Any]) -> None:
    """
    更新 Session State 中的字典類型值

    Args:
        key: Session State 鍵值
        updates: 要更新的鍵值對

    Example:
        update_state(StateKeys.USER_SETTINGS, {'default_period': '近1年'})
    """
    if key not in st.session_state:
        st.session_state[key] = {}

    if isinstance(st.session_state[key], dict):
        st.session_state[key].update(updates)
    else:
        raise TypeError(f"Session state '{key}' is not a dictionary")


def delete_state(key: str) -> bool:
    """
    刪除 Session State 值

    Args:
        key: Session State 鍵值

    Returns:
        是否成功刪除
    """
    if key in st.session_state:
        del st.session_state[key]
        return True
    return False


def clear_state(keys: Optional[List[str]] = None) -> None:
    """
    清除 Session State

    Args:
        keys: 要清除的鍵值列表，None 表示清除所有預定義的鍵值
    """
    if keys is None:
        keys = list(DEFAULT_VALUES.keys())

    for key in keys:
        if key in st.session_state:
            del st.session_state[key]


def reset_state(keys: Optional[List[str]] = None) -> None:
    """
    重置 Session State 為預設值

    Args:
        keys: 要重置的鍵值列表，None 表示重置所有預定義的鍵值
    """
    clear_state(keys)
    init_session_state(keys, force=True)


# ========== 特定功能函數 ==========

def add_selected_stock(stock_id: str) -> bool:
    """
    新增選中的股票

    Args:
        stock_id: 股票代號

    Returns:
        是否成功新增（若已存在則返回 False）
    """
    stocks = get_state(StateKeys.SELECTED_STOCKS, [])
    if stock_id not in stocks:
        stocks.append(stock_id)
        set_state(StateKeys.SELECTED_STOCKS, stocks)
        return True
    return False


def remove_selected_stock(stock_id: str) -> bool:
    """
    移除選中的股票

    Args:
        stock_id: 股票代號

    Returns:
        是否成功移除
    """
    stocks = get_state(StateKeys.SELECTED_STOCKS, [])
    if stock_id in stocks:
        stocks.remove(stock_id)
        set_state(StateKeys.SELECTED_STOCKS, stocks)
        return True
    return False


def clear_selected_stocks() -> None:
    """清除所有選中的股票"""
    set_state(StateKeys.SELECTED_STOCKS, [])


def set_analysis_result(key: str, result: Any) -> None:
    """
    儲存分析結果

    Args:
        key: 結果鍵值（如股票代號或分析類型）
        result: 分析結果
    """
    results = get_state(StateKeys.ANALYSIS_RESULTS, {})
    results[key] = {
        'data': result,
        'timestamp': datetime.now().isoformat(),
    }
    set_state(StateKeys.ANALYSIS_RESULTS, results)


def get_analysis_result(key: str, max_age_seconds: Optional[int] = None) -> Optional[Any]:
    """
    取得分析結果

    Args:
        key: 結果鍵值
        max_age_seconds: 最大快取時間（秒），超過則返回 None

    Returns:
        分析結果，若不存在或已過期則返回 None
    """
    results = get_state(StateKeys.ANALYSIS_RESULTS, {})

    if key not in results:
        return None

    result_entry = results[key]

    if max_age_seconds is not None:
        timestamp = datetime.fromisoformat(result_entry['timestamp'])
        age = (datetime.now() - timestamp).total_seconds()
        if age > max_age_seconds:
            return None

    return result_entry['data']


def get_user_setting(setting_key: str, default: Any = None) -> Any:
    """
    取得使用者設定

    Args:
        setting_key: 設定鍵值
        default: 預設值

    Returns:
        設定值
    """
    settings = get_state(StateKeys.USER_SETTINGS, {})
    return settings.get(setting_key, default)


def set_user_setting(setting_key: str, value: Any) -> None:
    """
    設定使用者設定

    Args:
        setting_key: 設定鍵值
        value: 設定值
    """
    update_state(StateKeys.USER_SETTINGS, {setting_key: value})


# ========== 跨頁面資料傳遞 ==========

def navigate_to_stock_analysis(stock_id: str) -> None:
    """
    設定要分析的股票並導航到個股分析頁面

    Args:
        stock_id: 股票代號
    """
    set_state(StateKeys.ANALYZE_STOCK, stock_id)


def get_stock_to_analyze() -> Optional[str]:
    """
    取得並清除要分析的股票

    Returns:
        股票代號，若無則返回 None
    """
    stock_id = get_state(StateKeys.ANALYZE_STOCK)
    if stock_id:
        delete_state(StateKeys.ANALYZE_STOCK)
    return stock_id


def pass_screening_results(results: Any) -> None:
    """
    傳遞選股結果到其他頁面

    Args:
        results: 選股結果
    """
    set_state(StateKeys.SCREENING_RESULTS, results)
    set_state(StateKeys.LAST_UPDATE, datetime.now().isoformat())


def get_screening_results() -> Optional[Any]:
    """
    取得選股結果

    Returns:
        選股結果
    """
    return get_state(StateKeys.SCREENING_RESULTS)


def pass_optimized_params(strategy_type: str, params: Dict[str, Any]) -> None:
    """
    傳遞優化後的參數到選股頁面

    Args:
        strategy_type: 策略類型
        params: 優化後的參數
    """
    set_state(StateKeys.APPLY_OPTIMIZED_PARAMS, {
        'strategy_type': strategy_type,
        'params': params,
    })


# ========== 工具函數 ==========

def _deep_copy(obj: Any) -> Any:
    """深拷貝物件"""
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_copy(item) for item in obj]
    elif isinstance(obj, set):
        return {_deep_copy(item) for item in obj}
    else:
        return obj


def has_state(key: str) -> bool:
    """
    檢查 Session State 是否存在

    Args:
        key: Session State 鍵值

    Returns:
        是否存在
    """
    return key in st.session_state


def get_all_states() -> Dict[str, Any]:
    """
    取得所有預定義的 Session State

    Returns:
        所有預定義鍵值的當前狀態
    """
    return {key: get_state(key) for key in DEFAULT_VALUES.keys()}


def debug_state() -> None:
    """在側邊欄顯示 Session State 除錯資訊（開發用）"""
    with st.sidebar.expander("🔧 Session State Debug"):
        for key in sorted(DEFAULT_VALUES.keys()):
            value = get_state(key)
            st.text(f"{key}: {type(value).__name__}")
            if isinstance(value, (list, dict)):
                st.json(value if len(str(value)) < 500 else f"[{len(value)} items]")
            else:
                st.write(value)
