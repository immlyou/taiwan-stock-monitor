"""
風險分析模組 - VaR、CVaR 及投資組合風險評估
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass


@dataclass
class RiskMetrics:
    """風險指標結構"""
    var_95: float              # 95% VaR
    var_99: float              # 99% VaR
    cvar_95: float             # 95% CVaR (條件風險值)
    cvar_99: float             # 99% CVaR
    volatility: float          # 年化波動率
    downside_volatility: float # 下行波動率
    max_drawdown: float        # 最大回撤
    beta: Optional[float]      # Beta 值
    tracking_error: Optional[float]  # 追蹤誤差


class RiskAnalyzer:
    """
    風險分析器

    提供多種風險評估方法:
    - VaR (Value at Risk) - 風險值
    - CVaR (Conditional VaR) - 條件風險值
    - 波動率分析
    - Beta 與追蹤誤差
    """

    def __init__(self, confidence_levels: List[float] = None):
        """
        Parameters:
        -----------
        confidence_levels : list, optional
            信心水準列表，預設 [0.95, 0.99]
        """
        self.confidence_levels = confidence_levels or [0.95, 0.99]

    def calculate_returns(self, prices: pd.Series) -> pd.Series:
        """計算日報酬率"""
        return prices.pct_change().dropna()

    def calculate_var_historical(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        歷史模擬法 VaR

        Parameters:
        -----------
        returns : pd.Series
            報酬率序列
        confidence : float
            信心水準

        Returns:
        --------
        float
            VaR 值（負數表示損失）
        """
        if len(returns) == 0:
            return 0.0

        return np.percentile(returns, (1 - confidence) * 100)

    def calculate_var_parametric(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        參數法 VaR (假設常態分佈)

        Parameters:
        -----------
        returns : pd.Series
            報酬率序列
        confidence : float
            信心水準

        Returns:
        --------
        float
            VaR 值
        """
        if len(returns) == 0:
            return 0.0

        from scipy import stats

        mean = returns.mean()
        std = returns.std()

        z_score = stats.norm.ppf(1 - confidence)
        return mean + z_score * std

    def calculate_cvar(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        條件風險值 CVaR (Expected Shortfall)

        比 VaR 更保守，計算超過 VaR 的平均損失

        Parameters:
        -----------
        returns : pd.Series
            報酬率序列
        confidence : float
            信心水準

        Returns:
        --------
        float
            CVaR 值
        """
        if len(returns) == 0:
            return 0.0

        var = self.calculate_var_historical(returns, confidence)
        # 取得低於 VaR 的所有報酬並計算平均
        tail_returns = returns[returns <= var]

        if len(tail_returns) == 0:
            return var

        return tail_returns.mean()

    def calculate_volatility(self, returns: pd.Series, annualize: bool = True) -> float:
        """
        計算波動率

        Parameters:
        -----------
        returns : pd.Series
            報酬率序列
        annualize : bool
            是否年化

        Returns:
        --------
        float
            波動率
        """
        if len(returns) == 0:
            return 0.0

        vol = returns.std()

        if annualize:
            vol *= np.sqrt(252)

        return vol

    def calculate_downside_volatility(self, returns: pd.Series, threshold: float = 0,
                                       annualize: bool = True) -> float:
        """
        計算下行波動率

        只考慮低於閾值的報酬

        Parameters:
        -----------
        returns : pd.Series
            報酬率序列
        threshold : float
            閾值，預設為 0
        annualize : bool
            是否年化

        Returns:
        --------
        float
            下行波動率
        """
        if len(returns) == 0:
            return 0.0

        downside_returns = returns[returns < threshold]

        if len(downside_returns) == 0:
            return 0.0

        vol = np.sqrt(np.mean(downside_returns ** 2))

        if annualize:
            vol *= np.sqrt(252)

        return vol

    def calculate_max_drawdown(self, prices: pd.Series) -> Tuple[float, pd.Timestamp, pd.Timestamp]:
        """
        計算最大回撤

        Returns:
        --------
        tuple
            (最大回撤, 峰值日期, 谷值日期)
        """
        if len(prices) == 0:
            return 0.0, None, None

        rolling_max = prices.cummax()
        drawdown = (prices - rolling_max) / rolling_max

        max_dd = drawdown.min()
        max_dd_date = drawdown.idxmin()

        # 找到峰值日期
        peak_date = prices[:max_dd_date].idxmax()

        return max_dd, peak_date, max_dd_date

    def calculate_beta(self, portfolio_returns: pd.Series,
                       benchmark_returns: pd.Series) -> float:
        """
        計算 Beta 值

        Parameters:
        -----------
        portfolio_returns : pd.Series
            投資組合報酬率
        benchmark_returns : pd.Series
            基準報酬率

        Returns:
        --------
        float
            Beta 值
        """
        # 對齊日期
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()

        if len(aligned) < 2:
            return 1.0

        covariance = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
        variance = aligned.iloc[:, 1].var()

        if variance == 0 or np.isnan(variance):
            return 1.0

        return covariance / variance

    def calculate_tracking_error(self, portfolio_returns: pd.Series,
                                  benchmark_returns: pd.Series,
                                  annualize: bool = True) -> float:
        """
        計算追蹤誤差

        Parameters:
        -----------
        portfolio_returns : pd.Series
            投資組合報酬率
        benchmark_returns : pd.Series
            基準報酬率
        annualize : bool
            是否年化

        Returns:
        --------
        float
            追蹤誤差
        """
        # 對齊日期
        aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()

        if len(aligned) < 2:
            return 0.0

        diff = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        te = diff.std()

        if annualize:
            te *= np.sqrt(252)

        return te

    def analyze(self, prices: pd.Series,
                benchmark_prices: Optional[pd.Series] = None) -> RiskMetrics:
        """
        完整風險分析

        Parameters:
        -----------
        prices : pd.Series
            價格序列
        benchmark_prices : pd.Series, optional
            基準價格序列

        Returns:
        --------
        RiskMetrics
            風險指標結構
        """
        returns = self.calculate_returns(prices)

        beta = None
        tracking_error = None

        if benchmark_prices is not None:
            benchmark_returns = self.calculate_returns(benchmark_prices)
            beta = self.calculate_beta(returns, benchmark_returns)
            tracking_error = self.calculate_tracking_error(returns, benchmark_returns)

        max_dd, _, _ = self.calculate_max_drawdown(prices)

        return RiskMetrics(
            var_95=self.calculate_var_historical(returns, 0.95) * 100,
            var_99=self.calculate_var_historical(returns, 0.99) * 100,
            cvar_95=self.calculate_cvar(returns, 0.95) * 100,
            cvar_99=self.calculate_cvar(returns, 0.99) * 100,
            volatility=self.calculate_volatility(returns) * 100,
            downside_volatility=self.calculate_downside_volatility(returns) * 100,
            max_drawdown=max_dd * 100,
            beta=beta,
            tracking_error=tracking_error * 100 if tracking_error else None,
        )


def calculate_portfolio_var(weights: Dict[str, float],
                            returns_df: pd.DataFrame,
                            confidence: float = 0.95,
                            method: str = 'historical') -> float:
    """
    計算投資組合 VaR

    Parameters:
    -----------
    weights : dict
        權重字典 {股票代號: 權重}
    returns_df : pd.DataFrame
        報酬率 DataFrame
    confidence : float
        信心水準
    method : str
        計算方法: 'historical' 或 'parametric'

    Returns:
    --------
    float
        投資組合 VaR
    """
    # 取得共同股票
    common_stocks = [s for s in weights.keys() if s in returns_df.columns]

    if not common_stocks:
        return 0.0

    # 計算投資組合報酬
    weight_series = pd.Series({s: weights[s] for s in common_stocks})
    weight_series = weight_series / weight_series.sum()  # 正規化權重

    portfolio_returns = (returns_df[common_stocks] * weight_series).sum(axis=1)

    analyzer = RiskAnalyzer()

    if method == 'parametric':
        return analyzer.calculate_var_parametric(portfolio_returns, confidence)
    else:
        return analyzer.calculate_var_historical(portfolio_returns, confidence)


def stress_test(prices: pd.Series, scenarios: Dict[str, float]) -> Dict[str, float]:
    """
    壓力測試

    Parameters:
    -----------
    prices : pd.Series
        價格序列
    scenarios : dict
        情境字典 {情境名稱: 價格變動百分比}
        例如: {'大跌': -0.20, '中度下跌': -0.10, '上漲': 0.10}

    Returns:
    --------
    dict
        各情境下的投資組合價值變動
    """
    current_value = prices.iloc[-1]
    results = {}

    for scenario_name, change_pct in scenarios.items():
        results[scenario_name] = {
            'new_value': current_value * (1 + change_pct),
            'pnl': current_value * change_pct,
            'pnl_pct': change_pct * 100,
        }

    return results


def monte_carlo_simulation(returns: pd.Series,
                           days: int = 252,
                           simulations: int = 1000,
                           initial_value: float = 1.0) -> pd.DataFrame:
    """
    蒙地卡羅模擬

    Parameters:
    -----------
    returns : pd.Series
        歷史報酬率
    days : int
        模擬天數
    simulations : int
        模擬次數
    initial_value : float
        初始值

    Returns:
    --------
    pd.DataFrame
        模擬結果，每列為一次模擬
    """
    mean_return = returns.mean()
    std_return = returns.std()

    # 產生隨機報酬
    random_returns = np.random.normal(mean_return, std_return, (simulations, days))

    # 計算累積價值
    cumulative_returns = np.cumprod(1 + random_returns, axis=1)
    simulated_values = initial_value * cumulative_returns

    return pd.DataFrame(simulated_values.T)
