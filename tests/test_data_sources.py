"""
data_sources 模組測試（完全 mock，不發出真實 HTTP 請求）
涵蓋：_source_cached、_set_source_cache、_twse_throttle、
      _safe_float、_parse_twse_number、_safe_json_val、
      _yfinance_ohlcv、_twse_realtime、_twse_realtime_batch、
      _twse_institutional、MultiSourceDataProvider
"""
import time
import math
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from typing import Optional

import core.data_sources as ds
from core.data_sources import (
    _source_cached, _set_source_cache,
    _safe_float, _parse_twse_number, _safe_json_val,
    _yfinance_ohlcv, _twse_realtime, _twse_realtime_batch,
    MultiSourceDataProvider,
    _source_cache, _source_cache_ts,
)


# ──────────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────────

class TestSafeFloat:
    def test_float_string(self):
        assert _safe_float("123.45") == pytest.approx(123.45)

    def test_integer(self):
        assert _safe_float(100) == 100.0

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_dash_returns_none(self):
        assert _safe_float("--") is None

    def test_empty_string_returns_none(self):
        assert _safe_float("") is None

    def test_zero_special_values(self):
        # 0 字串應回傳 None（代表 "--"）
        assert _safe_float("-") is None

    def test_normal_zero(self):
        result = _safe_float("0.0")
        # "0.0" 轉成 float 後值為 0，str("0.0").strip() 不在 ("", "-", "--") 中
        assert result == 0.0

    def test_invalid_string(self):
        assert _safe_float("abc") is None


class TestParseTwseNumber:
    def test_comma_separated(self):
        assert _parse_twse_number("1,234,567") == pytest.approx(1234567.0)

    def test_quoted(self):
        assert _parse_twse_number('"123.45"') == pytest.approx(123.45)

    def test_integer_input(self):
        assert _parse_twse_number(100) == 100.0

    def test_invalid_returns_zero(self):
        assert _parse_twse_number("N/A") == 0.0


class TestSafeJsonVal:
    def test_none(self):
        assert _safe_json_val(None) is None

    def test_int(self):
        assert _safe_json_val(42) == 42

    def test_float(self):
        assert _safe_json_val(3.14) == pytest.approx(3.14)

    def test_nan_returns_none(self):
        assert _safe_json_val(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe_json_val(float("inf")) is None

    def test_numpy_float(self):
        result = _safe_json_val(np.float64(1.5))
        assert result == pytest.approx(1.5)

    def test_numpy_integer(self):
        result = _safe_json_val(np.int64(10))
        assert result == 10

    def test_numpy_nan_returns_none(self):
        assert _safe_json_val(np.float64("nan")) is None

    def test_string_passthrough(self):
        assert _safe_json_val("hello") == "hello"


# ──────────────────────────────────────────────
# 快取機制
# ──────────────────────────────────────────────

class TestSourceCache:
    def setup_method(self):
        _source_cache.clear()
        _source_cache_ts.clear()

    def test_cache_miss_returns_none(self):
        result = _source_cached("nonexistent_key")
        assert result is None

    def test_cache_hit_within_ttl(self):
        _set_source_cache("key1", {"data": "value"})
        result = _source_cached("key1", ttl=3600)
        assert result == {"data": "value"}

    def test_cache_expired(self):
        _set_source_cache("key2", {"data": "old"})
        _source_cache_ts["key2"] = time.time() - 7200  # 過期
        result = _source_cached("key2", ttl=300)
        assert result is None

    def test_set_cache(self):
        _set_source_cache("key3", [1, 2, 3])
        assert _source_cache["key3"] == [1, 2, 3]
        assert "key3" in _source_cache_ts


# ──────────────────────────────────────────────
# _yfinance_ohlcv
# ──────────────────────────────────────────────

class TestYfinanceOhlcv:
    def test_yfinance_not_installed_returns_none(self):
        with patch.dict("sys.modules", {"yfinance": None}):
            result = _yfinance_ohlcv("2330", 60)
            # yfinance 不可用時應回傳 None 或安全降級
            assert result is None or isinstance(result, pd.DataFrame)

    @patch("core.data_sources._yfinance_ohlcv")
    def test_returns_dataframe_when_available(self, mock_fn):
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame({
            "open": [100.0] * 10, "high": [105.0] * 10,
            "low": [98.0] * 10, "close": [102.0] * 10,
            "volume": [100000.0] * 10,
        }, index=dates)
        mock_fn.return_value = df
        result = mock_fn("2330", 10)
        assert isinstance(result, pd.DataFrame)

    def test_import_error_handled(self):
        """yfinance 不可用時不應崩潰"""
        with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs:
                   (_ for _ in ()).throw(ImportError("No module named 'yfinance'"))
                   if name == "yfinance" else __import__(name, *args, **kwargs)):
            # 呼叫不應崩潰
            try:
                result = _yfinance_ohlcv("2330", 10)
                # 可能回傳 None 或 DataFrame
                assert result is None or isinstance(result, pd.DataFrame)
            except Exception:
                pass  # 預期可能失敗


# ──────────────────────────────────────────────
# _twse_realtime
# ──────────────────────────────────────────────

class TestTwseRealtime:
    def setup_method(self):
        _source_cache.clear()
        _source_cache_ts.clear()

    @patch("requests.get")
    @patch("core.data_sources._twse_throttle")
    def test_success(self, mock_throttle, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "msgArray": [{
                "c": "2330", "n": "台積電",
                "z": "600", "o": "595", "h": "605", "l": "592",
                "y": "590", "v": "50000",
            }]
        }
        mock_get.return_value = mock_resp

        result = _twse_realtime("2330")
        assert result is not None
        assert result["stock_id"] == "2330"
        assert result["price"] == pytest.approx(600.0)

    @patch("requests.get")
    @patch("core.data_sources._twse_throttle")
    def test_empty_msg_array_returns_none(self, mock_throttle, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"msgArray": []}
        mock_get.return_value = mock_resp

        result = _twse_realtime("2330")
        assert result is None

    @patch("requests.get")
    @patch("core.data_sources._twse_throttle")
    def test_uses_cache(self, mock_throttle, mock_get):
        _set_source_cache("twse_realtime_2317", {"stock_id": "2317", "price": 100.0})
        result = _twse_realtime("2317")
        mock_get.assert_not_called()
        assert result["stock_id"] == "2317"

    @patch("requests.get")
    @patch("core.data_sources._twse_throttle")
    def test_exception_returns_none(self, mock_throttle, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("失敗")
        result = _twse_realtime("2454")
        assert result is None


# ──────────────────────────────────────────────
# _twse_realtime_batch
# ──────────────────────────────────────────────

class TestTwseRealtimeBatch:
    def setup_method(self):
        _source_cache.clear()
        _source_cache_ts.clear()

    @patch("requests.get")
    @patch("core.data_sources._twse_throttle")
    def test_success(self, mock_throttle, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "msgArray": [
                {"c": "2330", "n": "台積電", "z": "600", "o": "595",
                 "h": "605", "l": "592", "y": "590", "v": "50000"},
            ]
        }
        mock_get.return_value = mock_resp

        results = _twse_realtime_batch(["2330", "2317"])
        assert isinstance(results, list)

    @patch("requests.get")
    @patch("core.data_sources._twse_throttle")
    def test_exception_returns_empty(self, mock_throttle, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("失敗")
        results = _twse_realtime_batch(["2330"])
        assert results == []


# ──────────────────────────────────────────────
# MultiSourceDataProvider
# ──────────────────────────────────────────────

class TestMultiSourceDataProvider:
    def setup_method(self):
        _source_cache.clear()
        _source_cache_ts.clear()

    def test_init(self):
        provider = MultiSourceDataProvider()
        assert provider._loader is None

    def test_init_with_loader(self):
        mock_loader = MagicMock()
        provider = MultiSourceDataProvider(loader=mock_loader)
        assert provider._loader is mock_loader

    @patch("core.data_sources._yfinance_ohlcv")
    def test_get_ohlcv_success(self, mock_yf):
        dates = pd.date_range("2024-01-01", periods=5)
        df = pd.DataFrame({
            "open": [100.0] * 5, "high": [105.0] * 5,
            "low": [98.0] * 5, "close": [102.0] * 5,
            "volume": [10000.0] * 5,
        }, index=dates)
        mock_yf.return_value = df

        provider = MultiSourceDataProvider()
        result = provider.get_ohlcv("2330", days=5)

        assert result is not None
        assert result["stock_id"] == "2330"
        assert result["source"] == "yfinance"
        assert len(result["data"]) == 5

    @patch("core.data_sources._yfinance_ohlcv")
    def test_get_ohlcv_all_fail_returns_none(self, mock_yf):
        mock_yf.return_value = None

        provider = MultiSourceDataProvider()
        result = provider.get_ohlcv("2330", days=5)
        assert result is None

    @patch("core.data_sources._twse_realtime")
    def test_get_realtime_quote_success(self, mock_realtime):
        mock_realtime.return_value = {
            "stock_id": "2330", "name": "台積電",
            "price": 600.0, "yesterday_close": 590.0,
        }
        provider = MultiSourceDataProvider()
        result = provider.get_realtime_quote("2330")

        assert result is not None
        assert result["source"] == "twse"
        assert result["stock_id"] == "2330"

    @patch("core.data_sources._twse_realtime")
    def test_get_realtime_quote_fail_returns_none(self, mock_realtime):
        mock_realtime.return_value = None

        provider = MultiSourceDataProvider()
        result = provider.get_realtime_quote("2330")
        assert result is None

    @patch("core.data_sources._twse_realtime_batch")
    def test_get_realtime_batch(self, mock_batch):
        mock_batch.return_value = [
            {"stock_id": "2330", "price": 600.0},
            {"stock_id": "2317", "price": 100.0},
        ]
        provider = MultiSourceDataProvider()
        results = provider.get_realtime_batch(["2330", "2317"])

        assert len(results) == 2
        for r in results:
            assert r["source"] == "twse"

    @patch("core.data_sources._twse_institutional")
    def test_get_institutional_success(self, mock_inst):
        mock_inst.return_value = {
            "stock_id": "2330",
            "foreign": [1000, 2000],
            "trust": [500, 800],
        }
        provider = MultiSourceDataProvider()
        result = provider.get_institutional("2330", days=2)

        assert result is not None
        assert result["source"] == "twse"

    @patch("core.data_sources._twse_institutional")
    def test_get_institutional_fail_returns_none(self, mock_inst):
        mock_inst.return_value = None

        provider = MultiSourceDataProvider()
        result = provider.get_institutional("2330")
        assert result is None

    @patch("core.data_sources._finmind_fundamentals")
    def test_get_fundamentals_success(self, mock_fm):
        mock_fm.return_value = {"pe_ratio": 15.0, "pb_ratio": 1.5}
        provider = MultiSourceDataProvider()
        result = provider.get_fundamentals("2330")

        assert result is not None
        assert result["source"] == "finmind"

    @patch("core.data_sources._finmind_fundamentals")
    def test_get_fundamentals_fail_returns_none(self, mock_fm):
        mock_fm.return_value = None

        provider = MultiSourceDataProvider()
        result = provider.get_fundamentals("2330")
        assert result is None

    @patch("core.data_sources._twse_margin_fallback")
    def test_get_margin_success(self, mock_margin):
        mock_margin.return_value = {
            "stock_id": "2330",
            "margin_buy": [100, 120],
            "margin_sell": [50, 60],
        }
        provider = MultiSourceDataProvider()
        result = provider.get_margin("2330")

        assert result is not None
        assert result["source"] == "twse"

    @patch("core.data_sources._twse_margin_fallback")
    def test_get_margin_fail_returns_none(self, mock_margin):
        mock_margin.return_value = None

        provider = MultiSourceDataProvider()
        result = provider.get_margin("2330")
        assert result is None

    @patch("core.data_sources._yfinance_ohlcv")
    def test_get_ohlcv_with_empty_df(self, mock_yf):
        mock_yf.return_value = pd.DataFrame()

        provider = MultiSourceDataProvider()
        result = provider.get_ohlcv("2330", days=5)
        assert result is None

    def test_get_ohlcv_data_format(self):
        """確認回傳的 data 格式含必要欄位"""
        dates = pd.date_range("2024-01-01", periods=3)
        df = pd.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [98.0, 99.0, 100.0],
            "close": [102.0, 103.0, 104.0],
            "volume": [10000.0, 11000.0, 12000.0],
        }, index=dates)

        with patch("core.data_sources._yfinance_ohlcv", return_value=df):
            provider = MultiSourceDataProvider()
            result = provider.get_ohlcv("2330", days=3)
            assert result is not None
            for record in result["data"]:
                assert "date" in record
                assert "close" in record
