"""
投資組合優化模組 - Markowitz 均值-方差優化
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from scipy.optimize import minimize
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """優化結果"""
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    method: str
    details: Dict = field(default_factory=dict)


@dataclass
class EfficientFrontier:
    """效率前緣"""
    returns: np.ndarray
    volatilities: np.ndarray
    sharpe_ratios: np.ndarray
    weights_list: List[Dict[str, float]]


class PortfolioOptimizer:
    """
    投資組合優化器

    使用 Markowitz 均值-方差模型進行投資組合優化

    Methods:
    --------
    optimize_max_sharpe : 最大化夏普比率
    optimize_min_volatility : 最小化波動率
    optimize_target_return : 給定目標報酬，最小化風險
    calculate_efficient_frontier : 計算效率前緣
    """

    def __init__(self,
                 returns: pd.DataFrame,
                 risk_free_rate: float = 0.02,
                 trading_days: int = 252):
        """
        Parameters:
        -----------
        returns : pd.DataFrame
            日報酬率數據，columns 為股票代碼
        risk_free_rate : float
            年化無風險利率 (預設 2%)
        trading_days : int
            年交易天數 (預設 252)
        """
        self.returns = returns.dropna(how='all', axis=1)
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days

        # 計算年化統計量
        self.mean_returns = self.returns.mean() * trading_days
        self.cov_matrix = self.returns.cov() * trading_days
        self.stocks = list(self.returns.columns)
        self.n_stocks = len(self.stocks)

        logger.info(f'初始化投資組合優化器: {self.n_stocks} 檔股票')

    def _portfolio_stats(self, weights: np.ndarray) -> Tuple[float, float, float]:
        """
        計算投資組合統計量

        Parameters:
        -----------
        weights : np.ndarray
            權重陣列

        Returns:
        --------
        tuple
            (預期報酬, 波動率, 夏普比率)
        """
        weights = np.array(weights)
        portfolio_return = np.sum(self.mean_returns * weights)
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0

        return portfolio_return, portfolio_vol, sharpe

    def _neg_sharpe(self, weights: np.ndarray) -> float:
        """負夏普比率 (用於最小化)"""
        _, _, sharpe = self._portfolio_stats(weights)
        return -sharpe

    def _portfolio_volatility(self, weights: np.ndarray) -> float:
        """投資組合波動率"""
        return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))

    def _portfolio_return(self, weights: np.ndarray) -> float:
        """投資組合預期報酬"""
        return np.sum(self.mean_returns * weights)

    def optimize_max_sharpe(self,
                            min_weight: float = 0.0,
                            max_weight: float = 1.0) -> OptimizationResult:
        """
        最大化夏普比率

        Parameters:
        -----------
        min_weight : float
            單一股票最小權重
        max_weight : float
            單一股票最大權重

        Returns:
        --------
        OptimizationResult
            優化結果
        """
        # 初始權重
        init_weights = np.array([1.0 / self.n_stocks] * self.n_stocks)

        # 約束條件
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # 權重和為 1
        ]

        # 邊界條件
        bounds = tuple((min_weight, max_weight) for _ in range(self.n_stocks))

        # 優化
        result = minimize(
            self._neg_sharpe,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not result.success:
            logger.warning(f'優化未收斂: {result.message}')

        weights = result.x
        ret, vol, sharpe = self._portfolio_stats(weights)

        weights_dict = {stock: w for stock, w in zip(self.stocks, weights) if w > 0.001}

        return OptimizationResult(
            weights=weights_dict,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            method='max_sharpe',
            details={'success': result.success, 'message': result.message}
        )

    def optimize_min_volatility(self,
                                 min_weight: float = 0.0,
                                 max_weight: float = 1.0) -> OptimizationResult:
        """
        最小化波動率

        Parameters:
        -----------
        min_weight : float
            單一股票最小權重
        max_weight : float
            單一股票最大權重

        Returns:
        --------
        OptimizationResult
            優化結果
        """
        init_weights = np.array([1.0 / self.n_stocks] * self.n_stocks)

        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        ]

        bounds = tuple((min_weight, max_weight) for _ in range(self.n_stocks))

        result = minimize(
            self._portfolio_volatility,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not result.success:
            logger.warning(f'優化未收斂: {result.message}')

        weights = result.x
        ret, vol, sharpe = self._portfolio_stats(weights)

        weights_dict = {stock: w for stock, w in zip(self.stocks, weights) if w > 0.001}

        return OptimizationResult(
            weights=weights_dict,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            method='min_volatility',
            details={'success': result.success, 'message': result.message}
        )

    def optimize_target_return(self,
                                target_return: float,
                                min_weight: float = 0.0,
                                max_weight: float = 1.0) -> OptimizationResult:
        """
        給定目標報酬，最小化風險

        Parameters:
        -----------
        target_return : float
            年化目標報酬率
        min_weight : float
            單一股票最小權重
        max_weight : float
            單一股票最大權重

        Returns:
        --------
        OptimizationResult
            優化結果
        """
        init_weights = np.array([1.0 / self.n_stocks] * self.n_stocks)

        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'eq', 'fun': lambda x: self._portfolio_return(x) - target_return}
        ]

        bounds = tuple((min_weight, max_weight) for _ in range(self.n_stocks))

        result = minimize(
            self._portfolio_volatility,
            init_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if not result.success:
            logger.warning(f'優化未收斂: {result.message}')

        weights = result.x
        ret, vol, sharpe = self._portfolio_stats(weights)

        weights_dict = {stock: w for stock, w in zip(self.stocks, weights) if w > 0.001}

        return OptimizationResult(
            weights=weights_dict,
            expected_return=ret,
            volatility=vol,
            sharpe_ratio=sharpe,
            method='target_return',
            details={
                'target_return': target_return,
                'success': result.success,
                'message': result.message
            }
        )

    def calculate_efficient_frontier(self,
                                      n_points: int = 50,
                                      min_weight: float = 0.0,
                                      max_weight: float = 1.0) -> EfficientFrontier:
        """
        計算效率前緣

        Parameters:
        -----------
        n_points : int
            前緣點數
        min_weight : float
            單一股票最小權重
        max_weight : float
            單一股票最大權重

        Returns:
        --------
        EfficientFrontier
            效率前緣數據
        """
        # 先找出最小和最大可行報酬
        min_vol_result = self.optimize_min_volatility(min_weight, max_weight)
        max_sharpe_result = self.optimize_max_sharpe(min_weight, max_weight)

        min_ret = min_vol_result.expected_return
        max_ret = max(max_sharpe_result.expected_return, self.mean_returns.max())

        # 在報酬範圍內計算效率前緣
        target_returns = np.linspace(min_ret, max_ret, n_points)

        returns_list = []
        volatilities_list = []
        sharpe_list = []
        weights_list = []

        for target_ret in target_returns:
            try:
                result = self.optimize_target_return(target_ret, min_weight, max_weight)
                if result.details.get('success', False):
                    returns_list.append(result.expected_return)
                    volatilities_list.append(result.volatility)
                    sharpe_list.append(result.sharpe_ratio)
                    weights_list.append(result.weights)
            except Exception:
                continue

        return EfficientFrontier(
            returns=np.array(returns_list),
            volatilities=np.array(volatilities_list),
            sharpe_ratios=np.array(sharpe_list),
            weights_list=weights_list
        )

    def random_portfolios(self, n_portfolios: int = 5000) -> pd.DataFrame:
        """
        生成隨機投資組合

        Parameters:
        -----------
        n_portfolios : int
            投資組合數量

        Returns:
        --------
        pd.DataFrame
            隨機投資組合的報酬、波動率、夏普比率
        """
        results = []

        for _ in range(n_portfolios):
            # 隨機權重
            weights = np.random.random(self.n_stocks)
            weights /= np.sum(weights)

            ret, vol, sharpe = self._portfolio_stats(weights)
            results.append({
                'return': ret,
                'volatility': vol,
                'sharpe': sharpe,
            })

        return pd.DataFrame(results)

    def get_correlation_matrix(self) -> pd.DataFrame:
        """取得股票相關係數矩陣"""
        return self.returns.corr()

    def get_stock_stats(self) -> pd.DataFrame:
        """取得個股統計量"""
        stats = pd.DataFrame({
            'annual_return': self.mean_returns,
            'annual_volatility': self.returns.std() * np.sqrt(self.trading_days),
        })
        stats['sharpe_ratio'] = (stats['annual_return'] - self.risk_free_rate) / stats['annual_volatility']
        return stats.sort_values('sharpe_ratio', ascending=False)


def optimize_portfolio(stock_ids: List[str],
                       returns_df: pd.DataFrame,
                       method: str = 'max_sharpe',
                       **kwargs) -> OptimizationResult:
    """
    快速優化投資組合

    Parameters:
    -----------
    stock_ids : list
        股票代碼列表
    returns_df : pd.DataFrame
        日報酬率數據
    method : str
        優化方法: 'max_sharpe', 'min_volatility', 'target_return'
    **kwargs
        傳遞給優化方法的額外參數

    Returns:
    --------
    OptimizationResult
        優化結果
    """
    # 過濾股票
    available_stocks = [s for s in stock_ids if s in returns_df.columns]
    if len(available_stocks) < 2:
        raise ValueError('至少需要 2 檔股票進行優化')

    returns = returns_df[available_stocks]
    optimizer = PortfolioOptimizer(returns, **kwargs)

    if method == 'max_sharpe':
        return optimizer.optimize_max_sharpe()
    elif method == 'min_volatility':
        return optimizer.optimize_min_volatility()
    elif method == 'target_return':
        target = kwargs.get('target_return', 0.1)
        return optimizer.optimize_target_return(target)
    else:
        raise ValueError(f'未知的優化方法: {method}')
