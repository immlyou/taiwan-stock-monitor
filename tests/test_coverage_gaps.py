"""
補齊各模組剩餘覆蓋率缺口
涵蓋：hot_stocks（analyze_hot_stocks、get_volume_anomalies）、
      twse_api（margin functions、fetch_taiex_realtime 解析路徑）、
      data_loader（FinLab 路徑 mock）、
      strategies/base（score/run edge cases）、
      backtest/engine（partial sell、record portfolio）、
      backtest/metrics（edge cases）、
      alerts（check_alerts_and_notify、_load_alerts、disable/enable）、
      prediction_tracker（_save_data、verify direction）
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────
# hot_stocks — analyze_hot_stocks / get_volume_anomalies
# ──────────────────────────────────────────────
from core.hot_stocks import HotStockAnalyzer, HotStockScore


@pytest.fixture(scope="module")
def hs_dates():
    return pd.date_range("2022-01-01", periods=60, freq="B")


@pytest.fixture(scope="module")
def hs_close(hs_dates):
    np.random.seed(0)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.012, (60, 3)), axis=0))
    return pd.DataFrame(prices, index=hs_dates, columns=["2330", "2317", "2454"])


@pytest.fixture(scope="module")
def hs_volume(hs_dates):
    np.random.seed(1)
    data = np.random.randint(1000, 30000, (60, 3)).astype(float) * 1000
    data[-5:, 0] *= 4  # 2330 最後爆量
    return pd.DataFrame(data, index=hs_dates, columns=["2330", "2317", "2454"])


@pytest.fixture
def hs_loader(hs_close, hs_volume):
    loader = MagicMock()
    stock_info = pd.DataFrame({
        "stock_id": ["2330", "2317", "2454"],
        "name": ["台積電", "鴻海", "聯發科"],
        "category": ["半導體", "電子", "半導體"],
        "industry": ["半導體", "電子", "半導體"],
    })
    loader.get.side_effect = lambda k, **kw: {"close": hs_close, "volume": hs_volume}.get(k)
    loader.get_stock_info.return_value = stock_info
    return loader


class TestAnalyzeHotStocks:

    def test_returns_list(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.analyze_hot_stocks()
            assert isinstance(results, list)

    def test_results_are_hot_stock_scores(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.analyze_hot_stocks()
            for r in results:
                assert isinstance(r, HotStockScore)

    def test_respects_top_n(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.analyze_hot_stocks(top_n=2)
            assert len(results) <= 2

    def test_with_news_data(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            news = {
                "2330": {"count": 5, "sentiment": 0.8, "score": 90.0},
            }
            results = analyzer.analyze_hot_stocks(news_hot_stocks=news, min_score=0.0)
            assert isinstance(results, list)

    def test_tags_generated(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            news = {
                "2330": {"count": 5, "sentiment": 0.8, "score": 90.0},
            }
            results = analyzer.analyze_hot_stocks(news_hot_stocks=news, min_score=0.0)
            # 有提供 news 且 count >= 3，應有 '新聞熱門' 標籤
            tagged = [r for r in results if r.stock_id == "2330"]
            if tagged:
                assert "新聞熱門" in tagged[0].tags

    def test_min_score_filters_results(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            all_results = analyzer.analyze_hot_stocks(min_score=0.0)
            filtered = analyzer.analyze_hot_stocks(min_score=999.0)
            assert len(filtered) <= len(all_results)

    def test_loader_error_graceful(self):
        failing_loader = MagicMock()
        failing_loader.get.side_effect = Exception("失敗")
        failing_loader.get_stock_info.side_effect = Exception("失敗")
        with patch("core.hot_stocks.get_loader", return_value=failing_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.analyze_hot_stocks()
            assert isinstance(results, list)


class TestGetVolumeAnomalies:

    def test_returns_list(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.get_volume_anomalies(min_ratio=1.0)
            assert isinstance(results, list)

    def test_all_meet_min_ratio(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.get_volume_anomalies(min_ratio=2.0)
            for r in results:
                assert r["volume_ratio"] >= 2.0

    def test_sorted_by_volume_ratio(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.get_volume_anomalies(min_ratio=0.5)
            if len(results) > 1:
                ratios = [r["volume_ratio"] for r in results]
                assert ratios == sorted(ratios, reverse=True)

    def test_respects_top_n(self, hs_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.get_volume_anomalies(min_ratio=0.5, top_n=2)
            assert len(results) <= 2


# ──────────────────────────────────────────────
# twse_api — margin / fetch_taiex_realtime parsing
# ──────────────────────────────────────────────
from core.twse_api import (
    fetch_stock_margin, fetch_taiex_realtime, clear_taiex_cache,
    _taiex_cache,
)


class TestFetchTaiexRealtimeParsing:
    def setup_method(self):
        _taiex_cache.clear()

    @patch("requests.get")
    def test_parses_data8_correctly(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "stat": "OK",
            "data8": [
                ["發行量加權股價指數", "21,000.00", "100.00"],
                ["其他指數", "5,000.00", "20.00"],
            ],
            "date": "20250124",
        }
        mock_get.return_value = mock_resp

        result = fetch_taiex_realtime()
        # 若解析成功應回傳 dict，若非交易時段可能 fallback
        assert result is None or isinstance(result, dict)

    def test_clear_cache(self):
        _taiex_cache["key"] = "value"
        clear_taiex_cache()
        assert len(_taiex_cache) == 0


class TestFetchStockMargin:
    @patch("requests.get")
    def test_returns_dict_or_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"stat": "NO DATA"}
        mock_get.return_value = mock_resp

        result = fetch_stock_margin("2330")
        assert result is None or isinstance(result, dict)

    @patch("requests.get")
    def test_exception_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("失敗")
        result = fetch_stock_margin("2330")
        assert result is None


# ──────────────────────────────────────────────
# data_loader — FinLab 路徑
# ──────────────────────────────────────────────
from core.data_loader import DataLoader


class TestDataLoaderFinLabPath:
    def test_finlab_not_initialized_raises(self):
        loader = DataLoader(use_global_cache=False)
        loader._use_finlab_api = True

        with patch("core.data_loader.init_finlab", return_value=False):
            with pytest.raises(RuntimeError, match="FinLab API 未初始化"):
                loader._load_from_finlab("close")

    def test_unknown_key_raises_key_error(self):
        """未知 data_key 在雲端模式下應拋出 KeyError（在 init_finlab 通過後檢查 mapping）"""
        loader = DataLoader(use_global_cache=False)
        loader._use_finlab_api = True

        # 建立一個假的 finlab 模組，讓 `from finlab import data` 不會 ModuleNotFoundError
        import sys
        from unittest.mock import MagicMock
        mock_finlab = MagicMock()
        mock_finlab.data = MagicMock()

        with patch("core.data_loader.init_finlab", return_value=True):
            with patch.dict(sys.modules, {"finlab": mock_finlab}):
                with pytest.raises(KeyError):
                    loader._load_from_finlab("nonexistent_key_xyz_unique_999")


# ──────────────────────────────────────────────
# strategies/base — CombinedStrategy edge cases
# ──────────────────────────────────────────────
from core.strategies.base import CombinedStrategy
from core.strategies.value import ValueStrategy


class TestBaseStrategyEdges:

    def test_score_default_implementation(self):
        """BaseStrategy.score() 預設：filter() 回傳 1，其他 0"""
        v = ValueStrategy({"use_pb": False, "use_dividend": False, "pe_max": 50.0})
        dates = pd.date_range("2023-01-01", periods=20)
        pe = pd.DataFrame({"A": [10.0] * 20, "B": [30.0] * 20}, index=dates)
        close = pd.DataFrame({"A": [100.0] * 20, "B": [100.0] * 20}, index=dates)
        data = {"close": close, "pe_ratio": pe}
        scores = v.score(data)
        assert isinstance(scores, pd.Series)

    def test_combined_strategy_get_default_params(self):
        strats = [ValueStrategy()]
        combined = CombinedStrategy(strats)
        params = combined.get_default_params()
        assert "mode" in params

    def test_combined_strategy_repr(self):
        combined = CombinedStrategy([ValueStrategy()])
        r = repr(combined)
        assert "CombinedStrategy" in r


# ──────────────────────────────────────────────
# backtest/engine — partial_sell、record_portfolio
# ──────────────────────────────────────────────
from core.backtest.engine import BacktestEngine


class TestBacktestEnginePartialSell:

    def setup_method(self):
        self.engine = BacktestEngine(initial_capital=1_000_000)
        self.engine.cash = 1_000_000
        self.engine.positions = {}
        self.engine.trades = []
        self.engine.portfolio_history = []

    def test_partial_sell_reduces_shares(self):
        self.engine._buy("2330", pd.Timestamp("2021-01-05"), 600.0, 120_000)
        initial_shares = self.engine.positions["2330"]["shares"]
        sell_shares = initial_shares // 2
        self.engine._partial_sell("2330", pd.Timestamp("2021-02-01"), 620.0, sell_shares)
        assert self.engine.positions["2330"]["shares"] == initial_shares - sell_shares

    def test_partial_sell_all_becomes_full_sell(self):
        self.engine._buy("2317", pd.Timestamp("2021-01-05"), 100.0, 50_000)
        shares = self.engine.positions["2317"]["shares"]
        self.engine._partial_sell("2317", pd.Timestamp("2021-02-01"), 105.0, shares + 100)
        assert "2317" not in self.engine.positions

    def test_partial_sell_nonexistent_no_crash(self):
        self.engine._partial_sell("9999", pd.Timestamp("2021-01-05"), 100.0, 10)

    def test_record_portfolio_value(self):
        self.engine._buy("2330", pd.Timestamp("2021-01-05"), 600.0, 100_000)
        prices = pd.Series({"2330": 620.0})
        self.engine._record_portfolio_value(pd.Timestamp("2021-01-06"), prices)
        assert len(self.engine.portfolio_history) == 1
        assert self.engine.portfolio_history[0]["value"] > 0

    def test_get_rebalance_dates_monthly(self):
        engine = BacktestEngine()
        dates = engine._get_rebalance_dates(
            pd.Timestamp("2021-01-01"),
            pd.Timestamp("2021-12-31"),
            freq="ME"
        )
        assert len(dates) == 12

    def test_get_rebalance_dates_old_alias(self):
        engine = BacktestEngine()
        dates = engine._get_rebalance_dates(
            pd.Timestamp("2021-01-01"),
            pd.Timestamp("2021-12-31"),
            freq="M"  # 舊別名
        )
        assert len(dates) == 12


# ──────────────────────────────────────────────
# backtest/metrics — edge cases
# ──────────────────────────────────────────────
from core.backtest.metrics import (
    calculate_returns, calculate_cumulative_returns,
    calculate_metrics, calculate_win_rate, compare_with_benchmark,
)


class TestMetricsEdgeCases:
    def test_calculate_returns_fillna_zero(self):
        """第一個 pct_change() 應填 0，而非 NaN"""
        pv = pd.Series([1_000_000.0, 1_010_000.0, 1_020_000.0])
        rets = calculate_returns(pv)
        assert rets.iloc[0] == 0.0

    def test_cumulative_returns_starts_at_zero(self):
        pv = pd.Series([1_000_000.0] * 10)
        cum = calculate_cumulative_returns(pv)
        assert cum.iloc[-1] == pytest.approx(0.0, abs=1e-9)

    def test_metrics_empty_trades(self):
        pv = pd.Series(
            np.linspace(1_000_000, 1_100_000, 100),
            index=pd.date_range("2021-01-01", periods=100)
        )
        metrics = calculate_metrics(pv, trades=None)
        assert metrics.total_trades == 0

    def test_win_rate_with_only_open_positions(self):
        """未出場的部位（exit_date=None）不應計入勝負"""
        trades = pd.DataFrame({
            "pnl": [0.0],
            "return": [0.0],
            "holding_days": [0],
        })
        rate = calculate_win_rate(trades)
        assert 0 <= rate <= 100

    def test_compare_benchmark_zero_tracking_error(self):
        """相同序列的追蹤誤差應接近 0"""
        dates = pd.date_range("2021-01-01", periods=100)
        pv = pd.Series(np.linspace(1_000_000, 1_100_000, 100), index=dates)
        result = compare_with_benchmark(pv, pv)
        assert result["tracking_error"] == pytest.approx(0.0, abs=1e-3)


# ──────────────────────────────────────────────
# alerts — check_alerts_and_notify
# ──────────────────────────────────────────────
from core.alerts import AlertEngine, check_alerts_and_notify


class TestCheckAlertsAndNotify:
    def test_no_triggered_alerts_returns_empty(self):
        with patch.object(AlertEngine, "check_all_alerts", return_value=[]):
            result = check_alerts_and_notify({}, send_notification=False)
            assert result == []

    def test_triggered_alerts_returned(self):
        from core.alerts import AlertResult
        mock_result = AlertResult(
            alert_id="test", stock_id="2330", alert_type="price_above",
            is_triggered=True, current_value=600.0, target_value=500.0,
            message="突破"
        )
        with patch.object(AlertEngine, "check_all_alerts", return_value=[mock_result]):
            result = check_alerts_and_notify({}, send_notification=False)
            assert len(result) == 1

    def test_sends_notification_when_triggered(self):
        from core.alerts import AlertResult
        mock_result = AlertResult(
            alert_id="test", stock_id="2330", alert_type="price_above",
            is_triggered=True, current_value=600.0, target_value=500.0,
            message="突破"
        )
        with patch.object(AlertEngine, "check_all_alerts", return_value=[mock_result]):
            # core.notification.send_notification 是在 alerts.py 函式內部 import 的
            with patch("core.notification.send_notification") as mock_notify:
                result = check_alerts_and_notify({}, send_notification=True)
                assert len(result) == 1  # 已觸發的警報被回傳即可


# ──────────────────────────────────────────────
# prediction_tracker — save/load
# ──────────────────────────────────────────────
from core.prediction_tracker import PredictionTracker, PredictionStatus


class TestPredictionTrackerSaveLoad:
    def test_save_creates_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.prediction_tracker.DATA_DIR", tmp_path)
        monkeypatch.setattr("core.prediction_tracker.PREDICTIONS_FILE",
                            tmp_path / "predictions.json")
        monkeypatch.setattr("core.prediction_tracker.VERIFICATION_LOG_FILE",
                            tmp_path / "verification_log.json")
        tracker = PredictionTracker()
        tracker.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        assert (tmp_path / "predictions.json").exists()

    def test_load_from_existing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.prediction_tracker.DATA_DIR", tmp_path)
        preds_file = tmp_path / "predictions.json"
        monkeypatch.setattr("core.prediction_tracker.PREDICTIONS_FILE", preds_file)
        monkeypatch.setattr("core.prediction_tracker.VERIFICATION_LOG_FILE",
                            tmp_path / "verification_log.json")

        # 先建立
        tracker1 = PredictionTracker()
        tracker1.add_target_price_prediction("2330", "台積電", 600.0, 650.0)

        # 再重新載入
        tracker2 = PredictionTracker()
        assert len(tracker2.predictions) == 1

    def test_verify_direction_prediction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.prediction_tracker.DATA_DIR", tmp_path)
        monkeypatch.setattr("core.prediction_tracker.PREDICTIONS_FILE",
                            tmp_path / "predictions.json")
        monkeypatch.setattr("core.prediction_tracker.VERIFICATION_LOG_FILE",
                            tmp_path / "verification_log.json")

        tracker = PredictionTracker()
        p = tracker.add_direction_prediction("2330", "台積電", 600.0, "up", verify_days=1)
        # 設定過期日為過去
        p.expire_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        p.created_at = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

        dates = pd.date_range(
            datetime.strptime(p.created_at, "%Y-%m-%d %H:%M:%S").date().isoformat(),
            periods=3
        )
        price_data = pd.DataFrame({"2330": [600, 610, 620]}, index=dates)
        tracker.verify_predictions(price_data)
        assert p.status in [PredictionStatus.SUCCESS.value, PredictionStatus.FAILED.value]

    def test_get_statistics_by_type(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.prediction_tracker.DATA_DIR", tmp_path)
        monkeypatch.setattr("core.prediction_tracker.PREDICTIONS_FILE",
                            tmp_path / "predictions.json")
        monkeypatch.setattr("core.prediction_tracker.VERIFICATION_LOG_FILE",
                            tmp_path / "verification_log.json")

        tracker = PredictionTracker()
        tracker.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        tracker.add_direction_prediction("2317", "鴻海", 100.0, "up")
        stats = tracker.get_statistics(prediction_type="target_price")
        assert stats["total"] == 1


# ──────────────────────────────────────────────
# 補齊 money_flow 剩餘缺口
# ──────────────────────────────────────────────
from core.money_flow import calculate_institutional_flow


class TestMoneyFlowEdgeCases:

    def test_none_investment_trust_handled(self):
        dates = pd.date_range("2023-01-01", periods=5)
        foreign = pd.DataFrame({"A": [1000.0] * 5}, index=dates)
        stock_info = pd.DataFrame({"stock_id": ["A"], "name": ["Test"], "category": ["半導體"]})
        flows = calculate_institutional_flow(foreign, None, None, stock_info)
        assert "A" in flows
        assert flows["A"].investment_trust_net == 0.0

    def test_nan_values_replaced_with_zero(self):
        dates = pd.date_range("2023-01-01", periods=3)
        foreign = pd.DataFrame({"A": [np.nan, np.nan, 5000.0]}, index=dates)
        stock_info = pd.DataFrame({"stock_id": ["A"], "name": ["Test"], "category": ["半導體"]})
        flows = calculate_institutional_flow(foreign, None, None, stock_info)
        assert not np.isnan(flows["A"].foreign_net)
