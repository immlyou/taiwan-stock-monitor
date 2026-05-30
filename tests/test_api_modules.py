"""
外部 API 模組測試（TWSE、即時報價）
涵蓋：twse_api、realtime_quote（皆使用 mock，不發出真實 HTTP 請求）
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────
# twse_api
# ──────────────────────────────────────────────
from core.twse_api import (
    _parse_twse_date, _parse_number,
    fetch_taiex_monthly, fetch_taiex_latest, fetch_taiex_realtime,
    get_taiex,
    _taiex_cache,
)


class TestParseTwseDate:
    def test_valid_date(self):
        result = _parse_twse_date("114/01/24")
        assert result == datetime(2025, 1, 24)

    def test_invalid_format_returns_none(self):
        result = _parse_twse_date("invalid")
        assert result is None

    def test_short_format_returns_none(self):
        result = _parse_twse_date("114/01")
        assert result is None


class TestParseNumber:
    def test_integer_string(self):
        assert _parse_number("1,234") == 1234.0

    def test_float_string(self):
        assert _parse_number("1234.56") == pytest.approx(1234.56)

    def test_numeric_input(self):
        assert _parse_number(100) == 100.0

    def test_dash_returns_none(self):
        # twse_api._parse_number 對無效輸入回傳 None
        assert _parse_number("-") is None

    def test_empty_returns_none(self):
        assert _parse_number("") is None

    def test_none_returns_float(self):
        # None 是 float 的子型別? 不是，但 isinstance(None, (int,float)) 是 False
        # 所以 None.replace() 會 AttributeError → 回傳 None
        assert _parse_number(None) is None


class TestFetchTaiexMonthly:
    @patch("requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "stat": "OK",
            "data": [
                ["114/01/02", "10000000", "500000000", "100000", "21000.00", "100.00"],
                ["114/01/03", "10000000", "500000000", "100000", "21100.00", "100.00"],
            ]
        }
        mock_get.return_value = mock_resp

        result = fetch_taiex_monthly(2025, 1)
        assert isinstance(result, pd.DataFrame)
        assert "close" in result.columns
        assert len(result) == 2

    @patch("requests.get")
    def test_stat_not_ok_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"stat": "NO DATA"}
        mock_get.return_value = mock_resp

        result = fetch_taiex_monthly(2025, 1)
        assert result is None

    @patch("requests.get")
    def test_exception_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("連線失敗")
        result = fetch_taiex_monthly(2025, 1)
        assert result is None

    @patch("requests.get")
    def test_default_year_month(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"stat": "NO DATA"}
        mock_get.return_value = mock_resp
        result = fetch_taiex_monthly()
        assert result is None


class TestFetchTaiexLatest:
    def setup_method(self):
        _taiex_cache.clear()

    @patch("core.twse_api.fetch_taiex_monthly")
    def test_returns_dict_when_data_available(self, mock_monthly):
        dates = pd.date_range("2025-01-01", periods=3)
        mock_monthly.return_value = pd.DataFrame(
            {"close": [20000.0, 20100.0, 20200.0],
             "change": [50.0, 100.0, 100.0]},
            index=dates
        )
        result = fetch_taiex_latest()
        assert isinstance(result, dict)
        assert "index" in result
        assert "change" in result
        assert "change_pct" in result

    @patch("core.twse_api.fetch_taiex_monthly")
    def test_uses_cache(self, mock_monthly):
        dates = pd.date_range("2025-01-01", periods=1)
        mock_monthly.return_value = pd.DataFrame(
            {"close": [20000.0], "change": [100.0]}, index=dates
        )
        # 第一次呼叫
        result1 = fetch_taiex_latest()
        # 第二次應使用快取，不再呼叫 mock_monthly
        mock_monthly.reset_mock()
        result2 = fetch_taiex_latest()
        mock_monthly.assert_not_called()

    @patch("core.twse_api.fetch_taiex_monthly")
    def test_returns_none_when_no_data(self, mock_monthly):
        mock_monthly.return_value = None
        result = fetch_taiex_latest()
        assert result is None


class TestFetchTaiexRealtime:
    def setup_method(self):
        _taiex_cache.clear()

    @patch("requests.get")
    def test_returns_dict_or_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"stat": "NO DATA"}
        mock_get.return_value = mock_resp
        result = fetch_taiex_realtime()
        assert result is None or isinstance(result, dict)

    @patch("requests.get")
    def test_exception_returns_none(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("連線失敗")
        result = fetch_taiex_realtime()
        assert result is None


class TestGetTaiex:
    def setup_method(self):
        _taiex_cache.clear()

    @patch("core.twse_api.fetch_taiex_realtime")
    def test_returns_tuple_with_data(self, mock_realtime):
        mock_realtime.return_value = {
            "index": 21000.0, "change": 100.0,
            "change_pct": 0.48, "date": "2025-01-24"
        }
        index, change_pct, date = get_taiex()
        assert index == 21000.0
        assert change_pct == pytest.approx(0.48)
        assert date == "2025-01-24"

    @patch("core.twse_api.fetch_taiex_realtime")
    def test_returns_none_tuple_when_no_data(self, mock_realtime):
        mock_realtime.return_value = None
        index, change_pct, date = get_taiex()
        assert index is None
        assert change_pct is None
        assert date is None

    @patch("core.twse_api.fetch_taiex_realtime")
    def test_returns_3_tuple(self, mock_realtime):
        mock_realtime.return_value = None
        result = get_taiex()
        assert isinstance(result, tuple)
        assert len(result) == 3


# ──────────────────────────────────────────────
# realtime_quote
# ──────────────────────────────────────────────
from core.realtime_quote import (
    StockQuote, _parse_number as rq_parse_number,
    _get_stock_code, fetch_realtime_quote, fetch_realtime_quotes,
    _quote_cache,
)


class TestStockQuote:
    def _make_quote(self, **kwargs):
        defaults = dict(
            stock_id="2330", name="台積電",
            price=600.0, open=595.0, high=605.0, low=592.0,
            yesterday_close=590.0, change=10.0, change_pct=1.69,
            volume=50000, volume_lots=50, amount=30_000_000.0,
            bid_price=599.0, ask_price=600.0,
            bid_volume=100, ask_volume=200,
            time="09:30:00", is_trading=True, market="上市"
        )
        defaults.update(kwargs)
        return StockQuote(**defaults)

    def test_is_up_positive_change(self):
        q = self._make_quote(change=10.0)
        assert q.is_up is True
        assert q.is_down is False

    def test_is_down_negative_change(self):
        q = self._make_quote(change=-5.0)
        assert q.is_down is True
        assert q.is_up is False

    def test_is_limit_up(self):
        q = self._make_quote(yesterday_close=600.0, price=660.1)
        assert q.is_limit_up is True

    def test_is_limit_down(self):
        q = self._make_quote(yesterday_close=600.0, price=539.9)
        assert q.is_limit_down is True

    def test_not_limit_when_yesterday_close_zero(self):
        q = self._make_quote(yesterday_close=0.0, price=100.0)
        assert q.is_limit_up is False
        assert q.is_limit_down is False

    def test_normal_price_not_limit(self):
        q = self._make_quote(yesterday_close=600.0, price=605.0)
        assert q.is_limit_up is False
        assert q.is_limit_down is False


class TestRealtimeParseHelpers:
    def test_parse_number_normal(self):
        assert rq_parse_number("1,234.56") == pytest.approx(1234.56)

    def test_parse_number_dash(self):
        assert rq_parse_number("-") == 0.0

    def test_parse_number_empty(self):
        assert rq_parse_number("") == 0.0

    def test_get_stock_code(self):
        code = _get_stock_code("2330")
        assert "2330" in code
        assert "tse" in code


class TestFetchRealtimeQuotes:
    def setup_method(self):
        _quote_cache.clear()

    @patch("requests.get")
    def test_returns_dict(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"msgArray": []}
        mock_get.return_value = mock_resp

        result = fetch_realtime_quotes(["2330"], use_cache=False)
        assert isinstance(result, dict)

    @patch("requests.get")
    def test_exception_returns_empty(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("失敗")

        result = fetch_realtime_quotes(["2330"], use_cache=False)
        assert isinstance(result, dict)

    def test_uses_cache(self):
        """快取命中時不發送請求"""
        from datetime import datetime
        mock_quote = MagicMock(spec=StockQuote)
        _quote_cache["2330"] = (datetime.now(), mock_quote)

        with patch("requests.get") as mock_get:
            result = fetch_realtime_quotes(["2330"], use_cache=True)
            mock_get.assert_not_called()
            assert "2330" in result

    @patch("requests.get")
    def test_parse_valid_response(self, mock_get):
        """解析 TWSE API 回應格式"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "msgArray": [{
                "c": "2330",     # 股票代號
                "n": "台積電",    # 名稱
                "z": "600",      # 成交價
                "o": "595",      # 開盤
                "h": "605",      # 最高
                "l": "592",      # 最低
                "y": "590",      # 昨收
                "tv": "50000",   # 成交量
                "v": "50000",
                "b": "599",
                "g": "600",
                "fv": "100",
                "gv": "200",
                "t": "09:30:00",
            }]
        }
        mock_get.return_value = mock_resp

        result = fetch_realtime_quotes(["2330"], use_cache=False)
        assert isinstance(result, dict)

    @patch("requests.get")
    def test_single_quote_helper(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"msgArray": []}
        mock_get.return_value = mock_resp

        result = fetch_realtime_quote("2330", use_cache=False)
        assert result is None or isinstance(result, StockQuote)
