# -*- coding: utf-8 -*-
"""
統一錯誤處理元件

提供一致的錯誤顯示、日誌記錄和回報機制
"""
import streamlit as st
import traceback
import logging
from datetime import datetime
from typing import Callable, Any
from functools import wraps

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('finlab_app')


class AppError(Exception):
    """應用程式錯誤基類"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or 'UNKNOWN'
        self.details = details or {}
        self.timestamp = datetime.now()
        super().__init__(self.message)


class DataLoadError(AppError):
    """資料載入錯誤"""
    def __init__(self, message: str, data_key: str = None):
        super().__init__(
            message,
            error_code='DATA_LOAD_ERROR',
            details={'data_key': data_key}
        )


class APIError(AppError):
    """API 呼叫錯誤"""
    def __init__(self, message: str, api_name: str = None, status_code: int = None):
        super().__init__(
            message,
            error_code='API_ERROR',
            details={'api_name': api_name, 'status_code': status_code}
        )


class ValidationError(AppError):
    """驗證錯誤"""
    def __init__(self, message: str, field: str = None):
        super().__init__(
            message,
            error_code='VALIDATION_ERROR',
            details={'field': field}
        )


def show_error(
    error: Exception,
    title: str = "發生錯誤",
    show_details: bool = True,
    show_traceback: bool = False,
    suggestion: str = None
):
    """
    顯示統一格式的錯誤訊息

    Parameters:
    -----------
    error : Exception
        錯誤物件
    title : str
        錯誤標題
    show_details : bool
        是否顯示錯誤詳情
    show_traceback : bool
        是否顯示完整堆疊追蹤
    suggestion : str
        建議的解決方案
    """
    # 記錄錯誤
    logger.error(f"{title}: {str(error)}", exc_info=True)

    # 判斷錯誤類型並設定圖示
    if isinstance(error, DataLoadError):
        icon = "📊"
        error_type = "資料載入錯誤"
    elif isinstance(error, APIError):
        icon = "🌐"
        error_type = "API 連線錯誤"
    elif isinstance(error, ValidationError):
        icon = "⚠️"
        error_type = "驗證錯誤"
    else:
        icon = "❌"
        error_type = "系統錯誤"

    # 顯示錯誤
    with st.container():
        st.error(f"{icon} **{title}**")

        if show_details:
            with st.expander("查看錯誤詳情", expanded=False):
                st.markdown(f"**錯誤類型:** {error_type}")
                st.markdown(f"**錯誤訊息:** {str(error)}")

                if isinstance(error, AppError):
                    st.markdown(f"**錯誤代碼:** {error.error_code}")
                    if error.details:
                        st.markdown("**詳細資訊:**")
                        st.json(error.details)

                if show_traceback:
                    st.markdown("**堆疊追蹤:**")
                    st.code(traceback.format_exc(), language='python')

        if suggestion:
            st.info(f"💡 **建議:** {suggestion}")


def show_warning(message: str, details: str = None):
    """顯示警告訊息"""
    st.warning(f"⚠️ {message}")
    if details:
        with st.expander("詳細資訊"):
            st.markdown(details)


def show_info(message: str):
    """顯示資訊訊息"""
    st.info(f"ℹ️ {message}")


def show_success(message: str):
    """顯示成功訊息"""
    st.success(f"✅ {message}")


def handle_error(
    default_return: Any = None,
    error_title: str = "操作失敗",
    suggestion: str = None,
    reraise: bool = False
):
    """
    錯誤處理裝飾器

    Parameters:
    -----------
    default_return : Any
        發生錯誤時的預設回傳值
    error_title : str
        錯誤標題
    suggestion : str
        建議的解決方案
    reraise : bool
        是否重新拋出錯誤

    Usage:
    ------
    @handle_error(default_return=[], error_title="載入資料失敗")
    def load_data():
        ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                show_error(e, title=error_title, suggestion=suggestion)
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    error_title: str = "操作失敗",
    suggestion: str = None,
    show_error_ui: bool = True,
    **kwargs
) -> Any:
    """
    安全執行函數

    Parameters:
    -----------
    func : Callable
        要執行的函數
    default_return : Any
        發生錯誤時的預設回傳值
    error_title : str
        錯誤標題
    suggestion : str
        建議的解決方案
    show_error_ui : bool
        是否顯示錯誤 UI

    Returns:
    --------
    Any
        函數回傳值或預設值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if show_error_ui:
            show_error(e, title=error_title, suggestion=suggestion)
        else:
            logger.error(f"{error_title}: {str(e)}", exc_info=True)
        return default_return


def create_error_boundary(component_name: str = "元件"):
    """
    建立錯誤邊界 context manager

    Usage:
    ------
    with create_error_boundary("圖表"):
        # 可能出錯的程式碼
        create_chart(data)
    """
    class ErrorBoundary:
        def __init__(self, name: str):
            self.name = name

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                show_error(
                    exc_val,
                    title=f"{self.name}載入失敗",
                    suggestion="請嘗試重新整理頁面，或檢查資料是否正確"
                )
                return True  # 抑制錯誤
            return False

    return ErrorBoundary(component_name)


def retry_on_error(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    error_types: tuple = (Exception,)
):
    """
    重試裝飾器

    Parameters:
    -----------
    max_retries : int
        最大重試次數
    delay_seconds : float
        重試間隔秒數
    error_types : tuple
        要重試的錯誤類型
    """
    import time

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except error_types as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"第 {attempt + 1} 次嘗試失敗，{delay_seconds} 秒後重試...")
                        time.sleep(delay_seconds)
            raise last_error
        return wrapper
    return decorator


# 常用錯誤訊息模板
ERROR_MESSAGES = {
    'data_not_found': "找不到所需的資料，請確認資料檔案是否存在",
    'network_error': "網路連線錯誤，請檢查網路狀態後重試",
    'invalid_input': "輸入資料格式不正確，請檢查後重新輸入",
    'permission_denied': "沒有權限執行此操作",
    'timeout': "操作逾時，請稍後再試",
    'server_error': "伺服器錯誤，請稍後再試",
    'unknown': "發生未知錯誤，請聯繫系統管理員",
}

# 建議解決方案模板
SUGGESTIONS = {
    'refresh': "請嘗試重新整理頁面",
    'clear_cache': "請嘗試清除快取後重試",
    'check_network': "請檢查網路連線狀態",
    'contact_admin': "如果問題持續，請聯繫系統管理員",
    'retry_later': "請稍後再試",
}
