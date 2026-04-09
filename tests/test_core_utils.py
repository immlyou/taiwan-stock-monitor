"""
核心工具模組測試
涵蓋：exceptions、validators、utils、logging_config、http_client
"""
import logging
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from pathlib import Path


# ──────────────────────────────────────────────
# exceptions
# ──────────────────────────────────────────────
from core.exceptions import (
    FinlabBaseException,
    DataException, DataNotFoundError, DataLoadError, DataFormatError,
    ValidationException, ParameterValidationError, ParameterRangeError,
    ParameterTypeError, ParameterConflictError,
    StrategyException, StrategyExecutionError, InsufficientDataError,
    BacktestException, BacktestConfigError, InsufficientCapitalError,
    NotificationException, NotificationSendError, NotificationConfigError,
)


class TestDataExceptions:
    def test_data_not_found_message(self):
        e = DataNotFoundError("close")
        assert "close" in str(e)
        assert e.data_key == "close"

    def test_data_not_found_with_filepath(self):
        e = DataNotFoundError("close", "/tmp/close.pickle")
        assert "/tmp/close.pickle" in str(e)
        assert e.filepath == "/tmp/close.pickle"

    def test_data_load_error(self):
        e = DataLoadError("volume", "磁碟損毀")
        assert "volume" in str(e)
        assert "磁碟損毀" in str(e)

    def test_data_load_error_no_reason(self):
        e = DataLoadError("pe_ratio")
        assert "pe_ratio" in str(e)
        assert e.reason is None

    def test_data_format_error(self):
        e = DataFormatError("close", "DataFrame", "Series")
        assert "close" in str(e)
        assert "DataFrame" in str(e)
        assert "Series" in str(e)

    def test_data_exception_hierarchy(self):
        e = DataNotFoundError("x")
        assert isinstance(e, DataException)
        assert isinstance(e, FinlabBaseException)
        assert isinstance(e, Exception)


class TestValidationExceptions:
    def test_parameter_validation_error(self):
        e = ParameterValidationError("pe_max", -1, "不可為負數")
        assert "pe_max" in str(e)
        assert e.param_name == "pe_max"
        assert e.value == -1

    def test_parameter_validation_error_no_message(self):
        e = ParameterValidationError("pe_max", -1)
        assert e.message is None

    def test_parameter_range_error_both_bounds(self):
        e = ParameterRangeError("pe_max", 200, 1.0, 100.0)
        assert "200" in str(e)
        assert "100.0" in str(e)
        assert e.min_val == 1.0
        assert e.max_val == 100.0

    def test_parameter_range_error_min_only(self):
        e = ParameterRangeError("capital", -1, min_val=0)
        assert "0" in str(e)
        assert e.max_val is None

    def test_parameter_range_error_max_only(self):
        e = ParameterRangeError("discount", 2.0, max_val=1.0)
        assert "1.0" in str(e)
        assert e.min_val is None

    def test_parameter_range_error_no_bounds(self):
        e = ParameterRangeError("x", 999)
        assert "x" in str(e)

    def test_parameter_type_error(self):
        e = ParameterTypeError("pe_max", "float", "str")
        assert "pe_max" in str(e)
        assert "float" in str(e)
        assert "str" in str(e)

    def test_parameter_conflict_error(self):
        e = ParameterConflictError({"rsi_min": 80, "rsi_max": 50}, "下限大於上限")
        assert "下限大於上限" in str(e)

    def test_validation_hierarchy(self):
        e = ParameterValidationError("x", 1)
        assert isinstance(e, ValidationException)
        assert isinstance(e, FinlabBaseException)


class TestStrategyExceptions:
    def test_strategy_execution_error(self):
        e = StrategyExecutionError("ValueStrategy", "資料不足")
        assert "ValueStrategy" in str(e)
        assert "資料不足" in str(e)

    def test_strategy_execution_error_no_reason(self):
        e = StrategyExecutionError("GrowthStrategy")
        assert e.reason is None

    def test_insufficient_data_error(self):
        e = InsufficientDataError("CompositeStrategy", ["close", "pe_ratio"], ["pe_ratio"])
        assert "pe_ratio" in str(e)
        assert e.missing_data == ["pe_ratio"]

    def test_strategy_hierarchy(self):
        e = StrategyExecutionError("x")
        assert isinstance(e, StrategyException)
        assert isinstance(e, FinlabBaseException)


class TestBacktestExceptions:
    def test_backtest_config_error(self):
        e = BacktestConfigError("初始資金不可為零")
        assert "初始資金不可為零" in str(e)

    def test_insufficient_capital_error(self):
        e = InsufficientCapitalError(100_000, 50_000)
        assert "100,000" in str(e)
        assert "50,000" in str(e)
        assert e.required == 100_000
        assert e.available == 50_000

    def test_backtest_hierarchy(self):
        e = BacktestConfigError("x")
        assert isinstance(e, BacktestException)
        assert isinstance(e, FinlabBaseException)


class TestNotificationExceptions:
    def test_notification_send_error(self):
        e = NotificationSendError("LINE", "Token 失效")
        assert "LINE" in str(e)
        assert "Token 失效" in str(e)
        assert e.channel == "LINE"

    def test_notification_send_error_no_reason(self):
        e = NotificationSendError("Telegram")
        assert e.reason is None

    def test_notification_config_error(self):
        e = NotificationConfigError("Email", "SMTP 未設定")
        assert "Email" in str(e)
        assert "SMTP" in str(e)

    def test_notification_hierarchy(self):
        e = NotificationSendError("x")
        assert isinstance(e, NotificationException)
        assert isinstance(e, FinlabBaseException)


# ──────────────────────────────────────────────
# validators
# ──────────────────────────────────────────────
from core.validators import (
    ParameterValidator, StrategyParamsValidator,
    validate_date_range, validate_stock_list,
)


class TestParameterValidator:
    def test_validate_type_ok(self):
        ParameterValidator.validate_type(3.14, float, "pe_max")  # 不應拋出

    def test_validate_type_fail(self):
        with pytest.raises(ParameterTypeError):
            ParameterValidator.validate_type("abc", float, "pe_max")

    def test_validate_range_ok(self):
        ParameterValidator.validate_range(50.0, "rsi", 0, 100)  # 不應拋出

    def test_validate_range_below_min(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_range(-1, "rsi", 0, 100)

    def test_validate_range_above_max(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_range(101, "rsi", 0, 100)

    def test_validate_range_no_bounds(self):
        ParameterValidator.validate_range(999, "x")  # 無界限，不應拋出

    def test_validate_positive_ok(self):
        ParameterValidator.validate_positive(0.001, "rate")

    def test_validate_positive_fail(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_positive(0, "rate")

    def test_validate_positive_negative_fail(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_positive(-1, "rate")

    def test_validate_non_negative_ok(self):
        ParameterValidator.validate_non_negative(0, "capital")

    def test_validate_non_negative_fail(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_non_negative(-0.01, "capital")

    def test_validate_percentage_ok(self):
        ParameterValidator.validate_percentage(75.0, "weight")

    def test_validate_percentage_below_zero(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_percentage(-1, "weight")

    def test_validate_percentage_above_100(self):
        with pytest.raises(ParameterRangeError):
            ParameterValidator.validate_percentage(101, "weight")

    def test_validate_not_empty_ok(self):
        ParameterValidator.validate_not_empty([1, 2], "stocks")

    def test_validate_not_empty_none(self):
        with pytest.raises(ParameterValidationError):
            ParameterValidator.validate_not_empty(None, "stocks")

    def test_validate_not_empty_list(self):
        with pytest.raises(ParameterValidationError):
            ParameterValidator.validate_not_empty([], "stocks")

    def test_validate_in_list_ok(self):
        ParameterValidator.validate_in_list("equal", ["equal", "market_cap"], "method")

    def test_validate_in_list_fail(self):
        with pytest.raises(ParameterValidationError):
            ParameterValidator.validate_in_list("random", ["equal", "market_cap"], "method")


class TestStrategyParamsValidator:
    def test_validate_value_params_defaults(self):
        result = StrategyParamsValidator.validate_value_params({})
        assert "pe_max" in result
        assert result["pe_max"] == 15.0

    def test_validate_value_params_custom(self):
        result = StrategyParamsValidator.validate_value_params({"pe_max": 20.0})
        assert result["pe_max"] == 20.0

    def test_validate_value_params_out_of_range(self):
        with pytest.raises(ParameterRangeError):
            StrategyParamsValidator.validate_value_params({"pe_max": 999.0})

    def test_validate_growth_params_defaults(self):
        result = StrategyParamsValidator.validate_growth_params({})
        assert "revenue_yoy_min" in result

    def test_validate_momentum_params_rsi_conflict(self):
        with pytest.raises(ParameterConflictError):
            StrategyParamsValidator.validate_momentum_params({"rsi_min": 80, "rsi_max": 50})

    def test_validate_momentum_params_ok(self):
        result = StrategyParamsValidator.validate_momentum_params({"rsi_min": 50, "rsi_max": 80})
        assert result["rsi_min"] == 50

    def test_validate_backtest_params_defaults(self):
        result = StrategyParamsValidator.validate_backtest_params({})
        assert "initial_capital" in result
        assert result["initial_capital"] == 1_000_000

    def test_validate_type_conversion(self):
        """整數應被轉換成浮點數"""
        result = StrategyParamsValidator.validate_value_params({"pe_max": 20})
        assert isinstance(result["pe_max"], float)


class TestValidateDateRange:
    def test_valid_range(self):
        validate_date_range("2021-01-01", "2023-12-31")  # 不應拋出

    def test_reversed_range_raises(self):
        with pytest.raises(ParameterConflictError):
            validate_date_range("2023-12-31", "2021-01-01")

    def test_none_dates_ok(self):
        validate_date_range(None, None)  # 不應拋出

    def test_timestamp_inputs(self):
        validate_date_range(pd.Timestamp("2021-01-01"), pd.Timestamp("2023-12-31"))


class TestValidateStockList:
    def test_valid_list(self):
        validate_stock_list(["2330", "2317"])  # 不應拋出

    def test_empty_list_raises(self):
        with pytest.raises(ParameterValidationError):
            validate_stock_list([])

    def test_invalid_stock_raises(self):
        with pytest.raises(ParameterValidationError):
            validate_stock_list([""])


# ──────────────────────────────────────────────
# utils
# ──────────────────────────────────────────────
from core.utils import (
    extract_stock_id, normalize_columns, align_dataframes,
    get_common_stocks, find_nearest_date, filter_trading_stocks,
)


class TestExtractStockId:
    def test_with_name(self):
        assert extract_stock_id("2330 台積電") == "2330"

    def test_without_name(self):
        assert extract_stock_id("2330") == "2330"

    def test_etf(self):
        assert extract_stock_id("0050 元大台灣50") == "0050"


class TestNormalizeColumns:
    def test_renames_columns(self):
        df = pd.DataFrame({"2330 台積電": [1], "2317 鴻海": [2]})
        result = normalize_columns(df)
        assert "2330" in result.columns
        assert "2317" in result.columns

    def test_no_change_when_already_clean(self):
        df = pd.DataFrame({"2330": [1], "2317": [2]})
        result = normalize_columns(df)
        assert list(result.columns) == ["2330", "2317"]


class TestAlignDataframes:
    def test_normalizes_all_dfs(self):
        dfs = {
            "close": pd.DataFrame({"2330 台積電": [100]}),
            "volume": pd.DataFrame({"2330 台積電": [1000]}),
        }
        result = align_dataframes(dfs)
        assert "2330" in result["close"].columns
        assert "2330" in result["volume"].columns

    def test_skips_non_dataframe(self):
        dfs = {"close": pd.DataFrame({"2330": [1]}), "scalar": 42}
        result = align_dataframes(dfs)
        assert result["scalar"] == 42

    def test_no_normalize(self):
        dfs = {"close": pd.DataFrame({"2330 台積電": [1]})}
        result = align_dataframes(dfs, normalize=False)
        assert "2330 台積電" in result["close"].columns


class TestGetCommonStocks:
    def test_common_stocks(self):
        dfs = {
            "a": pd.DataFrame({"2330": [1], "2317": [2]}),
            "b": pd.DataFrame({"2330": [3], "2454": [4]}),
        }
        result = get_common_stocks(dfs)
        assert "2330" in result
        assert "2317" not in result
        assert "2454" not in result

    def test_empty_dfs(self):
        result = get_common_stocks({})
        assert result == []

    def test_single_df(self):
        dfs = {"a": pd.DataFrame({"2330": [1]})}
        result = get_common_stocks(dfs)
        assert "2330" in result


class TestFindNearestDate:
    def test_exact_date(self):
        dates = pd.date_range("2023-01-01", periods=10)
        df = pd.DataFrame({"A": range(10)}, index=dates)
        result = find_nearest_date(df, dates[5])
        assert result == dates[5]

    def test_before_date(self):
        dates = pd.date_range("2023-01-01", periods=5, freq="W")
        df = pd.DataFrame({"A": range(5)}, index=dates)
        target = dates[2] + pd.Timedelta(days=1)
        result = find_nearest_date(df, target)
        assert result == dates[2]

    def test_before_all_dates(self):
        dates = pd.date_range("2023-06-01", periods=5)
        df = pd.DataFrame({"A": range(5)}, index=dates)
        target = pd.Timestamp("2023-01-01")
        result = find_nearest_date(df, target)
        assert result == dates[0]


class TestFilterTradingStocks:
    def test_filters_low_price(self):
        dates = pd.date_range("2023-01-01", periods=5)
        close = pd.DataFrame({
            "A": [100.0] * 5,
            "B": [3.0] * 5,   # 低於最低股價
        }, index=dates)
        result = filter_trading_stocks(close, dates[-1], min_price=5.0)
        assert "A" in result
        assert "B" not in result

    def test_filters_nan_price(self):
        dates = pd.date_range("2023-01-01", periods=5)
        close = pd.DataFrame({
            "A": [100.0] * 5,
            "B": [np.nan] * 5,
        }, index=dates)
        result = filter_trading_stocks(close, dates[-1])
        assert "A" in result
        assert "B" not in result

    def test_filters_with_volume(self):
        dates = pd.date_range("2023-01-01", periods=5)
        close = pd.DataFrame({"A": [100.0] * 5, "B": [50.0] * 5}, index=dates)
        volume = pd.DataFrame({"A": [1000.0] * 5, "B": [50.0] * 5}, index=dates)
        result = filter_trading_stocks(close, dates[-1], min_volume=volume, min_volume_value=500)
        assert "A" in result
        assert "B" not in result


# ──────────────────────────────────────────────
# logging_config
# ──────────────────────────────────────────────
from core.logging_config import (
    setup_logging, get_logger, LogContext,
    init_default_logger, log_strategy_execution,
    log_backtest_result, log_data_update,
)


class TestSetupLogging:
    def test_returns_logger(self):
        logger = setup_logging(name="test_setup_unique_1")
        assert isinstance(logger, logging.Logger)

    def test_no_duplicate_handlers(self):
        logger = setup_logging(name="test_no_dup")
        count1 = len(logger.handlers)
        setup_logging(name="test_no_dup")  # 第二次呼叫
        assert len(logger.handlers) == count1

    def test_detailed_format(self):
        logger = setup_logging(format_style="detailed", name="test_detailed")
        assert isinstance(logger, logging.Logger)

    def test_simple_format(self):
        logger = setup_logging(format_style="simple", name="test_simple")
        assert isinstance(logger, logging.Logger)

    def test_default_name(self):
        logger = setup_logging()
        assert logger.name == "finlab"

    def test_with_log_file(self, tmp_path):
        logger = setup_logging(
            log_file="test_log.log",
            log_dir=tmp_path,
            name="test_file_logger"
        )
        assert (tmp_path / "test_log.log").exists()


class TestGetLogger:
    def test_with_name(self):
        logger = get_logger("my_module")
        assert "finlab.my_module" == logger.name

    def test_without_name(self):
        logger = get_logger()
        assert logger.name == "finlab"


class TestLogContext:
    def test_context_manager_success(self):
        logger = logging.getLogger("test_ctx")
        with LogContext(logger, "測試操作"):
            pass  # 正常完成

    def test_context_manager_reraises_exception(self):
        logger = logging.getLogger("test_ctx_err")
        with pytest.raises(ValueError):
            with LogContext(logger, "失敗操作"):
                raise ValueError("測試錯誤")


class TestInitDefaultLogger:
    def test_returns_logger(self):
        logger = init_default_logger()
        assert isinstance(logger, logging.Logger)

    def test_singleton_behavior(self):
        l1 = init_default_logger()
        l2 = init_default_logger()
        assert l1 is l2


class TestLogHelpers:
    def test_log_strategy_execution(self):
        log_strategy_execution("ValueStrategy", {"pe_max": 15}, 10)

    def test_log_backtest_result(self):
        log_backtest_result("ValueStrategy", {
            "total_return": 25.0,
            "annualized_return": 12.5,
            "sharpe_ratio": 1.2
        })

    def test_log_data_update_success(self):
        log_data_update("close", success=True)

    def test_log_data_update_failure(self):
        log_data_update("volume", success=False, error="磁碟空間不足")


# ──────────────────────────────────────────────
# http_client
# ──────────────────────────────────────────────
from core.http_client import RetryConfig, HttpClient, get_http_client, http_get, http_post


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.initial_delay == 1.0
        assert cfg.max_delay == 30.0
        assert 429 in cfg.retry_on_status

    def test_custom(self):
        cfg = RetryConfig(max_retries=5, initial_delay=0.5)
        assert cfg.max_retries == 5
        assert cfg.initial_delay == 0.5


class TestHttpClient:
    def test_init_defaults(self):
        client = HttpClient()
        assert client.timeout == 30
        assert isinstance(client.retry_config, RetryConfig)

    def test_context_manager(self):
        with HttpClient() as client:
            assert client is not None

    def test_prepare_headers_merges(self):
        client = HttpClient(default_headers={"X-Base": "1"})
        headers = client._prepare_headers({"X-Extra": "2"})
        assert headers["X-Base"] == "1"
        assert headers["X-Extra"] == "2"

    def test_prepare_headers_no_extra(self):
        client = HttpClient(default_headers={"X-Base": "1"})
        headers = client._prepare_headers()
        assert headers["X-Base"] == "1"

    @patch("requests.Session.request")
    def test_get_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_request.return_value = mock_resp

        client = HttpClient(retry_config=RetryConfig(max_retries=0))
        resp = client.get("http://example.com")
        assert resp.status_code == 200

    @patch("requests.Session.request")
    def test_post_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_request.return_value = mock_resp

        client = HttpClient(retry_config=RetryConfig(max_retries=0))
        resp = client.post("http://example.com", json={"key": "val"})
        assert resp.status_code == 200

    @patch("requests.Session.request")
    @patch("time.sleep")
    def test_retries_on_500(self, mock_sleep, mock_request):
        """500 錯誤應觸發重試（預設 3 次）"""
        import requests as req_lib
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_request.return_value = mock_resp

        client = HttpClient()
        with pytest.raises(req_lib.HTTPError):
            client.get("http://example.com")

        # 預設 RetryConfig 重試 3 次 → 共 4 次呼叫
        assert mock_request.call_count == 4

    @patch("requests.Session.request")
    def test_no_retry_on_200(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_request.return_value = mock_resp

        client = HttpClient(retry_config=RetryConfig(max_retries=3, initial_delay=0))
        client.get("http://example.com")
        assert mock_request.call_count == 1

    @patch("requests.Session.request")
    def test_raises_on_connection_error(self, mock_request):
        import requests as req_lib
        mock_request.side_effect = req_lib.ConnectionError("連線失敗")

        client = HttpClient(retry_config=RetryConfig(max_retries=1, initial_delay=0))
        with pytest.raises(req_lib.ConnectionError):
            client.get("http://example.com")


class TestHttpHelpers:
    def test_get_http_client_singleton(self):
        c1 = get_http_client()
        c2 = get_http_client()
        assert c1 is c2
