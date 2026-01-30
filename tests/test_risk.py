"""
風險分析模組測試
"""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.risk import (
    calculate_sharpe_ratio, calculate_sortino_ratio, calculate_max_drawdown,
    calculate_var, calculate_cvar, calculate_beta, calculate_alpha
)


class TestReturnMetrics:
    """報酬率指標測試"""

    def test_sharpe_ratio_positive_returns(self, sample_returns):
        """正報酬應該產生正夏普比率"""
        # 創建穩定正報酬
        positive_returns = pd.DataFrame(
            np.abs(sample_returns.values) + 0.001,
            index=sample_returns.index,
            columns=sample_returns.columns
        )
        result = calculate_sharpe_ratio(positive_returns)

        assert isinstance(result, pd.Series)
        assert (result > 0).all()

    def test_sharpe_ratio_risk_free_rate(self, sample_returns):
        """較高的無風險利率應降低夏普比率"""
        sharpe_low_rf = calculate_sharpe_ratio(sample_returns, risk_free_rate=0.01)
        sharpe_high_rf = calculate_sharpe_ratio(sample_returns, risk_free_rate=0.05)

        assert (sharpe_low_rf >= sharpe_high_rf).all()

    def test_sortino_ratio(self, sample_returns):
        """Sortino 比率測試"""
        result = calculate_sortino_ratio(sample_returns)

        assert isinstance(result, pd.Series)
        assert len(result) == sample_returns.shape[1]


class TestDrawdown:
    """回撤分析測試"""

    def test_max_drawdown_range(self, sample_returns):
        """最大回撤應在 0 到 -100% 之間"""
        result = calculate_max_drawdown(sample_returns)

        assert isinstance(result, pd.Series)
        assert (result <= 0).all()  # 回撤應為負數或零
        assert (result >= -1).all()  # 不應超過 -100%

    def test_max_drawdown_increasing_prices(self):
        """持續上漲的資產應該沒有回撤"""
        dates = pd.date_range('2023-01-01', periods=100)
        increasing = pd.DataFrame(
            {'stock': np.linspace(1, 2, 100)},
            index=dates
        )
        returns = increasing.pct_change().dropna()
        result = calculate_max_drawdown(returns)

        assert result.iloc[0] == 0 or abs(result.iloc[0]) < 0.01


class TestVaR:
    """風險值測試"""

    def test_var_confidence_level(self, sample_returns):
        """較高信心水準應產生較大 VaR"""
        var_95 = calculate_var(sample_returns, confidence=0.95)
        var_99 = calculate_var(sample_returns, confidence=0.99)

        assert (var_99 <= var_95).all()  # VaR 是負值，99% 應更負

    def test_var_is_negative(self, sample_returns):
        """VaR 應該是負值 (損失)"""
        result = calculate_var(sample_returns)

        assert (result <= 0).all()

    def test_cvar_worse_than_var(self, sample_returns):
        """CVaR 應該比 VaR 更差 (更負)"""
        var = calculate_var(sample_returns)
        cvar = calculate_cvar(sample_returns)

        # CVaR 應該小於或等於 VaR (更負)
        assert (cvar <= var).all()


class TestBetaAlpha:
    """Beta 和 Alpha 測試"""

    def test_beta_market(self, sample_returns):
        """市場對自己的 Beta 應該是 1"""
        market = sample_returns.iloc[:, 0]  # 用第一檔股票當市場

        # Beta 對自己應該是 1
        result = calculate_beta(market, market)
        np.testing.assert_almost_equal(result, 1.0, decimal=10)

    def test_beta_range(self, sample_returns):
        """Beta 通常在 -2 到 3 之間"""
        market = sample_returns.mean(axis=1)  # 平均作為市場

        for col in sample_returns.columns:
            beta = calculate_beta(sample_returns[col], market)
            assert -3 < beta < 5  # 寬鬆範圍

    def test_alpha_calculation(self, sample_returns):
        """Alpha 計算測試"""
        market = sample_returns.mean(axis=1)

        for col in sample_returns.columns:
            alpha = calculate_alpha(sample_returns[col], market)
            assert isinstance(alpha, float)
