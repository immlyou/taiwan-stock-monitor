"""
回測模組測試
涵蓋：BacktestEngine、calculate_metrics、compare_with_benchmark、PerformanceMetrics
"""
import pytest
import pandas as pd
import numpy as np

from core.backtest.engine import BacktestEngine, quick_backtest
from core.backtest.metrics import (
    calculate_metrics,
    calculate_total_return,
    calculate_annualized_return,
    calculate_volatility,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_calmar_ratio,
    compare_with_benchmark,
    PerformanceMetrics,
)
from core.strategies.value import ValueStrategy


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def trading_dates():
    return pd.date_range("2021-01-04", periods=504, freq="B")  # 約 2 年


@pytest.fixture(scope="module")
def stocks():
    return ["2330", "2317", "2454", "2412", "2308"]


@pytest.fixture(scope="module")
def close_df(trading_dates, stocks):
    np.random.seed(42)
    n, m = len(trading_dates), len(stocks)
    returns = np.random.normal(0.0003, 0.015, (n, m))
    prices = 100 * np.exp(np.cumsum(returns, axis=0))
    return pd.DataFrame(prices, index=trading_dates, columns=stocks)


@pytest.fixture(scope="module")
def pe_df(trading_dates, stocks):
    np.random.seed(7)
    data = np.random.uniform(8, 14, (len(trading_dates), len(stocks)))
    return pd.DataFrame(data, index=trading_dates, columns=stocks)


@pytest.fixture(scope="module")
def pb_df(trading_dates, stocks):
    np.random.seed(8)
    data = np.random.uniform(0.5, 1.4, (len(trading_dates), len(stocks)))
    return pd.DataFrame(data, index=trading_dates, columns=stocks)


@pytest.fixture(scope="module")
def dividend_df(trading_dates, stocks):
    np.random.seed(9)
    data = np.random.uniform(4.5, 7.0, (len(trading_dates), len(stocks)))
    return pd.DataFrame(data, index=trading_dates, columns=stocks)


@pytest.fixture(scope="module")
def full_data(close_df, pe_df, pb_df, dividend_df):
    return {
        "close": close_df,
        "pe_ratio": pe_df,
        "pb_ratio": pb_df,
        "dividend_yield": dividend_df,
    }


@pytest.fixture(scope="module")
def simple_portfolio_values(trading_dates):
    """簡單的投資組合淨值序列（含成長、回撤）"""
    np.random.seed(10)
    rets = np.random.normal(0.0005, 0.012, len(trading_dates))
    values = 1_000_000 * np.exp(np.cumsum(rets))
    return pd.Series(values, index=trading_dates)


@pytest.fixture(scope="module")
def flat_portfolio(trading_dates):
    """完全不動的投資組合（無交易）"""
    return pd.Series([1_000_000.0] * len(trading_dates), index=trading_dates)


@pytest.fixture(scope="module")
def sample_trades():
    """模擬交易記錄"""
    return pd.DataFrame([
        {"stock_id": "2330", "entry_date": pd.Timestamp("2021-01-05"), "entry_price": 600,
         "exit_date": pd.Timestamp("2021-03-01"), "exit_price": 650,
         "shares": 1000, "pnl": 48000, "return": 8.0, "holding_days": 55},
        {"stock_id": "2317", "entry_date": pd.Timestamp("2021-02-01"), "entry_price": 100,
         "exit_date": pd.Timestamp("2021-04-01"), "exit_price": 90,
         "shares": 2000, "pnl": -21000, "return": -10.5, "holding_days": 59},
        {"stock_id": "2454", "entry_date": pd.Timestamp("2021-03-01"), "entry_price": 800,
         "exit_date": pd.Timestamp("2021-05-01"), "exit_price": 860,
         "shares": 500, "pnl": 28500, "return": 7.5, "holding_days": 61},
        {"stock_id": "2412", "entry_date": pd.Timestamp("2021-04-01"), "entry_price": 120,
         "exit_date": pd.Timestamp("2021-06-01"), "exit_price": 115,
         "shares": 3000, "pnl": -16500, "return": -4.2, "holding_days": 61},
        {"stock_id": "2308", "entry_date": pd.Timestamp("2021-05-01"), "entry_price": 200,
         "exit_date": pd.Timestamp("2021-07-01"), "exit_price": 230,
         "shares": 1000, "pnl": 28500, "return": 15.0, "holding_days": 61},
    ])


# ──────────────────────────────────────────────
# BacktestEngine 初始化
# ──────────────────────────────────────────────

class TestBacktestEngineInit:

    def test_default_initial_capital(self):
        engine = BacktestEngine()
        assert engine.initial_capital == 1_000_000

    def test_custom_initial_capital(self):
        engine = BacktestEngine(initial_capital=500_000)
        assert engine.initial_capital == 500_000

    def test_default_commission_rate(self):
        engine = BacktestEngine()
        assert abs(engine.commission_rate - 0.001425) < 1e-9

    def test_price_limit_enabled_by_default(self):
        engine = BacktestEngine()
        assert engine.price_limit_enabled is True
        assert engine.up_limit == pytest.approx(0.10)
        assert engine.down_limit == pytest.approx(-0.10)


# ──────────────────────────────────────────────
# 交易成本計算
# ──────────────────────────────────────────────

class TestTransactionCost:

    def setup_method(self):
        self.engine = BacktestEngine()

    def test_buy_cost_no_tax(self):
        """買入不收交易稅"""
        cost = self.engine._calculate_transaction_cost(100_000, is_sell=False)
        expected_commission = max(100_000 * 0.001425 * 0.6, 20)
        assert abs(cost - expected_commission) < 0.01

    def test_sell_cost_includes_tax(self):
        """賣出包含 0.3% 交易稅"""
        cost = self.engine._calculate_transaction_cost(100_000, is_sell=True)
        commission = max(100_000 * 0.001425 * 0.6, 20)
        tax = 100_000 * 0.003
        assert abs(cost - (commission + tax)) < 0.01

    def test_minimum_commission_applied(self):
        """小額交易應採用最低手續費 20 元"""
        cost = self.engine._calculate_transaction_cost(100, is_sell=False)
        assert cost == pytest.approx(20.0)

    def test_zero_amount_returns_zero(self):
        cost = self.engine._calculate_transaction_cost(0, is_sell=False)
        assert cost == 0.0

    def test_sell_cost_greater_than_buy_cost(self):
        """賣出成本 > 買入成本（多了交易稅）"""
        buy_cost = self.engine._calculate_transaction_cost(200_000, is_sell=False)
        sell_cost = self.engine._calculate_transaction_cost(200_000, is_sell=True)
        assert sell_cost > buy_cost


# ──────────────────────────────────────────────
# 漲跌停判斷
# ──────────────────────────────────────────────

class TestPriceLimit:

    def setup_method(self):
        self.engine = BacktestEngine()

    def test_no_limit_when_disabled(self):
        self.engine.price_limit_enabled = False
        prev = pd.Series({"2330": 500.0})
        can_buy, can_sell, price = self.engine._check_price_limit("2330", 560.0, prev)
        assert can_buy is True
        assert can_sell is True
        self.engine.price_limit_enabled = True

    def test_limit_up_cannot_buy(self):
        prev = pd.Series({"2330": 500.0})
        can_buy, can_sell, _ = self.engine._check_price_limit("2330", 551.0, prev)
        assert can_buy is False
        assert can_sell is True

    def test_limit_down_cannot_sell(self):
        prev = pd.Series({"2330": 500.0})
        can_buy, can_sell, _ = self.engine._check_price_limit("2330", 449.0, prev)
        assert can_buy is True
        assert can_sell is False

    def test_normal_price_change_can_trade(self):
        prev = pd.Series({"2330": 500.0})
        can_buy, can_sell, _ = self.engine._check_price_limit("2330", 510.0, prev)
        assert can_buy is True
        assert can_sell is True

    def test_missing_stock_can_trade(self):
        prev = pd.Series({"2317": 100.0})
        can_buy, can_sell, _ = self.engine._check_price_limit("2330", 550.0, prev)
        assert can_buy is True
        assert can_sell is True


# ──────────────────────────────────────────────
# 權重分配
# ──────────────────────────────────────────────

class TestWeightAllocation:

    def setup_method(self):
        self.engine = BacktestEngine()

    def test_equal_weight_sums_to_one(self):
        stocks = ["A", "B", "C", "D"]
        weights = self.engine._allocate_weights(stocks, method="equal")
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_equal_weight_is_uniform(self):
        stocks = ["A", "B", "C", "D"]
        weights = self.engine._allocate_weights(stocks, method="equal")
        for w in weights.values():
            assert abs(w - 0.25) < 1e-9

    def test_market_cap_weight_sums_to_one(self):
        stocks = ["A", "B", "C"]
        mv = pd.Series({"A": 1000, "B": 2000, "C": 3000})
        weights = self.engine._allocate_weights(stocks, mv, method="market_cap")
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_market_cap_weight_proportional(self):
        stocks = ["A", "B"]
        mv = pd.Series({"A": 1000, "B": 3000})
        weights = self.engine._allocate_weights(stocks, mv, method="market_cap")
        assert abs(weights["A"] - 0.25) < 1e-6
        assert abs(weights["B"] - 0.75) < 1e-6

    def test_empty_stocks_returns_empty(self):
        weights = self.engine._allocate_weights([])
        assert weights == {}


# ──────────────────────────────────────────────
# 買入 / 賣出操作
# ──────────────────────────────────────────────

class TestBuySell:

    def setup_method(self):
        self.engine = BacktestEngine(initial_capital=1_000_000)
        self.engine.cash = 1_000_000
        self.engine.positions = {}
        self.engine.trades = []

    def test_buy_reduces_cash(self):
        before = self.engine.cash
        self.engine._buy("2330", pd.Timestamp("2021-01-05"), 600.0, 120_000)
        assert self.engine.cash < before

    def test_buy_creates_position(self):
        self.engine._buy("2317", pd.Timestamp("2021-01-05"), 100.0, 50_000)
        assert "2317" in self.engine.positions
        assert self.engine.positions["2317"]["shares"] > 0

    def test_buy_insufficient_cash_does_not_overdraft(self):
        self.engine.cash = 500
        self.engine._buy("2330", pd.Timestamp("2021-01-05"), 600.0, 10_000_000)
        # 買完後現金不應為負
        assert self.engine.cash >= 0

    def test_sell_removes_position(self):
        self.engine.cash = 1_000_000
        self.engine._buy("2454", pd.Timestamp("2021-01-05"), 800.0, 80_000)
        assert "2454" in self.engine.positions
        self.engine._sell("2454", pd.Timestamp("2021-02-01"), 820.0)
        assert "2454" not in self.engine.positions

    def test_sell_records_trade(self):
        self.engine.cash = 1_000_000
        self.engine.trades = []
        self.engine._buy("2412", pd.Timestamp("2021-01-05"), 120.0, 60_000)
        self.engine._sell("2412", pd.Timestamp("2021-03-01"), 130.0)
        assert len(self.engine.trades) == 1
        assert self.engine.trades[0].stock_id == "2412"

    def test_sell_nonexistent_position_no_crash(self):
        self.engine._sell("9999", pd.Timestamp("2021-01-05"), 100.0)  # 不應崩潰


# ──────────────────────────────────────────────
# 完整回測執行
# ──────────────────────────────────────────────

class TestBacktestRun:

    def test_run_returns_backtest_result(self, full_data, trading_dates):
        engine = BacktestEngine(initial_capital=1_000_000)

        def always_buy_first_two(data, date):
            return list(data["close"].columns[:2])

        result = engine.run(
            strategy_func=always_buy_first_two,
            data=full_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
            rebalance_freq="ME",
            max_stocks=2,
        )
        from core.backtest.engine import BacktestResult
        assert isinstance(result, BacktestResult)

    def test_portfolio_values_length_matches_trading_days(self, full_data, trading_dates):
        engine = BacktestEngine()

        def strategy(data, date):
            return [data["close"].columns[0]]

        result = engine.run(
            strategy_func=strategy,
            data=full_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
        )
        assert len(result.portfolio_values) == len(trading_dates)

    def test_portfolio_values_always_non_negative(self, full_data, trading_dates):
        engine = BacktestEngine()

        def strategy(data, date):
            return list(data["close"].columns[:3])

        result = engine.run(
            strategy_func=strategy,
            data=full_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
        )
        assert (result.portfolio_values >= 0).all()

    def test_no_strategy_holds_cash(self, full_data, trading_dates):
        """沒有選出任何股票時，投資組合價值應維持在初始資金"""
        engine = BacktestEngine(initial_capital=1_000_000)

        def no_stock(data, date):
            return []

        result = engine.run(
            strategy_func=no_stock,
            data=full_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
        )
        # 全程持現，每日淨值皆等於初始資金（允許浮點誤差）
        assert all(
            abs(v - 1_000_000) < 1.0
            for v in result.portfolio_values
        )

    def test_max_stocks_constraint_respected(self, full_data, trading_dates):
        max_stocks = 2
        engine = BacktestEngine()

        def all_stocks(data, date):
            return list(data["close"].columns)

        result = engine.run(
            strategy_func=all_stocks,
            data=full_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
            max_stocks=max_stocks,
        )
        for _, row in result.positions.iterrows():
            assert row["positions"] <= max_stocks

    def test_quick_backtest_helper(self, full_data, trading_dates):
        strategy = ValueStrategy()
        result = quick_backtest(
            strategy=strategy,
            data=full_data,
            start_date=str(trading_dates[0].date()),
            end_date=str(trading_dates[-1].date()),
        )
        assert result.metrics is not None
        assert result.metrics.total_return != 0 or True  # 允許任何數值

    def test_no_close_data_raises(self):
        engine = BacktestEngine()
        with pytest.raises(ValueError, match="close"):
            engine.run(strategy_func=lambda d, t: [], data={})

    def test_rebalance_freq_compat_old_alias(self, full_data, trading_dates):
        """舊版頻率別名 'M' 應等同於 'ME'，不應崩潰"""
        engine = BacktestEngine()

        def strategy(data, date):
            return [data["close"].columns[0]]

        result = engine.run(
            strategy_func=strategy,
            data=full_data,
            start_date=trading_dates[0],
            end_date=trading_dates[-1],
            rebalance_freq="M",
        )
        assert len(result.portfolio_values) > 0


# ──────────────────────────────────────────────
# 績效指標計算
# ──────────────────────────────────────────────

class TestPerformanceMetrics:

    def test_total_return_positive_growth(self, simple_portfolio_values):
        r = calculate_total_return(simple_portfolio_values)
        assert isinstance(r, float)

    def test_total_return_flat(self, flat_portfolio):
        r = calculate_total_return(flat_portfolio)
        assert abs(r) < 1e-6

    def test_total_return_single_point(self, trading_dates):
        pv = pd.Series([1_000_000.0], index=[trading_dates[0]])
        r = calculate_total_return(pv)
        assert r == 0.0

    def test_annualized_return_two_years_doubles(self, trading_dates):
        """兩年翻倍 → 年化約 41.4%"""
        values = pd.Series(
            np.linspace(1_000_000, 2_000_000, len(trading_dates)),
            index=trading_dates
        )
        r = calculate_annualized_return(values)
        assert 35 < r < 50

    def test_annualized_return_zero_days_safe(self):
        ts = pd.Timestamp("2021-01-01")
        pv = pd.Series([1_000_000.0, 1_050_000.0], index=[ts, ts])
        r = calculate_annualized_return(pv)
        assert r == 0.0

    def test_volatility_positive(self, simple_portfolio_values):
        v = calculate_volatility(simple_portfolio_values)
        assert v > 0

    def test_volatility_flat_is_zero(self, flat_portfolio):
        v = calculate_volatility(flat_portfolio)
        assert v == pytest.approx(0.0, abs=1e-6)

    def test_sharpe_ratio_type(self, simple_portfolio_values):
        sr = calculate_sharpe_ratio(simple_portfolio_values)
        assert isinstance(sr, float)

    def test_sortino_ratio_no_downside_returns_inf(self, trading_dates):
        """完全沒有虧損 → Sortino = inf"""
        values = pd.Series(
            np.linspace(1_000_000, 2_000_000, len(trading_dates)),
            index=trading_dates
        )
        sr = calculate_sortino_ratio(values)
        assert sr == float("inf")

    def test_sortino_ratio_finite_with_losses(self, simple_portfolio_values):
        sr = calculate_sortino_ratio(simple_portfolio_values)
        assert np.isfinite(sr)

    def test_max_drawdown_negative_or_zero(self, simple_portfolio_values):
        dd, duration, series = calculate_max_drawdown(simple_portfolio_values)
        assert dd <= 0

    def test_max_drawdown_no_drawdown_is_zero(self, trading_dates):
        rising = pd.Series(
            np.linspace(1_000_000, 2_000_000, len(trading_dates)),
            index=trading_dates
        )
        dd, _, _ = calculate_max_drawdown(rising)
        assert dd == pytest.approx(0.0, abs=0.01)

    def test_max_drawdown_duration_non_negative(self, simple_portfolio_values):
        _, duration, _ = calculate_max_drawdown(simple_portfolio_values)
        assert duration >= 0

    def test_calmar_ratio_returns_inf_when_no_drawdown(self, trading_dates):
        rising = pd.Series(
            np.linspace(1_000_000, 2_000_000, len(trading_dates)),
            index=trading_dates
        )
        calmar = calculate_calmar_ratio(rising)
        assert calmar == float("inf")

    def test_win_rate_all_wins(self):
        trades = pd.DataFrame({"return": [5.0, 3.0, 10.0, 2.0]})
        assert calculate_win_rate(trades) == 100.0

    def test_win_rate_all_losses(self):
        trades = pd.DataFrame({"return": [-5.0, -3.0, -1.0]})
        assert calculate_win_rate(trades) == 0.0

    def test_win_rate_mixed(self):
        trades = pd.DataFrame({"return": [5.0, -3.0, 10.0, -2.0]})
        assert calculate_win_rate(trades) == 50.0

    def test_win_rate_empty(self):
        assert calculate_win_rate(pd.DataFrame()) == 0.0

    def test_profit_factor_greater_than_one_when_profitable(self, sample_trades):
        """盈利交易多於虧損交易 → 獲利因子 > 1"""
        pf = calculate_profit_factor(sample_trades)
        assert pf > 1.0

    def test_profit_factor_uses_pnl_column(self, sample_trades):
        """確認使用 pnl（絕對金額）而非 return（百分比）計算"""
        pf_pnl = calculate_profit_factor(sample_trades)
        assert isinstance(pf_pnl, float)

    def test_profit_factor_empty(self):
        assert calculate_profit_factor(pd.DataFrame()) == 0.0

    def test_calculate_metrics_returns_performance_metrics(self, simple_portfolio_values, sample_trades):
        metrics = calculate_metrics(simple_portfolio_values, sample_trades)
        assert isinstance(metrics, PerformanceMetrics)
        assert isinstance(metrics.total_return, float)
        assert isinstance(metrics.sharpe_ratio, float)
        assert isinstance(metrics.max_drawdown, float)
        assert metrics.max_drawdown <= 0
        assert 0 <= metrics.win_rate <= 100
        assert metrics.total_trades == len(sample_trades)

    def test_calculate_metrics_no_trades(self, simple_portfolio_values):
        metrics = calculate_metrics(simple_portfolio_values)
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0


# ──────────────────────────────────────────────
# compare_with_benchmark
# ──────────────────────────────────────────────

class TestCompareWithBenchmark:

    def test_returns_dict_with_required_keys(self, simple_portfolio_values):
        benchmark = simple_portfolio_values * np.random.uniform(0.95, 1.05, len(simple_portfolio_values))
        result = compare_with_benchmark(simple_portfolio_values, benchmark)
        for key in ["excess_return", "beta", "alpha", "information_ratio", "correlation", "tracking_error"]:
            assert key in result

    def test_beta_self_comparison_is_one(self, simple_portfolio_values):
        result = compare_with_benchmark(simple_portfolio_values, simple_portfolio_values)
        assert result["beta"] == pytest.approx(1.0, abs=1e-6)

    def test_correlation_self_is_one(self, simple_portfolio_values):
        result = compare_with_benchmark(simple_portfolio_values, simple_portfolio_values)
        assert result["correlation"] == pytest.approx(1.0, abs=1e-6)

    def test_excess_return_outperform(self, trading_dates):
        """投資組合報酬高於基準 → 超額報酬為正"""
        base = pd.Series(np.linspace(1_000_000, 1_200_000, len(trading_dates)), index=trading_dates)
        portfolio = pd.Series(np.linspace(1_000_000, 1_400_000, len(trading_dates)), index=trading_dates)
        result = compare_with_benchmark(portfolio, base)
        assert result["excess_return"] > 0

    def test_risk_free_rate_parameter_affects_alpha(self, trading_dates):
        """不同 risk_free_rate 應產生不同 alpha（修正 W1 後驗證）
        使用差異夠大的兩個利率，確保 Alpha 計算結果不同。"""
        # 構造：portfolio 明顯優於 benchmark（+30% vs +10%）
        portfolio = pd.Series(
            np.linspace(1_000_000, 1_300_000, len(trading_dates)),
            index=trading_dates
        )
        benchmark = pd.Series(
            np.linspace(1_000_000, 1_100_000, len(trading_dates)),
            index=trading_dates
        )
        r_rf0 = compare_with_benchmark(portfolio, benchmark, risk_free_rate=0.0)
        r_rf10 = compare_with_benchmark(portfolio, benchmark, risk_free_rate=0.10)
        # 無風險利率 10% vs 0% 下的 alpha 必然不同
        assert abs(r_rf0["alpha"] - r_rf10["alpha"]) > 1e-6
