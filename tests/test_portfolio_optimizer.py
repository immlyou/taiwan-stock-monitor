"""
投資組合優化模組測試
"""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.portfolio_optimizer import PortfolioOptimizer, OptimizationResult


class TestPortfolioOptimizer:
    """投資組合優化器測試"""

    @pytest.fixture
    def optimizer(self, sample_returns):
        """建立優化器 fixture"""
        return PortfolioOptimizer(sample_returns)

    def test_initialization(self, optimizer, sample_stocks):
        """測試初始化"""
        assert optimizer.n_stocks == len(sample_stocks)
        assert len(optimizer.stocks) == len(sample_stocks)
        assert optimizer.mean_returns is not None
        assert optimizer.cov_matrix is not None

    def test_max_sharpe_weights_sum_to_one(self, optimizer):
        """最大夏普優化的權重和應為 1"""
        result = optimizer.optimize_max_sharpe()

        total_weight = sum(result.weights.values())
        np.testing.assert_almost_equal(total_weight, 1.0, decimal=5)

    def test_max_sharpe_result_type(self, optimizer):
        """最大夏普優化結果類型檢查"""
        result = optimizer.optimize_max_sharpe()

        assert isinstance(result, OptimizationResult)
        assert isinstance(result.weights, dict)
        assert isinstance(result.expected_return, float)
        assert isinstance(result.volatility, float)
        assert isinstance(result.sharpe_ratio, float)
        assert result.method == 'max_sharpe'

    def test_min_volatility_weights_sum_to_one(self, optimizer):
        """最小波動優化的權重和應為 1"""
        result = optimizer.optimize_min_volatility()

        total_weight = sum(result.weights.values())
        np.testing.assert_almost_equal(total_weight, 1.0, decimal=5)

    def test_min_volatility_lower_than_equal_weight(self, optimizer):
        """最小波動組合的波動率應小於等權組合"""
        result = optimizer.optimize_min_volatility()

        # 計算等權組合波動率
        n = optimizer.n_stocks
        equal_weights = np.array([1.0 / n] * n)
        _, equal_vol, _ = optimizer._portfolio_stats(equal_weights)

        # 最優化結果應該波動率更低或相等
        assert result.volatility <= equal_vol + 0.001  # 允許小誤差

    def test_target_return_achieves_target(self, optimizer):
        """目標報酬優化應達到目標"""
        target = 0.10  # 10% 年化報酬
        result = optimizer.optimize_target_return(target)

        if result.details.get('success'):
            np.testing.assert_almost_equal(
                result.expected_return, target, decimal=3
            )

    def test_weight_constraints(self, optimizer):
        """權重約束測試"""
        min_w = 0.05
        max_w = 0.40

        result = optimizer.optimize_max_sharpe(min_weight=min_w, max_weight=max_w)

        for weight in result.weights.values():
            assert weight >= min_w - 0.001  # 允許小誤差
            assert weight <= max_w + 0.001

    def test_efficient_frontier_points(self, optimizer):
        """效率前緣點數測試"""
        n_points = 20
        frontier = optimizer.calculate_efficient_frontier(n_points=n_points)

        # 應該有一些有效的點
        assert len(frontier.returns) > 0
        assert len(frontier.volatilities) == len(frontier.returns)
        assert len(frontier.sharpe_ratios) == len(frontier.returns)

    def test_efficient_frontier_monotonic_volatility(self, optimizer):
        """效率前緣上報酬增加時波動率也應增加"""
        frontier = optimizer.calculate_efficient_frontier(n_points=30)

        if len(frontier.returns) > 1:
            # 按報酬排序
            sorted_idx = np.argsort(frontier.returns)
            sorted_vols = frontier.volatilities[sorted_idx]

            # 波動率應大致增加 (允許一些噪音)
            # 計算波動率增加的比例
            increases = np.sum(np.diff(sorted_vols) >= -0.001)
            total = len(sorted_vols) - 1

            assert increases / total > 0.7  # 至少 70% 是增加的

    def test_random_portfolios(self, optimizer):
        """隨機投資組合生成測試"""
        n_portfolios = 100
        result = optimizer.random_portfolios(n_portfolios)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == n_portfolios
        assert 'return' in result.columns
        assert 'volatility' in result.columns
        assert 'sharpe' in result.columns

    def test_correlation_matrix(self, optimizer, sample_stocks):
        """相關係數矩陣測試"""
        corr = optimizer.get_correlation_matrix()

        assert isinstance(corr, pd.DataFrame)
        assert corr.shape == (len(sample_stocks), len(sample_stocks))

        # 對角線應為 1
        np.testing.assert_array_almost_equal(np.diag(corr.values), 1.0)

        # 相關係數應在 -1 到 1 之間
        assert (corr.values >= -1).all()
        assert (corr.values <= 1).all()

    def test_stock_stats(self, optimizer, sample_stocks):
        """個股統計量測試"""
        stats = optimizer.get_stock_stats()

        assert isinstance(stats, pd.DataFrame)
        assert len(stats) == len(sample_stocks)
        assert 'annual_return' in stats.columns
        assert 'annual_volatility' in stats.columns
        assert 'sharpe_ratio' in stats.columns

    def test_positive_volatility(self, optimizer):
        """波動率應為正值"""
        result = optimizer.optimize_max_sharpe()
        assert result.volatility > 0


class TestEdgeCases:
    """邊界情況測試"""

    def test_two_stocks(self, sample_dates):
        """只有兩檔股票的情況"""
        np.random.seed(42)
        returns = pd.DataFrame({
            'A': np.random.normal(0.001, 0.02, len(sample_dates)),
            'B': np.random.normal(0.0005, 0.015, len(sample_dates)),
        }, index=sample_dates)

        optimizer = PortfolioOptimizer(returns)
        result = optimizer.optimize_max_sharpe()

        assert len(result.weights) <= 2
        total = sum(result.weights.values())
        np.testing.assert_almost_equal(total, 1.0, decimal=5)

    def test_highly_correlated_stocks(self, sample_dates):
        """高度相關股票"""
        np.random.seed(42)
        base = np.random.normal(0.001, 0.02, len(sample_dates))
        returns = pd.DataFrame({
            'A': base,
            'B': base + np.random.normal(0, 0.001, len(sample_dates)),
            'C': base + np.random.normal(0, 0.002, len(sample_dates)),
        }, index=sample_dates)

        optimizer = PortfolioOptimizer(returns)
        result = optimizer.optimize_min_volatility()

        # 應該能成功優化
        assert result.volatility > 0
        total = sum(result.weights.values())
        np.testing.assert_almost_equal(total, 1.0, decimal=5)
