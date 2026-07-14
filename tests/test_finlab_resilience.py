"""FinLab 韌性層測試

涵蓋：
- _finlab_get_with_retry：短暫性錯誤（連線/逾時/5xx）的指數退避重試，
  前 N 次失敗、第 N+1 次成功 → 最終成功且呼叫次數正確。
- 額度錯誤絕不重試：data.get() 拋 quota 類錯誤 → 只呼叫一次、
  _finlab_quota_exceeded 變 True、raise FinLabQuotaExceededError。
- 非短暫性未知錯誤不重試 → 只呼叫一次、原樣往上拋。
- _is_transient_finlab_error 分類邏輯。
- MultiSourceDataProvider 多源 fallback：FinLab 失敗時退到下一來源（yfinance/TWSE/FinMind）。

說明：本機 framework Python 無法 import pandas，這些測試在 verify 階段的
venv 內執行。重試測試以 monkeypatch 換掉 time.sleep 避免實際延遲，
並把 _finlab_counter_date 設為今日台北日期，避免熔斷器跨日重置誤觸。
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

import core.data_loader as dl
from core.data_loader import DataLoader, FinLabQuotaExceededError
from core.timeutils import today_taipei


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def cloud_loader(tmp_path, monkeypatch):
    """雲端模式 loader，磁碟快取隔離到 tmp_path，熔斷狀態重置為今日。"""
    monkeypatch.setattr(DataLoader, "_FINLAB_DISK_CACHE_DIR", tmp_path)
    loader = DataLoader.__new__(DataLoader)
    loader._use_finlab_api = True
    loader._use_global_cache = False
    loader._cache = {}
    dl._finlab_quota_exceeded = False
    dl._finlab_usage_mb = 0.0
    # 設為今日台北日期，熔斷器不會在測試中誤觸跨日重置
    dl._finlab_counter_date = today_taipei()
    # 重試測試不要真的睡——把退避歸零
    monkeypatch.setattr(dl, "FINLAB_RETRY_MAX", 3)
    monkeypatch.setattr(dl, "FINLAB_RETRY_INITIAL_DELAY", 0.0)
    monkeypatch.setattr(dl, "FINLAB_RETRY_MAX_DELAY", 0.0)
    yield loader
    # teardown：還原模組級熔斷旗標，避免測試 body 設 True 洩漏到後續收集的測試檔
    # （這些是直接賦值的模組全域，不會像 monkeypatch 自動還原）。
    dl._finlab_quota_exceeded = False
    dl._finlab_usage_mb = 0.0


# ──────────────────────────────────────────────
# _is_transient_finlab_error 分類
# ──────────────────────────────────────────────

class TestIsTransientFinlabError:
    def test_connection_error_is_transient(self):
        assert dl._is_transient_finlab_error(requests.exceptions.ConnectionError("boom")) is True

    def test_timeout_is_transient(self):
        assert dl._is_transient_finlab_error(requests.exceptions.Timeout("slow")) is True

    def test_http_5xx_is_transient(self):
        resp = MagicMock()
        resp.status_code = 503
        err = requests.exceptions.HTTPError("503", response=resp)
        assert dl._is_transient_finlab_error(err) is True

    def test_http_4xx_not_transient(self):
        resp = MagicMock()
        resp.status_code = 404
        err = requests.exceptions.HTTPError("404", response=resp)
        assert dl._is_transient_finlab_error(err) is False

    def test_builtin_timeout_error_is_transient(self):
        assert dl._is_transient_finlab_error(TimeoutError("t")) is True

    def test_string_pattern_502(self):
        assert dl._is_transient_finlab_error(RuntimeError("502 Bad Gateway")) is True

    def test_string_pattern_service_unavailable(self):
        assert dl._is_transient_finlab_error(Exception("Service Unavailable")) is True

    def test_quota_error_not_transient(self):
        assert dl._is_transient_finlab_error(Exception("Usage exceed 5000 MB")) is False

    def test_unknown_error_not_transient(self):
        assert dl._is_transient_finlab_error(ValueError("某個不相關錯誤")) is False


# ──────────────────────────────────────────────
# _finlab_get_with_retry：短暫性錯誤重試
# ──────────────────────────────────────────────

class TestRetryTransient:
    def test_retries_then_succeeds(self, cloud_loader):
        """前 2 次拋短暫性錯誤、第 3 次成功 → 回傳結果、共呼叫 3 次。"""
        sentinel = object()
        data = MagicMock()
        data.get.side_effect = [
            requests.exceptions.ConnectionError("抖動 1"),
            requests.exceptions.Timeout("抖動 2"),
            sentinel,
        ]
        result = cloud_loader._finlab_get_with_retry(data, "price:收盤價")
        assert result is sentinel
        assert data.get.call_count == 3

    def test_succeeds_first_try_no_retry(self, cloud_loader):
        sentinel = object()
        data = MagicMock()
        data.get.return_value = sentinel
        result = cloud_loader._finlab_get_with_retry(data, "price:收盤價")
        assert result is sentinel
        assert data.get.call_count == 1

    def test_exhausts_retries_then_raises(self, cloud_loader):
        """持續短暫性錯誤 → 重試耗盡後往上拋；呼叫 = MAX + 1 次。"""
        data = MagicMock()
        data.get.side_effect = requests.exceptions.Timeout("一直逾時")
        with pytest.raises(requests.exceptions.Timeout):
            cloud_loader._finlab_get_with_retry(data, "price:收盤價")
        assert data.get.call_count == dl.FINLAB_RETRY_MAX + 1

    def test_non_transient_not_retried(self, cloud_loader):
        """非短暫性未知錯誤 → 不重試，只呼叫一次並原樣往上拋。"""
        data = MagicMock()
        data.get.side_effect = ValueError("不相關錯誤")
        with pytest.raises(ValueError):
            cloud_loader._finlab_get_with_retry(data, "price:收盤價")
        assert data.get.call_count == 1


# ──────────────────────────────────────────────
# _finlab_get_with_retry：額度錯誤絕不重試
# ──────────────────────────────────────────────

class TestRetryQuotaNeverRetried:
    def test_quota_error_single_call_sets_flag(self, cloud_loader):
        """quota 錯誤 → 只呼叫一次、設旗標、raise FinLabQuotaExceededError。"""
        data = MagicMock()
        data.get.side_effect = Exception("Usage exceed 5000 MB")
        with patch("core.finlab_quota_alerter.get_alerter") as mock_alerter:
            with pytest.raises(FinLabQuotaExceededError):
                cloud_loader._finlab_get_with_retry(data, "price:收盤價")
            mock_alerter.return_value.notify_quota_exceeded.assert_called_once()
        assert data.get.call_count == 1
        assert dl._finlab_quota_exceeded is True

    def test_quota_error_named_exception_not_retried(self, cloud_loader):
        """例外類別名稱含 quota → 視為額度錯誤，不重試。"""
        class FinlabQuotaError(Exception):
            pass

        data = MagicMock()
        data.get.side_effect = FinlabQuotaError("limit reached")
        with patch("core.finlab_quota_alerter.get_alerter"):
            with pytest.raises(FinLabQuotaExceededError):
                cloud_loader._finlab_get_with_retry(data, "price:收盤價")
        assert data.get.call_count == 1
        assert dl._finlab_quota_exceeded is True


# ──────────────────────────────────────────────
# _load_from_finlab 端到端：重試 + quota 不重試
# ──────────────────────────────────────────────

class TestLoadFromFinlabIntegration:
    def test_transient_then_success_normalizes(self, cloud_loader, monkeypatch):
        """_load_from_finlab：第一次短暫性錯誤、第二次成功 → 回傳標準化 DataFrame。"""
        import pandas as pd

        df = pd.DataFrame(
            {"2330": [1.0, 2.0], "2317": [3.0, 4.0]},
            index=pd.to_datetime(["2024-01-02", "2024-01-01"]),  # 故意亂序測 sort
        )
        fake_data = MagicMock()
        fake_data.get.side_effect = [
            requests.exceptions.ConnectionError("抖動"),
            df,
        ]

        monkeypatch.setattr(dl, "init_finlab", lambda: True)
        monkeypatch.setitem(dl.FINLAB_DATA_MAPPING, "close", "price:收盤價")
        import sys
        fake_finlab = MagicMock()
        fake_finlab.data = fake_data
        monkeypatch.setitem(sys.modules, "finlab", fake_finlab)

        result = cloud_loader._load_from_finlab("close")
        assert isinstance(result, pd.DataFrame)
        assert result.index.is_monotonic_increasing  # 已 sort
        assert fake_data.get.call_count == 2
        assert dl._finlab_quota_exceeded is False

    def test_quota_error_short_circuits_no_retry(self, cloud_loader, monkeypatch):
        """_load_from_finlab：quota 錯誤 → 只呼叫一次、設旗標、raise。"""
        fake_data = MagicMock()
        fake_data.get.side_effect = Exception("Usage exceed 5000 MB")

        monkeypatch.setattr(dl, "init_finlab", lambda: True)
        monkeypatch.setitem(dl.FINLAB_DATA_MAPPING, "close", "price:收盤價")
        import sys
        fake_finlab = MagicMock()
        fake_finlab.data = fake_data
        monkeypatch.setitem(sys.modules, "finlab", fake_finlab)

        with patch("core.finlab_quota_alerter.get_alerter"):
            with pytest.raises(FinLabQuotaExceededError):
                cloud_loader._load_from_finlab("close")
        assert fake_data.get.call_count == 1
        assert dl._finlab_quota_exceeded is True

    def test_breaker_open_skips_call(self, cloud_loader):
        """熔斷已開（今日額度超限）→ 函式開頭短路，根本不碰 data.get。"""
        dl._finlab_quota_exceeded = True
        dl._finlab_counter_date = today_taipei()
        with pytest.raises(FinLabQuotaExceededError):
            cloud_loader._load_from_finlab("close")


# ──────────────────────────────────────────────
# MultiSourceDataProvider 多源 fallback
# ──────────────────────────────────────────────

class TestMultiSourceFallback:
    """驗證 FinLab 不可用時，MultiSourceDataProvider 會退到下一個來源。"""

    def setup_method(self):
        from core.data_sources import _source_cache, _source_cache_ts
        _source_cache.clear()
        _source_cache_ts.clear()

    def test_ohlcv_falls_back_to_yfinance(self):
        """OHLCV：FinLab loader 失敗，退到 yfinance。"""
        import pandas as pd
        from core.data_sources import MultiSourceDataProvider

        # loader 模擬 FinLab 額度超限
        mock_loader = MagicMock()
        mock_loader.get.side_effect = FinLabQuotaExceededError("quota")

        dates = pd.date_range("2024-01-01", periods=5)
        yf_df = pd.DataFrame({
            "open": [100.0] * 5, "high": [105.0] * 5,
            "low": [98.0] * 5, "close": [102.0] * 5,
            "volume": [10000.0] * 5,
        }, index=dates)

        with patch("core.data_sources._yfinance_ohlcv", return_value=yf_df) as mock_yf:
            provider = MultiSourceDataProvider(loader=mock_loader)
            result = provider.get_ohlcv("2330", days=5)

        assert result is not None
        assert result["source"] == "yfinance"
        assert len(result["data"]) == 5
        mock_yf.assert_called_once()

    def test_ohlcv_all_sources_fail_returns_none(self):
        from core.data_sources import MultiSourceDataProvider

        mock_loader = MagicMock()
        mock_loader.get.side_effect = FinLabQuotaExceededError("quota")

        with patch("core.data_sources._yfinance_ohlcv", return_value=None):
            provider = MultiSourceDataProvider(loader=mock_loader)
            result = provider.get_ohlcv("2330", days=5)
        assert result is None

    def test_institutional_falls_back_to_twse(self):
        """三大法人：退到 TWSE T86。"""
        from core.data_sources import MultiSourceDataProvider

        twse_result = {
            "stock_id": "2330",
            "外資": {"total_shares": 1000, "daily": []},
        }
        with patch("core.data_sources._twse_institutional", return_value=twse_result) as mock_inst:
            provider = MultiSourceDataProvider()
            result = provider.get_institutional("2330", days=5)

        assert result is not None
        assert result["source"] == "twse"
        mock_inst.assert_called_once_with("2330", 5)

    def test_fundamentals_falls_back_to_finmind(self):
        """基本面：退到 FinMind。"""
        from core.data_sources import MultiSourceDataProvider

        fm_result = {"pe_ratio": 15.0, "pb_ratio": 1.5, "dividend_yield": 2.0}
        with patch("core.data_sources._finmind_fundamentals", return_value=fm_result) as mock_fm:
            provider = MultiSourceDataProvider()
            result = provider.get_fundamentals("2330")

        assert result is not None
        assert result["source"] == "finmind"
        mock_fm.assert_called_once_with("2330")

    def test_margin_falls_back_to_twse(self):
        """融資融券：退到 TWSE。"""
        from core.data_sources import MultiSourceDataProvider

        margin_result = {"margin_buy": 100, "margin_sell": 50, "margin_ratio": 1.0, "date": "2024-01-01"}
        with patch("core.data_sources._twse_margin_fallback", return_value=margin_result) as mock_margin:
            provider = MultiSourceDataProvider()
            result = provider.get_margin("2330", days=5)

        assert result is not None
        assert result["source"] == "twse"
        mock_margin.assert_called_once_with("2330", 5)

    def test_realtime_quote_uses_twse(self):
        """即時報價：直接走 TWSE。"""
        from core.data_sources import MultiSourceDataProvider

        rt_result = {"stock_id": "2330", "name": "台積電", "price": 600.0, "yesterday_close": 590.0}
        with patch("core.data_sources._twse_realtime", return_value=rt_result):
            provider = MultiSourceDataProvider()
            result = provider.get_realtime_quote("2330")

        assert result is not None
        assert result["source"] == "twse"

    def test_institutional_all_fail_returns_none(self):
        from core.data_sources import MultiSourceDataProvider

        with patch("core.data_sources._twse_institutional", return_value=None):
            provider = MultiSourceDataProvider()
            result = provider.get_institutional("2330")
        assert result is None
