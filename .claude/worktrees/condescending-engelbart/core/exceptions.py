"""
自訂異常類別
"""


class FinlabBaseException(Exception):
    """基礎異常類別"""
    pass


# ============== 數據相關異常 ==============

class DataException(FinlabBaseException):
    """數據相關異常基礎類別"""
    pass


class DataNotFoundError(DataException):
    """數據檔案不存在"""

    def __init__(self, data_key: str, filepath: str = None):
        self.data_key = data_key
        self.filepath = filepath
        message = f"找不到數據: {data_key}"
        if filepath:
            message += f" (路徑: {filepath})"
        super().__init__(message)


class DataLoadError(DataException):
    """數據載入失敗"""

    def __init__(self, data_key: str, reason: str = None):
        self.data_key = data_key
        self.reason = reason
        message = f"載入數據失敗: {data_key}"
        if reason:
            message += f" - {reason}"
        super().__init__(message)


class DataFormatError(DataException):
    """數據格式錯誤"""

    def __init__(self, data_key: str, expected: str, actual: str):
        self.data_key = data_key
        self.expected = expected
        self.actual = actual
        super().__init__(f"數據格式錯誤: {data_key} - 預期 {expected}，實際 {actual}")


# ============== 參數驗證異常 ==============

class ValidationException(FinlabBaseException):
    """參數驗證異常基礎類別"""
    pass


class ParameterValidationError(ValidationException):
    """參數驗證失敗"""

    def __init__(self, param_name: str, value, message: str = None):
        self.param_name = param_name
        self.value = value
        self.message = message
        error_msg = f"參數驗證失敗: {param_name}={value}"
        if message:
            error_msg += f" - {message}"
        super().__init__(error_msg)


class ParameterRangeError(ValidationException):
    """參數超出範圍"""

    def __init__(self, param_name: str, value, min_val=None, max_val=None):
        self.param_name = param_name
        self.value = value
        self.min_val = min_val
        self.max_val = max_val

        if min_val is not None and max_val is not None:
            message = f"參數 {param_name}={value} 超出範圍 [{min_val}, {max_val}]"
        elif min_val is not None:
            message = f"參數 {param_name}={value} 必須大於等於 {min_val}"
        elif max_val is not None:
            message = f"參數 {param_name}={value} 必須小於等於 {max_val}"
        else:
            message = f"參數 {param_name}={value} 超出範圍"

        super().__init__(message)


class ParameterTypeError(ValidationException):
    """參數類型錯誤"""

    def __init__(self, param_name: str, expected_type: str, actual_type: str):
        self.param_name = param_name
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(f"參數類型錯誤: {param_name} 預期 {expected_type}，實際 {actual_type}")


class ParameterConflictError(ValidationException):
    """參數邏輯衝突"""

    def __init__(self, params: dict, message: str):
        self.params = params
        super().__init__(f"參數衝突: {message} - {params}")


# ============== 策略相關異常 ==============

class StrategyException(FinlabBaseException):
    """策略相關異常基礎類別"""
    pass


class StrategyExecutionError(StrategyException):
    """策略執行失敗"""

    def __init__(self, strategy_name: str, reason: str = None):
        self.strategy_name = strategy_name
        self.reason = reason
        message = f"策略執行失敗: {strategy_name}"
        if reason:
            message += f" - {reason}"
        super().__init__(message)


class InsufficientDataError(StrategyException):
    """數據不足"""

    def __init__(self, strategy_name: str, required_data: list, missing_data: list):
        self.strategy_name = strategy_name
        self.required_data = required_data
        self.missing_data = missing_data
        super().__init__(
            f"策略 {strategy_name} 數據不足 - 缺少: {', '.join(missing_data)}"
        )


# ============== 回測相關異常 ==============

class BacktestException(FinlabBaseException):
    """回測相關異常基礎類別"""
    pass


class BacktestConfigError(BacktestException):
    """回測配置錯誤"""

    def __init__(self, message: str):
        super().__init__(f"回測配置錯誤: {message}")


class InsufficientCapitalError(BacktestException):
    """資金不足"""

    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f"資金不足: 需要 {required:,.0f}，可用 {available:,.0f}")


# ============== 通知相關異常 ==============

class NotificationException(FinlabBaseException):
    """通知相關異常基礎類別"""
    pass


class NotificationSendError(NotificationException):
    """通知發送失敗"""

    def __init__(self, channel: str, reason: str = None):
        self.channel = channel
        self.reason = reason
        message = f"通知發送失敗 ({channel})"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class NotificationConfigError(NotificationException):
    """通知配置錯誤"""

    def __init__(self, channel: str, message: str):
        self.channel = channel
        super().__init__(f"通知配置錯誤 ({channel}): {message}")
