"""
績效指標計算模組
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """績效指標結構"""
    total_return: float           # 總報酬率 (%)
    annualized_return: float      # 年化報酬率 (%)
    volatility: float             # 年化波動率 (%)
    sharpe_ratio: float           # 夏普比率
    sortino_ratio: float          # 索提諾比率
    max_drawdown: float           # 最大回撤 (%)
    max_drawdown_duration: int    # 最大回撤持續天數
    win_rate: float               # 勝率 (%)
    profit_factor: float          # 獲利因子
    total_trades: int             # 總交易次數
    avg_holding_days: float       # 平均持股天數
    calmar_ratio: float           # 卡瑪比率


def calculate_returns(portfolio_values: pd.Series) -> pd.Series:
    """計算日報酬率"""
    return portfolio_values.pct_change().fillna(0)


def calculate_cumulative_returns(portfolio_values: pd.Series) -> pd.Series:
    """計算累積報酬率"""
    return (portfolio_values / portfolio_values.iloc[0]) - 1


def calculate_total_return(portfolio_values: pd.Series) -> float:
    """計算總報酬率 (%)"""
    if len(portfolio_values) < 2:
        return 0.0
    return ((portfolio_values.iloc[-1] / portfolio_values.iloc[0]) - 1) * 100


def calculate_annualized_return(portfolio_values: pd.Series) -> float:
    """計算年化報酬率 (%)"""
    if len(portfolio_values) < 2:
        return 0.0

    total_days = (portfolio_values.index[-1] - portfolio_values.index[0]).days
    if total_days <= 0:
        return 0.0

    total_return = portfolio_values.iloc[-1] / portfolio_values.iloc[0]
    years = total_days / 365.0
    annualized = (total_return ** (1 / years)) - 1

    return annualized * 100


def calculate_volatility(portfolio_values: pd.Series, annualize: bool = True) -> float:
    """計算波動率 (%)"""
    if len(portfolio_values) < 2:
        return 0.0

    returns = calculate_returns(portfolio_values)
    vol = returns.std()

    # 安全檢查
    if np.isnan(vol) or np.isinf(vol):
        return 0.0

    if annualize:
        vol = vol * np.sqrt(252)

    return vol * 100


def calculate_sharpe_ratio(portfolio_values: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    計算夏普比率

    Parameters:
    -----------
    portfolio_values : pd.Series
        投資組合淨值序列
    risk_free_rate : float
        無風險利率 (年化)
    """
    if len(portfolio_values) < 2:
        return 0.0

    annualized_return = calculate_annualized_return(portfolio_values) / 100
    volatility = calculate_volatility(portfolio_values) / 100

    # 安全檢查：處理零波動率或 NaN
    if volatility == 0 or np.isnan(volatility) or np.isinf(volatility):
        return 0.0

    result = (annualized_return - risk_free_rate) / volatility

    # 處理結果為 NaN 或 Inf 的情況
    if np.isnan(result) or np.isinf(result):
        return 0.0

    return result


def calculate_sortino_ratio(portfolio_values: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    計算索提諾比率 (只考慮下行風險)
    """
    if len(portfolio_values) < 2:
        return 0.0

    returns = calculate_returns(portfolio_values)
    annualized_return = calculate_annualized_return(portfolio_values) / 100

    # 只計算負報酬的標準差
    downside_returns = returns[returns < 0]
    if len(downside_returns) == 0:
        # 沒有負報酬，回傳正無限大但設定上限避免顯示問題
        return 999.99

    downside_std = downside_returns.std() * np.sqrt(252)

    # 安全檢查
    if downside_std == 0 or np.isnan(downside_std) or np.isinf(downside_std):
        return 999.99

    result = (annualized_return - risk_free_rate) / downside_std

    # 處理結果為 NaN 或 Inf 的情況
    if np.isnan(result) or np.isinf(result):
        return 999.99 if result > 0 or np.isnan(result) else -999.99

    return result


def calculate_max_drawdown(portfolio_values: pd.Series) -> tuple:
    """
    計算最大回撤

    Returns:
    --------
    tuple
        (最大回撤百分比, 最大回撤持續天數, 回撤序列)
    """
    rolling_max = portfolio_values.cummax()
    drawdown = (portfolio_values - rolling_max) / rolling_max

    max_dd = drawdown.min() * 100

    # 計算最大回撤持續天數
    is_drawdown = drawdown < 0
    drawdown_periods = []
    current_start = None

    for i, (date, is_dd) in enumerate(is_drawdown.items()):
        if is_dd and current_start is None:
            current_start = date
        elif not is_dd and current_start is not None:
            drawdown_periods.append((current_start, date))
            current_start = None

    if current_start is not None:
        drawdown_periods.append((current_start, portfolio_values.index[-1]))

    max_duration = 0
    for start, end in drawdown_periods:
        duration = (end - start).days
        max_duration = max(max_duration, duration)

    return max_dd, max_duration, drawdown


def calculate_win_rate(trades: pd.DataFrame) -> float:
    """
    計算勝率

    Parameters:
    -----------
    trades : pd.DataFrame
        交易記錄，需有 'return' 欄位
    """
    if len(trades) == 0:
        return 0.0

    winning_trades = (trades['return'] > 0).sum()
    return (winning_trades / len(trades)) * 100


def calculate_profit_factor(trades: pd.DataFrame) -> float:
    """
    計算獲利因子 (總獲利 / 總虧損)
    """
    if len(trades) == 0:
        return 0.0

    profits = trades[trades['return'] > 0]['return'].sum()
    losses = abs(trades[trades['return'] < 0]['return'].sum())

    if losses == 0:
        return float('inf') if profits > 0 else 0.0

    return profits / losses


def calculate_calmar_ratio(portfolio_values: pd.Series) -> float:
    """計算卡瑪比率 (年化報酬 / 最大回撤)"""
    if len(portfolio_values) < 2:
        return 0.0

    annualized_return = calculate_annualized_return(portfolio_values)
    max_dd, _, _ = calculate_max_drawdown(portfolio_values)

    # 安全檢查
    if max_dd == 0 or np.isnan(max_dd):
        return 999.99 if annualized_return > 0 else 0.0

    result = annualized_return / abs(max_dd)

    # 處理結果為 NaN 或 Inf 的情況
    if np.isnan(result) or np.isinf(result):
        return 999.99 if result > 0 or np.isnan(result) else -999.99

    return result


def calculate_metrics(portfolio_values: pd.Series,
                     trades: Optional[pd.DataFrame] = None,
                     risk_free_rate: float = 0.02) -> PerformanceMetrics:
    """
    計算完整績效指標

    Parameters:
    -----------
    portfolio_values : pd.Series
        投資組合淨值序列
    trades : pd.DataFrame, optional
        交易記錄
    risk_free_rate : float
        無風險利率

    Returns:
    --------
    PerformanceMetrics
        績效指標結構
    """
    max_dd, max_dd_duration, _ = calculate_max_drawdown(portfolio_values)

    if trades is not None and len(trades) > 0:
        win_rate = calculate_win_rate(trades)
        profit_factor = calculate_profit_factor(trades)
        total_trades = len(trades)
        avg_holding = trades['holding_days'].mean() if 'holding_days' in trades.columns else 0
    else:
        win_rate = 0.0
        profit_factor = 0.0
        total_trades = 0
        avg_holding = 0.0

    return PerformanceMetrics(
        total_return=calculate_total_return(portfolio_values),
        annualized_return=calculate_annualized_return(portfolio_values),
        volatility=calculate_volatility(portfolio_values),
        sharpe_ratio=calculate_sharpe_ratio(portfolio_values, risk_free_rate),
        sortino_ratio=calculate_sortino_ratio(portfolio_values, risk_free_rate),
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_duration,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        avg_holding_days=avg_holding,
        calmar_ratio=calculate_calmar_ratio(portfolio_values),
    )


def compare_with_benchmark(portfolio_values: pd.Series,
                           benchmark_values: pd.Series) -> Dict[str, Any]:
    """
    與大盤比較績效

    Returns:
    --------
    dict
        包含超額報酬、beta、alpha 等比較指標
    """
    # 對齊日期
    common_dates = portfolio_values.index.intersection(benchmark_values.index)
    portfolio = portfolio_values.loc[common_dates]
    benchmark = benchmark_values.loc[common_dates]

    # 計算報酬率
    portfolio_returns = calculate_returns(portfolio)
    benchmark_returns = calculate_returns(benchmark)

    # 超額報酬
    excess_return = (calculate_total_return(portfolio) -
                    calculate_total_return(benchmark))

    # Beta 計算
    covariance = portfolio_returns.cov(benchmark_returns)
    benchmark_variance = benchmark_returns.var()
    beta = covariance / benchmark_variance if benchmark_variance != 0 else 0

    # Alpha 計算 (Jensen's Alpha)
    portfolio_ann_return = calculate_annualized_return(portfolio) / 100
    benchmark_ann_return = calculate_annualized_return(benchmark) / 100
    risk_free_rate = 0.02

    alpha = portfolio_ann_return - (risk_free_rate + beta * (benchmark_ann_return - risk_free_rate))

    # Information Ratio
    tracking_error = (portfolio_returns - benchmark_returns).std() * np.sqrt(252)
    information_ratio = (portfolio_ann_return - benchmark_ann_return) / tracking_error if tracking_error != 0 else 0

    return {
        'excess_return': excess_return,
        'beta': beta,
        'alpha': alpha * 100,  # 轉為百分比
        'information_ratio': information_ratio,
        'correlation': portfolio_returns.corr(benchmark_returns),
        'tracking_error': tracking_error * 100,
    }
