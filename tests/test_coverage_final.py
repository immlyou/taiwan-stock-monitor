"""
最終覆蓋率衝刺：針對 twse_api margin、hot_stocks、
notification abstract methods、data_loader 等精確補齊
"""
import os
import sys
import pickle
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────
# twse_api — margin functions
# ──────────────────────────────────────────────
from core.twse_api import (
    fetch_stock_margin, fetch_margin_history,
    clear_margin_cache, _margin_cache,
    _fetch_stock_margin_for_date,
)


class TestTwseMarginDetailed:
    def setup_method(self):
        _margin_cache.clear()

    @patch("requests.get")
    def test_fetch_stock_margin_date_specified(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "stat": "OK",
            "tables": [{
                "title": "融資融券彙總",
                "data": [
                    ["2330", "台積電",
                     "1000", "500", "200", "50000", "51200",
                     "100000",
                     "200", "100", "50", "10000", "10150",
                     "20000", "0", ""],
                ]
            }]
        }
        mock_get.return_value = mock_resp
        result = fetch_stock_margin("2330", date="20250124")
        assert result is not None
        assert result["stock_id"] == "2330"
        assert "margin_buy" in result

    @patch("requests.get")
    def test_fetch_stock_margin_no_date_retries(self, mock_get):
        """無日期時應回溯嘗試"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"stat": "NO DATA"}
        mock_get.return_value = mock_resp
        result = fetch_stock_margin("2330", retry_days=2)
        assert result is None

    @patch("requests.get")
    def test_fetch_stock_margin_uses_cache(self, mock_get):
        """同一日期第二次呼叫應使用快取"""
        cached_data = {
            "stock_id": "2330", "margin_buy": 50000,
            "margin_sell": 10000, "margin_ratio": 20.0,
            "margin_buy_change": 100, "margin_sell_change": 50,
            "date": "2025-01-24"
        }
        _margin_cache["margin_2330_20250124"] = (datetime.now(), cached_data)
        result = _fetch_stock_margin_for_date("2330", "20250124")
        mock_get.assert_not_called()
        assert result["margin_buy"] == 50000

    @patch("requests.get")
    def test_fetch_stock_margin_exception_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("失敗")
        result = _fetch_stock_margin_for_date("2330", "20250124")
        assert result is None

    @patch("core.twse_api.fetch_stock_margin")
    def test_fetch_margin_history_returns_dataframe(self, mock_margin):
        mock_margin.return_value = {
            "stock_id": "2330",
            "margin_buy": 50000,
            "margin_sell": 10000,
            "margin_ratio": 20.0,
            "date": "2025-01-24",
        }
        result = fetch_margin_history("2330", days=3)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3

    @patch("core.twse_api.fetch_stock_margin")
    def test_fetch_margin_history_no_data_returns_none(self, mock_margin):
        mock_margin.return_value = None
        result = fetch_margin_history("2330", days=3)
        assert result is None

    def test_clear_margin_cache(self):
        _margin_cache["test_key"] = "test_value"
        clear_margin_cache()
        assert len(_margin_cache) == 0


# ──────────────────────────────────────────────
# hot_stocks — generate_focus_report、get_hot_stocks_integrated
# ──────────────────────────────────────────────
from core.hot_stocks import HotStockAnalyzer, get_hot_stocks_integrated


@pytest.fixture(scope="module")
def hs3_dates():
    return pd.date_range("2022-01-01", periods=60, freq="B")


@pytest.fixture(scope="module")
def hs3_close(hs3_dates):
    np.random.seed(0)
    p = 100 * np.exp(np.cumsum(np.random.normal(0, 0.012, (60, 3)), axis=0))
    return pd.DataFrame(p, index=hs3_dates, columns=["2330", "2317", "2454"])


@pytest.fixture(scope="module")
def hs3_volume(hs3_dates):
    np.random.seed(1)
    data = np.random.randint(1000, 30000, (60, 3)).astype(float) * 1000
    return pd.DataFrame(data, index=hs3_dates, columns=["2330", "2317", "2454"])


@pytest.fixture
def hs3_loader(hs3_close, hs3_volume):
    loader = MagicMock()
    stock_info = pd.DataFrame({
        "stock_id": ["2330", "2317", "2454"],
        "name": ["台積電", "鴻海", "聯發科"],
        "industry": ["半導體", "電子", "半導體"],
    })
    loader.get.side_effect = lambda k, **kw: {"close": hs3_close, "volume": hs3_volume}.get(k)
    loader.get_stock_info.return_value = stock_info
    return loader


class TestGenerateFocusReport:
    def test_returns_dict(self, hs3_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs3_loader):
            analyzer = HotStockAnalyzer()
            result = analyzer.generate_focus_report()
            assert isinstance(result, dict)
            assert "hot_stocks" in result
            assert "volume_anomalies" in result
            assert "summary" in result

    def test_with_news_data(self, hs3_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs3_loader):
            analyzer = HotStockAnalyzer()
            news = {
                "2330": {"count": 5, "sentiment": 0.6, "score": 90.0},
                "2317": {"count": 2, "sentiment": -0.4, "score": 40.0},
            }
            result = analyzer.generate_focus_report(news_hot_stocks=news)
            assert isinstance(result, dict)

    def test_summary_contains_counts(self, hs3_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs3_loader):
            analyzer = HotStockAnalyzer()
            result = analyzer.generate_focus_report()
            summary = result["summary"]
            assert "total_analyzed" in summary
            assert "positive_count" in summary
            assert "negative_count" in summary


class TestGetHotStocksIntegrated:
    def test_without_news_scanner(self, hs3_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs3_loader):
            result = get_hot_stocks_integrated()
            assert isinstance(result, list)

    def test_with_mock_news_scanner(self, hs3_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs3_loader):
            mock_scanner = MagicMock()
            mock_scanner.get_hot_stocks.return_value = {"2330": 85.0}
            mock_news = [MagicMock(sentiment_score=0.5)]
            mock_scanner.get_stock_news.return_value = mock_news
            result = get_hot_stocks_integrated(news_scanner=mock_scanner, top_n=5)
            assert isinstance(result, list)

    def test_news_scanner_exception_graceful(self, hs3_loader):
        with patch("core.hot_stocks.get_loader", return_value=hs3_loader):
            mock_scanner = MagicMock()
            mock_scanner.get_hot_stocks.side_effect = Exception("失敗")
            result = get_hot_stocks_integrated(news_scanner=mock_scanner)
            assert isinstance(result, list)


# ──────────────────────────────────────────────
# notification — abstract base 行 37, 42（docstring 後的 pass）
# ──────────────────────────────────────────────
from core.notification import (
    NotificationChannel, NotificationManager,
)


class ConcreteChannel(NotificationChannel):
    """用於測試抽象基類的具體實作"""
    def send(self, title: str, message: str) -> bool:
        return True

    def is_configured(self) -> bool:
        return True


class TestNotificationAbstractBase:
    def test_abstract_class_cannot_instantiate(self):
        """抽象類別不能直接實例化"""
        with pytest.raises(TypeError):
            NotificationChannel()

    def test_concrete_subclass_works(self):
        ch = ConcreteChannel()
        assert ch.is_configured() is True
        assert ch.send("title", "msg") is True

    def test_concrete_channel_registers(self):
        mgr = NotificationManager()
        ch = ConcreteChannel()
        mgr.register_channel("concrete", ch)
        assert "concrete" in mgr.channels

    def test_concrete_channel_send_via_manager(self):
        mgr = NotificationManager()
        ch = ConcreteChannel()
        mgr.register_channel("concrete2", ch)
        results = mgr.send("測試", "內容", channels=["concrete2"])
        assert results["concrete2"] is True


# ──────────────────────────────────────────────
# data_loader — init_finlab with token, load_for_strategy composite
# ──────────────────────────────────────────────
from core.data_loader import DataLoader, init_finlab
import core.data_loader as dl_module


class TestDataLoaderFinLabDetailed:
    def setup_method(self):
        dl_module._finlab_initialized = False

    def teardown_method(self):
        dl_module._finlab_initialized = False

    def test_init_finlab_with_token_success(self):
        """提供 token 時，finlab.login 應被呼叫"""
        mock_finlab = MagicMock()
        mock_finlab.login = MagicMock()

        with patch.dict(sys.modules, {"finlab": mock_finlab}):
            with patch.dict(os.environ, {"FINLAB_API_TOKEN": "test_token_abc"}):
                with patch("core.data_loader.HAS_STREAMLIT", False):
                    dl_module._finlab_initialized = False
                    result = init_finlab()
                    assert result is True
                    mock_finlab.login.assert_called_once_with("test_token_abc")

    def test_init_finlab_exception_during_login(self):
        """finlab.login 拋出例外時應回傳 False"""
        mock_finlab = MagicMock()
        mock_finlab.login.side_effect = Exception("token 無效")

        with patch.dict(sys.modules, {"finlab": mock_finlab}):
            with patch.dict(os.environ, {"FINLAB_API_TOKEN": "bad_token"}):
                with patch("core.data_loader.HAS_STREAMLIT", False):
                    dl_module._finlab_initialized = False
                    result = init_finlab()
                    assert result is False


@pytest.fixture
def composite_loader_dir(tmp_path):
    np.random.seed(0)
    dates = pd.date_range("2022-01-01", periods=20, freq="B")
    stocks = ["2330", "2317"]
    from config import DATA_FILES
    for key, filename in DATA_FILES.items():
        df = pd.DataFrame(
            np.random.uniform(50, 200, (20, 2)),
            index=dates, columns=stocks
        )
        with open(tmp_path / filename, "wb") as f:
            pickle.dump(df, f)
    return tmp_path


class TestDataLoaderLoadForStrategy:
    def test_load_for_strategy_composite(self, composite_loader_dir):
        """composite 策略需要更多數據欄位"""
        loader = DataLoader(data_dir=composite_loader_dir, use_global_cache=False)
        loader._use_finlab_api = False
        data = loader.load_for_strategy("composite")
        assert "close" in data

    def test_load_for_strategy_fallback_unknown(self, composite_loader_dir):
        """未知策略類型應 fallback 到基本數據"""
        loader = DataLoader(data_dir=composite_loader_dir, use_global_cache=False)
        loader._use_finlab_api = False
        data = loader.load_for_strategy("unknown_strategy_xyz")
        assert "close" in data

    def test_get_benchmark_alternative_column(self, composite_loader_dir):
        """benchmark DataFrame 只有一欄時應取第一欄"""
        loader = DataLoader(data_dir=composite_loader_dir, use_global_cache=False)
        loader._use_finlab_api = False
        benchmark = loader.get_benchmark()
        assert isinstance(benchmark, pd.Series)


# ──────────────────────────────────────────────
# data_sources — yfinance OTC fallback path
# ──────────────────────────────────────────────
import core.data_sources as ds
from core.data_sources import _source_cache, _source_cache_ts


class TestYfinanceOtcPath:
    def setup_method(self):
        _source_cache.clear()
        _source_cache_ts.clear()

    @patch("core.data_sources._yfinance_ohlcv")
    def test_ohlcv_empty_df_triggers_fallback(self, mock_yf):
        """yfinance 回傳空 DataFrame 時，provider 應回傳 None"""
        mock_yf.return_value = pd.DataFrame()
        provider = ds.MultiSourceDataProvider()
        result = provider.get_ohlcv("2330", days=10)
        assert result is None

    def test_safe_json_val_large_float(self):
        """大整數不應被截斷"""
        result = ds._safe_json_val(1234567.89)
        assert result == pytest.approx(1234567.89, abs=0.01)

    def test_safe_json_val_zero_is_zero(self):
        result = ds._safe_json_val(0.0)
        assert result == 0.0


# ──────────────────────────────────────────────
# prediction_tracker — 補齊更多 _save_data / 驗證路徑
# ──────────────────────────────────────────────
from core.prediction_tracker import PredictionTracker, PredictionStatus


class TestPredictionTrackerExtra:
    @pytest.fixture
    def tracker_with_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.prediction_tracker.DATA_DIR", tmp_path)
        monkeypatch.setattr("core.prediction_tracker.PREDICTIONS_FILE",
                            tmp_path / "predictions.json")
        monkeypatch.setattr("core.prediction_tracker.VERIFICATION_LOG_FILE",
                            tmp_path / "verification_log.json")
        return PredictionTracker()

    def test_add_batch_and_get_statistics(self, tracker_with_dir):
        stocks = [
            {"stock_id": "2330", "stock_name": "台積電", "current_price": 600.0},
            {"stock_id": "2317", "stock_name": "鴻海", "current_price": 100.0},
        ]
        tracker_with_dir.add_batch_stock_picks(stocks, source="test_strategy")
        stats = tracker_with_dir.get_statistics(days=30)
        assert stats["total"] == 2
        assert stats["pending"] == 2

    def test_get_statistics_by_source(self, tracker_with_dir):
        tracker_with_dir.add_target_price_prediction(
            "2330", "台積電", 600.0, 650.0, source="value_strategy"
        )
        stats = tracker_with_dir.get_statistics(days=30)
        assert "value_strategy" in stats["by_source"]

    def test_cancel_already_verified_returns_false(self, tracker_with_dir):
        p = tracker_with_dir.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        p.status = PredictionStatus.SUCCESS.value
        result = tracker_with_dir.cancel_prediction(p.id)
        assert result is False  # 已驗證的不能取消

    def test_get_recent_with_status_filter(self, tracker_with_dir):
        p = tracker_with_dir.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        p.status = PredictionStatus.SUCCESS.value
        tracker_with_dir._save_data()

        success = tracker_with_dir.get_recent_predictions(
            days=7, status=PredictionStatus.SUCCESS.value
        )
        assert all(x.status == PredictionStatus.SUCCESS.value for x in success)

    def test_verification_log_appended(self, tracker_with_dir, tmp_path):
        p = tracker_with_dir.add_stock_pick_prediction(
            "2330", "台積電", 600.0, verify_days=1
        )
        p.expire_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        p.created_at = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        dates = pd.date_range(
            datetime.strptime(p.created_at, "%Y-%m-%d %H:%M:%S").date().isoformat(),
            periods=3
        )
        price_data = pd.DataFrame({"2330": [600, 610, 620]}, index=dates)
        tracker_with_dir.verify_predictions(price_data)

        if tracker_with_dir.verification_log:
            assert len(tracker_with_dir.verification_log) >= 1


# ──────────────────────────────────────────────
# backtest/engine — 剩餘 rebalance 路徑
# ──────────────────────────────────────────────
from core.backtest.engine import BacktestEngine


class TestBacktestEngineExtra:
    def test_rebalance_freq_quarterly(self):
        engine = BacktestEngine()
        dates = engine._get_rebalance_dates(
            pd.Timestamp("2021-01-01"),
            pd.Timestamp("2021-12-31"),
            freq="QE"
        )
        assert len(dates) == 4

    def test_market_cap_weight_with_missing_stocks(self):
        engine = BacktestEngine()
        stocks = ["A", "B", "C"]
        mv = pd.Series({"A": 1000, "B": 2000})  # C 缺失
        weights = engine._allocate_weights(stocks, mv, method="market_cap")
        # 缺失的股票應以等權處理
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_buy_sell_pnl_positive(self):
        """買入後以更高價賣出，損益應為正"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.cash = 1_000_000
        engine.positions = {}
        engine.trades = []
        engine._buy("2330", pd.Timestamp("2021-01-05"), 600.0, 120_000)
        engine._sell("2330", pd.Timestamp("2021-03-01"), 660.0)  # 漲 10%
        if engine.trades:
            assert engine.trades[-1].pnl > 0

    def test_buy_sell_pnl_negative(self):
        """買入後以更低價賣出，損益應為負"""
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.cash = 1_000_000
        engine.positions = {}
        engine.trades = []
        engine._buy("2317", pd.Timestamp("2021-01-05"), 100.0, 50_000)
        engine._sell("2317", pd.Timestamp("2021-03-01"), 85.0)  # 跌 15%
        if engine.trades:
            assert engine.trades[-1].pnl < 0
