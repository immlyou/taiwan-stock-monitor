"""
參數驗證器模組
"""
from typing import Any, Dict, List, Optional, Type, Union
from .exceptions import (
    ParameterValidationError,
    ParameterRangeError,
    ParameterTypeError,
    ParameterConflictError,
)


class ParameterValidator:
    """參數驗證器"""

    @staticmethod
    def validate_type(value: Any, expected_type: Type, param_name: str) -> None:
        """
        驗證參數類型

        Parameters:
        -----------
        value : Any
            參數值
        expected_type : Type
            預期類型
        param_name : str
            參數名稱

        Raises:
        -------
        ParameterTypeError
            類型不符時拋出
        """
        if not isinstance(value, expected_type):
            raise ParameterTypeError(
                param_name,
                expected_type.__name__,
                type(value).__name__
            )

    @staticmethod
    def validate_range(value: Union[int, float],
                       param_name: str,
                       min_val: Optional[Union[int, float]] = None,
                       max_val: Optional[Union[int, float]] = None) -> None:
        """
        驗證參數範圍

        Parameters:
        -----------
        value : int or float
            參數值
        param_name : str
            參數名稱
        min_val : int or float, optional
            最小值
        max_val : int or float, optional
            最大值

        Raises:
        -------
        ParameterRangeError
            超出範圍時拋出
        """
        if min_val is not None and value < min_val:
            raise ParameterRangeError(param_name, value, min_val, max_val)
        if max_val is not None and value > max_val:
            raise ParameterRangeError(param_name, value, min_val, max_val)

    @staticmethod
    def validate_positive(value: Union[int, float], param_name: str) -> None:
        """驗證參數為正數"""
        if value <= 0:
            raise ParameterRangeError(param_name, value, min_val=0)

    @staticmethod
    def validate_non_negative(value: Union[int, float], param_name: str) -> None:
        """驗證參數為非負數"""
        if value < 0:
            raise ParameterRangeError(param_name, value, min_val=0)

    @staticmethod
    def validate_percentage(value: Union[int, float], param_name: str) -> None:
        """驗證參數為百分比 (0-100)"""
        if value < 0 or value > 100:
            raise ParameterRangeError(param_name, value, 0, 100)

    @staticmethod
    def validate_not_empty(value: Any, param_name: str) -> None:
        """驗證參數不為空"""
        if value is None or (hasattr(value, '__len__') and len(value) == 0):
            raise ParameterValidationError(param_name, value, "不可為空")

    @staticmethod
    def validate_in_list(value: Any, allowed_values: List, param_name: str) -> None:
        """驗證參數在允許的值列表中"""
        if value not in allowed_values:
            raise ParameterValidationError(
                param_name,
                value,
                f"必須是以下其中之一: {allowed_values}"
            )


class StrategyParamsValidator:
    """策略參數驗證器"""

    # 參數定義：{參數名: (類型, 最小值, 最大值, 預設值, 描述)}
    VALUE_PARAMS = {
        'pe_max': (float, 1.0, 100.0, 15.0, '本益比上限'),
        'pb_max': (float, 0.1, 10.0, 1.5, '股價淨值比上限'),
        'dividend_yield_min': (float, 0.0, 20.0, 4.0, '殖利率下限 (%)'),
    }

    GROWTH_PARAMS = {
        'revenue_yoy_min': (float, -100.0, 500.0, 20.0, '年增率下限 (%)'),
        'revenue_mom_min': (float, -100.0, 500.0, 10.0, '月增率下限 (%)'),
        'consecutive_months': (int, 1, 12, 3, '連續成長月數'),
    }

    MOMENTUM_PARAMS = {
        'breakout_days': (int, 5, 252, 20, '突破天數'),
        'volume_ratio': (float, 0.5, 10.0, 1.5, '成交量比'),
        'rsi_min': (int, 0, 100, 50, 'RSI 下限'),
        'rsi_max': (int, 0, 100, 80, 'RSI 上限'),
    }

    BACKTEST_PARAMS = {
        'initial_capital': (float, 10000, 1e10, 1000000, '初始資金'),
        'max_stocks': (int, 1, 100, 10, '最大持股數'),
        'commission_rate': (float, 0.0, 0.01, 0.001425, '手續費率'),
        'tax_rate': (float, 0.0, 0.01, 0.003, '交易稅率'),
        'discount': (float, 0.1, 1.0, 0.6, '手續費折扣'),
    }

    @classmethod
    def validate_value_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """驗證價值策略參數"""
        return cls._validate_params(params, cls.VALUE_PARAMS)

    @classmethod
    def validate_growth_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """驗證成長策略參數"""
        return cls._validate_params(params, cls.GROWTH_PARAMS)

    @classmethod
    def validate_momentum_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """驗證動能策略參數"""
        validated = cls._validate_params(params, cls.MOMENTUM_PARAMS)

        # 額外檢查：RSI 下限不能大於上限
        if validated.get('rsi_min', 0) >= validated.get('rsi_max', 100):
            raise ParameterConflictError(
                {'rsi_min': validated.get('rsi_min'), 'rsi_max': validated.get('rsi_max')},
                'RSI 下限必須小於上限'
            )

        return validated

    @classmethod
    def validate_backtest_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """驗證回測參數"""
        return cls._validate_params(params, cls.BACKTEST_PARAMS)

    @classmethod
    def _validate_params(cls, params: Dict[str, Any],
                         param_defs: Dict[str, tuple]) -> Dict[str, Any]:
        """
        通用參數驗證

        Parameters:
        -----------
        params : dict
            待驗證參數
        param_defs : dict
            參數定義

        Returns:
        --------
        dict
            驗證後的參數（含預設值）
        """
        validated = {}

        for param_name, (expected_type, min_val, max_val, default, desc) in param_defs.items():
            value = params.get(param_name, default)

            # 類型轉換
            try:
                value = expected_type(value)
            except (ValueError, TypeError):
                raise ParameterTypeError(param_name, expected_type.__name__, type(value).__name__)

            # 範圍驗證
            ParameterValidator.validate_range(value, param_name, min_val, max_val)

            validated[param_name] = value

        return validated


def validate_date_range(start_date, end_date) -> None:
    """
    驗證日期範圍

    Raises:
    -------
    ParameterConflictError
        結束日期早於開始日期時拋出
    """
    import pandas as pd

    if start_date is None or end_date is None:
        return

    start = pd.Timestamp(start_date) if not isinstance(start_date, pd.Timestamp) else start_date
    end = pd.Timestamp(end_date) if not isinstance(end_date, pd.Timestamp) else end_date

    if end < start:
        raise ParameterConflictError(
            {'start_date': str(start), 'end_date': str(end)},
            '結束日期不能早於開始日期'
        )


def validate_stock_list(stocks: List[str], param_name: str = 'stocks') -> None:
    """
    驗證股票列表

    Raises:
    -------
    ParameterValidationError
        列表為空或格式錯誤時拋出
    """
    ParameterValidator.validate_not_empty(stocks, param_name)

    for stock in stocks:
        if not isinstance(stock, str) or len(stock) < 1:
            raise ParameterValidationError(
                param_name,
                stock,
                '股票代號必須是非空字串'
            )
