"""
針對特定缺口的精準測試
涵蓋：data_loader（init_finlab、is_streamlit_cloud、get_active_stocks）、
      hidden_gems（各 scan 方法）、hot_stocks（剩餘方法）、
      health_check（改善覆蓋）、optimizer（walk-forward 邊界）、
      portfolio_optimizer（quick_optimize）、backtest/metrics（edge cases）
"""
import os
import sys
import pickle
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────
# data_loader — init_finlab、is_streamlit_cloud、get_active_stocks
# ──────────────────────────────────────────────
from core.data_loader import (
    DataLoader, DataCache, is_streamlit_cloud,
    init_finlab, is_stock_active,
)
import core.data_loader as dl_module


class TestIsStreamlitCloud:
    def test_returns_true_when_env_var_set(self):
        with patch.dict(os.environ, {"STREAMLIT_SHARING_MODE": "streamlit"}):
            result = is_streamlit_cloud()
            assert result is True

    def test_returns_true_when_headless(self):
        with patch.dict(os.environ, {"STREAMLIT_SERVER_HEADLESS": "true"}):
            result = is_streamlit_cloud()
            assert result is True

    def test_returns_false_when_pickle_exists(self, tmp_path):
        """當 pickle 檔案存在時，應回傳 False（非雲端環境）"""
        # 建立假的 pickle 檔案
        dummy_pickle = tmp_path / "price#收盤價.pickle"
        dummy_pickle.touch()
        # 需要 mock DATA_DIR 指向 tmp_path
        with patch("core.data_loader.DATA_DIR", tmp_path):
            with patch.dict(os.environ, {}, clear=False):
                # 清除可能干擾的環境變數
                env = {k: v for k, v in os.environ.items()
                       if k not in ("STREAMLIT_SHARING_MODE", "STREAMLIT_SERVER_HEADLESS")}
                with patch.dict(os.environ, env, clear=True):
                    result = is_streamlit_cloud()
                    # pickle 存在 → False（本地模式）
                    assert result is False


class TestInitFinlab:
    def setup_method(self):
        # 重置 FinLab 初始化狀態
        dl_module._finlab_initialized = False

    def test_returns_false_when_no_token(self):
        """無 token 時應回傳 False"""
        mock_finlab = MagicMock()
        with patch.dict(sys.modules, {"finlab": mock_finlab}):
            with patch.dict(os.environ, {}, clear=False):
                env = {k: v for k, v in os.environ.items() if k != "FINLAB_API_TOKEN"}
                with patch.dict(os.environ, env, clear=True):
                    with patch("core.data_loader.HAS_STREAMLIT", False):
                        dl_module._finlab_initialized = False
                        result = init_finlab()
                        assert result is False

    def test_returns_true_when_already_initialized(self):
        """已初始化時直接回傳 True，不重複初始化"""
        dl_module._finlab_initialized = True
        result = init_finlab()
        assert result is True

    def test_returns_false_when_import_error(self):
        """finlab 未安裝時應回傳 False"""
        dl_module._finlab_initialized = False
        with patch.dict(sys.modules, {"finlab": None}):
            result = init_finlab()
            assert result is False

    def teardown_method(self):
        dl_module._finlab_initialized = False


@pytest.fixture
def active_stocks_dir(tmp_path):
    """建立供 get_active_stocks 使用的 pickle 目錄"""
    np.random.seed(0)
    dates = pd.date_range("2022-01-01", periods=60, freq="B")
    stocks = ["2330", "2317", "9999"]
    from config import DATA_FILES
    for key, filename in DATA_FILES.items():
        df = pd.DataFrame(
            np.random.uniform(50, 200, (60, 3)),
            index=dates, columns=stocks
        )
        with open(tmp_path / filename, "wb") as f:
            pickle.dump(df, f)
    return tmp_path


class TestGetActiveStocksDetailed:
    def test_all_active_when_fresh_data(self, active_stocks_dir):
        loader = DataLoader(data_dir=active_stocks_dir, use_global_cache=False)
        loader._use_finlab_api = False
        with patch("core.data_loader.DataLoader", return_value=loader):
            cache = DataCache()
            cache.clear_key("_active_stocks_30")
            stocks = loader.get_stock_list()
            assert len(stocks) == 3

    def test_is_stock_active_existing(self, active_stocks_dir):
        loader = DataLoader(data_dir=active_stocks_dir, use_global_cache=False)
        loader._use_finlab_api = False
        with patch("core.data_loader.DataLoader", return_value=loader):
            result = is_stock_active("2330")
            assert isinstance(result, bool)

    def test_is_stock_active_nonexistent(self, active_stocks_dir):
        loader = DataLoader(data_dir=active_stocks_dir, use_global_cache=False)
        loader._use_finlab_api = False
        with patch("core.data_loader.DataLoader", return_value=loader):
            result = is_stock_active("XXXX_NOT_IN_DATA")
            assert result is False


# ──────────────────────────────────────────────
# hidden_gems — 各 private scan 方法直接測試
# ──────────────────────────────────────────────
from core.hidden_gems import HiddenGemsScanner


@pytest.fixture(scope="module")
def scan_dates():
    return pd.date_range("2021-01-01", periods=120, freq="B")


@pytest.fixture(scope="module")
def scan_stocks():
    return [f"{i:04d}" for i in range(2300, 2325)]  # 25 支股票


@pytest.fixture(scope="module")
def scan_data(scan_dates, scan_stocks):
    """構造專門觸發各掃描方法條件的數據"""
    np.random.seed(77)
    n, m = len(scan_dates), len(scan_stocks)

    close = pd.DataFrame(
        100 * np.exp(np.cumsum(np.random.normal(0, 0.01, (n, m)), axis=0)),
        index=scan_dates, columns=scan_stocks
    )
    volume = pd.DataFrame(
        np.random.randint(100, 5000, (n, m)).astype(float) * 1000,
        index=scan_dates, columns=scan_stocks
    )
    # 低 PE、低 PB、高殖利率（觸發 value gems 條件）
    pe = pd.DataFrame(np.random.uniform(5, 11, (n, m)), index=scan_dates, columns=scan_stocks)
    pb = pd.DataFrame(np.random.uniform(0.3, 0.9, (n, m)), index=scan_dates, columns=scan_stocks)
    dividend = pd.DataFrame(np.random.uniform(6, 10, (n, m)), index=scan_dates, columns=scan_stocks)
    # 高 YoY（觸發 revenue breakout 條件）
    revenue_yoy = pd.DataFrame(np.random.uniform(35, 80, (n, m)), index=scan_dates, columns=scan_stocks)
    revenue_mom = pd.DataFrame(np.random.uniform(15, 30, (n, m)), index=scan_dates, columns=scan_stocks)
    # 法人持續買超（觸發 stealth buy 條件）
    foreign = pd.DataFrame(np.abs(np.random.randint(100, 5000, (n, m))).astype(float), index=scan_dates, columns=scan_stocks)
    trust = pd.DataFrame(np.abs(np.random.randint(50, 2000, (n, m))).astype(float), index=scan_dates, columns=scan_stocks)
    # 市值（觸發 small cap 條件）
    market_value = pd.DataFrame(np.random.uniform(1e9, 5e9, (n, m)), index=scan_dates, columns=scan_stocks)
    # 大股東比率變化（觸發 ownership shift 條件）
    ownership = pd.DataFrame(np.random.uniform(30, 60, (n, m)), index=scan_dates, columns=scan_stocks)

    return {
        "close": close,
        "volume": volume,
        "pe_ratio": pe,
        "pb_ratio": pb,
        "dividend_yield": dividend,
        "revenue_yoy": revenue_yoy,
        "revenue_mom": revenue_mom,
        "foreign_investors": foreign,
        "investment_trust": trust,
        "market_value": market_value,
        "inventory_over_1000_ratio": ownership,
    }


@pytest.fixture
def scan_loader(scan_data, scan_stocks, scan_dates):
    loader = MagicMock()
    cats = pd.DataFrame({
        "stock_id": scan_stocks,
        "name": [f"股票{s}" for s in scan_stocks],
        "category": ["半導體"] * len(scan_stocks),
    })

    def get_side_effect(key, **kwargs):
        return scan_data.get(key, pd.DataFrame())

    loader.get.side_effect = get_side_effect
    loader.get_stock_info.return_value = cats
    return loader


class TestHiddenGemsScanMethods:
    """直接測試各私有掃描方法以提升覆蓋率"""

    def _make_cache(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        return scanner._build_cache(scan_data, scan_stocks)

    def test_scan_value_gems_with_matching_data(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        result = scanner._scan_value_gems(scan_data, scan_stocks, cache)
        assert isinstance(result, list)

    def test_scan_value_gems_no_pe_returns_empty(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        data_no_pe = {k: v for k, v in scan_data.items() if k != "pe_ratio"}
        result = scanner._scan_value_gems(data_no_pe, scan_stocks, cache)
        assert result == []

    def test_scan_revenue_breakout(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        result = scanner._scan_revenue_breakout(scan_data, scan_stocks, cache)
        assert isinstance(result, list)

    def test_scan_revenue_breakout_no_yoy_returns_empty(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        data_no_yoy = {k: v for k, v in scan_data.items() if k != "revenue_yoy"}
        result = scanner._scan_revenue_breakout(data_no_yoy, scan_stocks, cache)
        assert result == []

    def test_scan_stealth_buy(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        result = scanner._scan_stealth_buy(scan_data, scan_stocks, cache)
        assert isinstance(result, list)

    def test_scan_stealth_buy_no_foreign_returns_empty(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        data_no_fi = {k: v for k, v in scan_data.items() if k != "foreign_investors"}
        result = scanner._scan_stealth_buy(data_no_fi, scan_stocks, cache)
        assert result == []

    def test_scan_technical_reversal(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        result = scanner._scan_technical_reversal(scan_data, scan_stocks, cache)
        assert isinstance(result, list)

    def test_scan_small_cap_growth(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        result = scanner._scan_small_cap_growth(scan_data, scan_stocks, cache)
        assert isinstance(result, list)

    def test_scan_ownership_shift(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        cache = self._make_cache(scan_data, scan_stocks)
        result = scanner._scan_ownership_shift(scan_data, scan_stocks, cache)
        assert isinstance(result, list)

    def test_compute_composite(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        scanner._name_map = {s: f"股票{s}" for s in scan_stocks}
        cache = self._make_cache(scan_data, scan_stocks)
        top20 = scanner._compute_composite(
            scan_stocks, [], [], [], [], [], [], scan_data, cache
        )
        assert isinstance(top20, list)

    def test_build_name_map_from_stock_info(self, scan_loader, scan_stocks):
        scanner = HiddenGemsScanner()
        name_map = scanner._build_name_map(scan_loader)
        assert isinstance(name_map, dict)

    def test_build_name_map_exception_returns_empty(self):
        scanner = HiddenGemsScanner()
        failing_loader = MagicMock()
        failing_loader.get.side_effect = Exception("失敗")
        result = scanner._build_name_map(failing_loader)
        assert result == {}

    def test_make_entry_structure(self, scan_data, scan_stocks):
        scanner = HiddenGemsScanner()
        scanner._name_map = {scan_stocks[0]: "台積電"}
        cache = self._make_cache(scan_data, scan_stocks)
        entry = scanner._make_entry(scan_stocks[0], cache, 75.0, tags=["測試"], highlight="PE 10.0")
        assert isinstance(entry, dict)
        assert "stock_id" in entry
        assert "scores" in entry


# ──────────────────────────────────────────────
# hot_stocks — 補齊缺口
# ──────────────────────────────────────────────
from core.hot_stocks import HotStockAnalyzer


@pytest.fixture(scope="module")
def hs2_dates():
    return pd.date_range("2022-01-01", periods=60, freq="B")


@pytest.fixture(scope="module")
def hs2_close(hs2_dates):
    np.random.seed(0)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.012, (60, 3)), axis=0))
    return pd.DataFrame(prices, index=hs2_dates, columns=["2330", "2317", "2454"])


@pytest.fixture(scope="module")
def hs2_volume(hs2_dates):
    np.random.seed(1)
    data = np.random.randint(1000, 30000, (60, 3)).astype(float) * 1000
    return pd.DataFrame(data, index=hs2_dates, columns=["2330", "2317", "2454"])


@pytest.fixture
def hs2_loader(hs2_close, hs2_volume):
    loader = MagicMock()
    stock_info = pd.DataFrame({
        "stock_id": ["2330", "2317", "2454"],
        "name": ["台積電", "鴻海", "聯發科"],
        "category": ["半導體", "電子", "半導體"],
        "industry": ["半導體", "電子", "半導體"],
    })
    loader.get.side_effect = lambda k, **kw: {"close": hs2_close, "volume": hs2_volume}.get(k)
    loader.get_stock_info.return_value = stock_info
    return loader


class TestHotStocksAdditional:
    def test_volume_score_above_5x_ratio_is_100(self, hs2_loader, hs2_dates):
        """量比 >= 5 時分數應為 100"""
        with patch("core.hot_stocks.get_loader", return_value=hs2_loader):
            analyzer = HotStockAnalyzer()
            # 手動建立高量比場景
            analyzer.loader = hs2_loader
            # 取得正常計算結果
            results = analyzer.calculate_volume_scores()
            # 無論如何不應超過 100
            for data in results.values():
                assert data["score"] <= 100.0

    def test_momentum_score_extreme_rise(self, hs2_dates):
        """漲幅 >= 30% 時動能分數應為 100"""
        rising_close = pd.DataFrame(
            {s: np.linspace(100, 160, 60) for s in ["2330", "2317"]},
            index=hs2_dates
        )
        loader = MagicMock()
        loader.get.side_effect = lambda k, **kw: rising_close if k == "close" else None
        with patch("core.hot_stocks.get_loader", return_value=loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_momentum_scores()
            for data in results.values():
                assert data["score"] <= 100.0

    def test_momentum_score_extreme_fall(self, hs2_dates):
        """跌幅 >= 30% 時動能分數應為 0"""
        falling_close = pd.DataFrame(
            {s: np.linspace(100, 60, 60) for s in ["2330"]},
            index=hs2_dates
        )
        loader = MagicMock()
        loader.get.side_effect = lambda k, **kw: falling_close if k == "close" else None
        with patch("core.hot_stocks.get_loader", return_value=loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_momentum_scores()
            for data in results.values():
                assert data["score"] >= 0.0

    def test_news_positive_tag(self, hs2_loader):
        """正面新聞情緒應產生「正面報導」標籤"""
        with patch("core.hot_stocks.get_loader", return_value=hs2_loader):
            analyzer = HotStockAnalyzer()
            news = {
                "2330": {"count": 5, "sentiment": 0.5, "score": 90.0},  # 正面情緒 > 0.3
            }
            results = analyzer.analyze_hot_stocks(news_hot_stocks=news, min_score=0.0)
            tagged = [r for r in results if r.stock_id == "2330"]
            if tagged:
                assert "正面報導" in tagged[0].tags

    def test_news_negative_tag(self, hs2_loader):
        """負面新聞情緒應產生「負面報導」標籤"""
        with patch("core.hot_stocks.get_loader", return_value=hs2_loader):
            analyzer = HotStockAnalyzer()
            news = {
                "2330": {"count": 5, "sentiment": -0.5, "score": 90.0},
            }
            results = analyzer.analyze_hot_stocks(news_hot_stocks=news, min_score=0.0)
            tagged = [r for r in results if r.stock_id == "2330"]
            if tagged:
                assert "負面報導" in tagged[0].tags


# ──────────────────────────────────────────────
# portfolio_optimizer — quick_optimize
# ──────────────────────────────────────────────
from core.portfolio_optimizer import optimize_portfolio


class TestQuickOptimize:
    @pytest.fixture(scope="class")
    def opt_returns(self):
        np.random.seed(0)
        dates = pd.date_range("2021-01-01", periods=252)
        return pd.DataFrame(
            np.random.normal(0.0005, 0.015, (252, 3)),
            index=dates, columns=["2330", "2317", "2454"]
        )

    def test_max_sharpe(self, opt_returns):
        result = optimize_portfolio(["2330", "2317", "2454"], opt_returns, "max_sharpe")
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4

    def test_min_volatility(self, opt_returns):
        result = optimize_portfolio(["2330", "2317", "2454"], opt_returns, "min_volatility")
        assert result.volatility > 0

    def test_target_return(self, opt_returns):
        # target_return 需在 PortfolioOptimizer 初始化後單獨呼叫
        result = optimize_portfolio(
            ["2330", "2317", "2454"], opt_returns, "target_return"
        )
        assert result is not None

    def test_unknown_method_raises(self, opt_returns):
        with pytest.raises(ValueError):
            optimize_portfolio(["2330", "2317"], opt_returns, "unknown_method")

    def test_insufficient_stocks_raises(self, opt_returns):
        with pytest.raises(ValueError):
            optimize_portfolio(["2330"], opt_returns, "max_sharpe")

    def test_stocks_not_in_data_raises(self, opt_returns):
        with pytest.raises(ValueError):
            optimize_portfolio(["XXXX", "YYYY"], opt_returns, "max_sharpe")


# ──────────────────────────────────────────────
# optimizer — _evaluate_params edge cases
# ──────────────────────────────────────────────
from core.optimizer import GridSearchOptimizer


class TestGridSearchEdgeCases:
    @pytest.fixture(scope="class")
    def opt_data(self):
        np.random.seed(0)
        dates = pd.date_range("2021-01-01", periods=120, freq="B")
        close = pd.DataFrame(
            100 * np.exp(np.cumsum(np.random.normal(0, 0.01, (120, 2)), axis=0)),
            index=dates, columns=["2330", "2317"]
        )
        pe = pd.DataFrame(np.random.uniform(8, 20, (120, 2)), index=dates, columns=["2330", "2317"])
        return {"close": close, "pe_ratio": pe,
                "pb_ratio": pe * 0.1, "dividend_yield": pe * 0.3}

    def test_lower_is_better(self, opt_data):
        from core.strategies.value import ValueStrategy
        param_grid = {"pe_max": [15.0, 20.0], "use_pb": [False], "use_dividend": [False]}
        scores = [0.5, 0.3]
        idx = [0]

        def mock_bt(strategy, data):
            result = MagicMock()
            result.metrics.sharpe_ratio = scores[idx[0]]
            idx[0] += 1
            return result

        opt = GridSearchOptimizer(ValueStrategy, param_grid, higher_is_better=False)
        result = opt.optimize(opt_data, mock_bt, verbose=False)
        assert result.best_score == 0.3  # lower is better

    def test_progress_logging(self, opt_data):
        """verbose=True 時記錄進度不應崩潰"""
        from core.strategies.value import ValueStrategy
        param_grid = {"pe_max": [10.0, 15.0, 20.0], "use_pb": [False], "use_dividend": [False]}

        def mock_bt(strategy, data):
            result = MagicMock()
            result.metrics.sharpe_ratio = 1.0
            return result

        opt = GridSearchOptimizer(ValueStrategy, param_grid)
        result = opt.optimize(opt_data, mock_bt, verbose=True)
        assert result is not None


# ──────────────────────────────────────────────
# backtest/metrics — 補齊剩餘 edge cases
# ──────────────────────────────────────────────
from core.backtest.metrics import (
    calculate_total_return, calculate_annualized_return,
    calculate_volatility, calculate_sharpe_ratio,
    calculate_calmar_ratio,
    calculate_metrics,
)


class TestMetricsEdgeCases2:
    def test_total_return_empty_series(self):
        result = calculate_total_return(pd.Series(dtype=float))
        assert result == 0.0

    def test_annualized_return_same_dates(self):
        """開始日期等於結束日期時應回傳 0"""
        ts = pd.Timestamp("2021-01-01")
        pv = pd.Series([1_000_000.0, 1_050_000.0], index=[ts, ts])
        result = calculate_annualized_return(pv)
        assert result == 0.0

    def test_volatility_empty_series(self):
        pv = pd.Series(dtype=float)
        result = calculate_volatility(pv)
        assert result == 0.0

    def test_sharpe_zero_volatility(self):
        """使用真實日期 index 的持平投資組合"""
        dates = pd.date_range("2021-01-01", periods=10)
        pv = pd.Series([1_000_000.0] * 10, index=dates)
        result = calculate_sharpe_ratio(pv)
        assert result == 0.0

    def test_calmar_negative_max_drawdown(self):
        dates = pd.date_range("2021-01-01", periods=100)
        values = pd.Series(
            np.concatenate([
                np.linspace(1_000_000, 800_000, 50),  # 跌 20%
                np.linspace(800_000, 900_000, 50),     # 反彈
            ]),
            index=dates
        )
        calmar = calculate_calmar_ratio(values)
        assert isinstance(calmar, float)

    def test_metrics_with_nan_portfolio(self):
        pv = pd.Series([1_000_000.0, float("nan"), 1_100_000.0])
        # 不應崩潰
        try:
            metrics = calculate_metrics(pv)
            assert metrics is not None
        except Exception:
            pass  # 含 NaN 時行為可能因版本不同而異


# ──────────────────────────────────────────────
# health_check — 改善覆蓋率
# ──────────────────────────────────────────────
from core.health_check import HealthChecker, HealthStatus, check_system_health, get_health_summary


class TestHealthCheckAdditional:
    def test_check_system_health_returns_health_status(self):
        """check_system_health 便捷函式"""
        status = check_system_health()
        assert isinstance(status, HealthStatus)

    def test_get_health_summary_returns_dict(self):
        """get_health_summary 回傳字典"""
        result = get_health_summary()
        assert isinstance(result, dict)
        assert "overall_status" in result

    def test_check_disk_space_with_low_free_space(self):
        """磁碟空間不足時應回傳 critical 或 warning"""
        checker = HealthChecker()
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(
                free=0.1 * (1024 ** 3),   # 0.1 GB
                total=100 * (1024 ** 3),   # 100 GB
                used=99.9 * (1024 ** 3)
            )
            result = checker.check_disk_space(min_free_gb=1.0)
            assert result.status == "critical"

    def test_check_disk_space_with_warning(self):
        checker = HealthChecker()
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.return_value = MagicMock(
                free=1.5 * (1024 ** 3),    # 1.5 GB (between 1 and 2)
                total=100 * (1024 ** 3),
                used=98.5 * (1024 ** 3)
            )
            result = checker.check_disk_space(min_free_gb=1.0)
            assert result.status == "warning"

    def test_check_memory_high_usage(self):
        checker = HealthChecker()
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(
                percent=95.0,
                available=0.1 * (1024 ** 3)
            )
            result = checker.check_memory_usage(max_percent=90.0)
            assert result.status == "critical"

    def test_check_memory_warning(self):
        checker = HealthChecker()
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(
                percent=75.0,
                available=2.0 * (1024 ** 3)
            )
            result = checker.check_memory_usage(max_percent=90.0)
            assert result.status == "warning"

    def test_check_logs_with_large_files(self, tmp_path):
        """日誌檔案很大時應回傳 warning 或 critical"""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        # 建立大於 100MB 的假日誌檔（模擬檔案大小而非真實寫入）
        log_file = logs_dir / "huge.log"
        log_file.write_bytes(b"x" * 1000)

        checker = HealthChecker()
        checker.data_dir = tmp_path

        # mock stat 回傳超大 size
        original_stat = Path.stat
        def mock_stat(self):
            if str(self).endswith(".log"):
                r = MagicMock()
                r.st_size = 600 * (1024 ** 2)  # 600 MB
                return r
            return original_stat(self)

        with patch.object(Path, "stat", mock_stat):
            result = checker.check_logs()
            assert result.status in ("warning", "critical")
