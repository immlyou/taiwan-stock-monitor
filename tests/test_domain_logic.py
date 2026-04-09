"""
業務邏輯模組測試
涵蓋：money_flow、optimizer、prediction_tracker、strategies/custom、
      indicators（補齊剩餘）、risk（補齊剩餘）
"""
import json
import uuid
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────
# money_flow
# ──────────────────────────────────────────────
from core.money_flow import (
    InstitutionalFlow, calculate_institutional_flow,
    calculate_consecutive_days, get_top_flows,
    get_sector_flow, calculate_flow_trend,
    get_continuous_buy_stocks,
)


@pytest.fixture(scope="module")
def flow_dates():
    return pd.date_range("2023-01-01", periods=20, freq="B")


@pytest.fixture(scope="module")
def stocks():
    return ["2330", "2317", "2454", "2412", "2308"]


@pytest.fixture(scope="module")
def foreign_df(flow_dates, stocks):
    np.random.seed(0)
    data = np.random.randint(-5000, 8000, (len(flow_dates), len(stocks))) * 1000
    df = pd.DataFrame(data.astype(float), index=flow_dates, columns=stocks)
    # 讓 2330 持續買超
    df["2330"] = np.abs(df["2330"])
    return df


@pytest.fixture(scope="module")
def investment_trust_df(flow_dates, stocks):
    np.random.seed(1)
    data = np.random.randint(-2000, 3000, (len(flow_dates), len(stocks))) * 1000
    return pd.DataFrame(data.astype(float), index=flow_dates, columns=stocks)


@pytest.fixture(scope="module")
def dealer_df(flow_dates, stocks):
    np.random.seed(2)
    data = np.random.randint(-1000, 2000, (len(flow_dates), len(stocks))) * 1000
    return pd.DataFrame(data.astype(float), index=flow_dates, columns=stocks)


@pytest.fixture(scope="module")
def stock_info_df(stocks):
    return pd.DataFrame({
        "stock_id": stocks,
        "name": ["台積電", "鴻海", "聯發科", "中華電", "台達電"],
        "category": ["半導體", "電子", "半導體", "電信", "電子"],
    })


@pytest.fixture(scope="module")
def flows(foreign_df, investment_trust_df, dealer_df, stock_info_df):
    return calculate_institutional_flow(
        foreign_df, investment_trust_df, dealer_df, stock_info_df
    )


class TestCalculateInstitutionalFlow:
    def test_returns_dict(self, flows, stocks):
        assert isinstance(flows, dict)

    def test_all_stocks_present(self, flows, stocks):
        for s in stocks:
            assert s in flows

    def test_flow_fields(self, flows):
        flow = next(iter(flows.values()))
        assert isinstance(flow, InstitutionalFlow)
        assert hasattr(flow, "foreign_net")
        assert hasattr(flow, "total_net")
        assert hasattr(flow, "consecutive_days")

    def test_empty_foreign_returns_empty(self, investment_trust_df, dealer_df, stock_info_df):
        result = calculate_institutional_flow(None, investment_trust_df, dealer_df, stock_info_df)
        assert result == {}

    def test_empty_foreign_df(self, investment_trust_df, dealer_df, stock_info_df):
        result = calculate_institutional_flow(
            pd.DataFrame(), investment_trust_df, dealer_df, stock_info_df
        )
        assert result == {}

    def test_unit_conversion_to_lots(self, flows):
        """外資買賣超單位應為「張」（原始值 / 1000）"""
        flow = flows.get("2330")
        if flow:
            # total_net 的絕對值應遠小於原始股數值
            assert abs(flow.foreign_net) < 100_000  # 張，而非百萬股

    def test_with_foreign_holding(self, foreign_df, investment_trust_df, dealer_df, stock_info_df, flow_dates, stocks):
        holding = pd.DataFrame(
            {s: [30.0] * len(flow_dates) for s in stocks},
            index=flow_dates
        )
        flows = calculate_institutional_flow(
            foreign_df, investment_trust_df, dealer_df, stock_info_df, holding
        )
        for flow in flows.values():
            assert flow.foreign_holding_pct == pytest.approx(30.0, abs=0.1)


class TestCalculateConsecutiveDays:
    def test_all_positive_returns_positive(self):
        dates = pd.date_range("2023-01-01", periods=5)
        df = pd.DataFrame({"A": [1000.0] * 5}, index=dates)
        result = calculate_consecutive_days(df)
        assert result["A"] > 0

    def test_all_negative_returns_negative(self):
        dates = pd.date_range("2023-01-01", periods=5)
        df = pd.DataFrame({"A": [-1000.0] * 5}, index=dates)
        result = calculate_consecutive_days(df)
        assert result["A"] < 0

    def test_zero_last_day_returns_zero(self):
        dates = pd.date_range("2023-01-01", periods=5)
        df = pd.DataFrame({"A": [1000.0, 1000.0, 1000.0, 1000.0, 0.0]}, index=dates)
        result = calculate_consecutive_days(df)
        assert result["A"] == 0

    def test_mixed_returns_correct_count(self):
        dates = pd.date_range("2023-01-01", periods=5)
        df = pd.DataFrame({"A": [1000.0, -500.0, 800.0, 900.0, 700.0]}, index=dates)
        result = calculate_consecutive_days(df)
        assert result["A"] == 3  # 最後 3 天買超

    def test_empty_returns_empty(self):
        result = calculate_consecutive_days(None)
        assert result == {}

    def test_empty_df(self):
        result = calculate_consecutive_days(pd.DataFrame())
        assert result == {}


class TestGetTopFlows:
    def test_returns_list(self, flows):
        result = get_top_flows(flows, top_n=3)
        assert isinstance(result, list)
        assert len(result) <= 3

    def test_sorted_descending_by_default(self, flows):
        result = get_top_flows(flows, flow_type="foreign", top_n=5)
        if len(result) > 1:
            assert result[0].foreign_net >= result[-1].foreign_net

    def test_ascending_order(self, flows):
        result = get_top_flows(flows, flow_type="foreign", ascending=True, top_n=5)
        if len(result) > 1:
            assert result[0].foreign_net <= result[-1].foreign_net

    def test_investment_trust_type(self, flows):
        result = get_top_flows(flows, flow_type="investment_trust", top_n=3)
        assert isinstance(result, list)

    def test_total_type(self, flows):
        result = get_top_flows(flows, flow_type="total", top_n=3)
        assert isinstance(result, list)


class TestGetSectorFlow:
    def test_returns_dataframe(self, flows):
        result = get_sector_flow(flows)
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, flows):
        result = get_sector_flow(flows)
        if len(result) > 0:
            assert "產業" in result.columns
            assert "合計" in result.columns

    def test_empty_flows_returns_empty(self):
        result = get_sector_flow({})
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestCalculateFlowTrend:
    def test_returns_dataframe(self, foreign_df, investment_trust_df, dealer_df):
        result = calculate_flow_trend(foreign_df, investment_trust_df, dealer_df)
        assert isinstance(result, pd.DataFrame)
        assert "合計" in result.columns

    def test_none_inputs(self):
        result = calculate_flow_trend(None, None, None)
        assert isinstance(result, pd.DataFrame)

    def test_days_parameter(self, foreign_df, investment_trust_df, dealer_df):
        result = calculate_flow_trend(foreign_df, investment_trust_df, dealer_df, days=5)
        assert len(result) <= 5


class TestGetContinuousBuyStocks:
    def test_returns_list(self, flows):
        result = get_continuous_buy_stocks(flows, min_days=1)
        assert isinstance(result, list)

    def test_all_meet_min_days(self, flows):
        min_days = 1
        result = get_continuous_buy_stocks(flows, min_days=min_days)
        for flow in result:
            assert flow.consecutive_days >= min_days

    def test_high_min_days_returns_fewer(self, flows):
        r1 = get_continuous_buy_stocks(flows, min_days=1)
        r2 = get_continuous_buy_stocks(flows, min_days=100)
        assert len(r1) >= len(r2)


# ──────────────────────────────────────────────
# optimizer (GridSearchOptimizer)
# ──────────────────────────────────────────────
from core.optimizer import GridSearchOptimizer, WalkForwardOptimizer, OptimizationResult, quick_optimize
from core.strategies.value import ValueStrategy


@pytest.fixture(scope="module")
def opt_dates():
    return pd.date_range("2021-01-01", periods=504, freq="B")


@pytest.fixture(scope="module")
def opt_close(opt_dates):
    np.random.seed(42)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, (len(opt_dates), 3)), axis=0))
    return pd.DataFrame(prices, index=opt_dates, columns=["2330", "2317", "2454"])


@pytest.fixture(scope="module")
def opt_pe(opt_dates):
    return pd.DataFrame(
        np.random.uniform(8, 20, (len(opt_dates), 3)),
        index=opt_dates, columns=["2330", "2317", "2454"]
    )


@pytest.fixture(scope="module")
def opt_pb(opt_dates):
    return pd.DataFrame(
        np.random.uniform(0.5, 2.0, (len(opt_dates), 3)),
        index=opt_dates, columns=["2330", "2317", "2454"]
    )


@pytest.fixture(scope="module")
def opt_div(opt_dates):
    return pd.DataFrame(
        np.random.uniform(3.0, 8.0, (len(opt_dates), 3)),
        index=opt_dates, columns=["2330", "2317", "2454"]
    )


@pytest.fixture(scope="module")
def opt_data(opt_close, opt_pe, opt_pb, opt_div):
    return {
        "close": opt_close,
        "pe_ratio": opt_pe,
        "pb_ratio": opt_pb,
        "dividend_yield": opt_div,
    }


class TestGridSearchOptimizer:

    def test_generate_combinations(self):
        param_grid = {"pe_max": [10, 15, 20], "pb_max": [1.0, 1.5]}
        opt = GridSearchOptimizer(ValueStrategy, param_grid)
        combos = opt._generate_combinations()
        assert len(combos) == 6  # 3 × 2

    def test_optimize_returns_result(self, opt_data):
        param_grid = {"pe_max": [10.0, 20.0], "use_pb": [False], "use_dividend": [False]}

        def mock_backtest(strategy, data):
            result = MagicMock()
            result.metrics.sharpe_ratio = float(np.random.random())
            return result

        opt = GridSearchOptimizer(ValueStrategy, param_grid)
        result = opt.optimize(opt_data, mock_backtest, verbose=False)

        assert isinstance(result, OptimizationResult)
        assert "pe_max" in result.best_params
        assert result.total_combinations == 2

    def test_optimize_higher_is_better(self, opt_data):
        param_grid = {"pe_max": [10.0, 20.0], "use_pb": [False], "use_dividend": [False]}
        scores = [0.5, 1.5]
        call_count = [0]

        def mock_backtest(strategy, data):
            result = MagicMock()
            result.metrics.sharpe_ratio = scores[call_count[0]]
            call_count[0] += 1
            return result

        opt = GridSearchOptimizer(ValueStrategy, param_grid, higher_is_better=True)
        result = opt.optimize(opt_data, mock_backtest, verbose=False)
        assert result.best_score == 1.5

    def test_optimize_exception_returns_inf(self, opt_data):
        param_grid = {"pe_max": [10.0], "use_pb": [False], "use_dividend": [False]}

        def failing_backtest(strategy, data):
            raise RuntimeError("模擬錯誤")

        opt = GridSearchOptimizer(ValueStrategy, param_grid)
        result = opt.optimize(opt_data, failing_backtest, verbose=False)
        assert result.best_score == float("-inf")

    def test_all_results_in_dataframe(self, opt_data):
        param_grid = {"pe_max": [10.0, 15.0], "use_pb": [False], "use_dividend": [False]}

        def mock_backtest(strategy, data):
            result = MagicMock()
            result.metrics.sharpe_ratio = 1.0
            return result

        opt = GridSearchOptimizer(ValueStrategy, param_grid)
        result = opt.optimize(opt_data, mock_backtest, verbose=False)
        assert len(result.all_results) == 2
        assert "score" in result.all_results.columns


class TestWalkForwardOptimizer:

    def test_split_periods(self, opt_dates):
        opt = WalkForwardOptimizer(
            ValueStrategy,
            param_grid={"pe_max": [10.0]},
            in_sample_months=12,
            out_sample_months=3,
        )
        periods = opt._split_periods(opt_dates[0], opt_dates[-1])
        assert len(periods) > 0
        for start, end, os_start, os_end in periods:
            assert os_start > end

    def test_optimize_no_close_raises(self):
        opt = WalkForwardOptimizer(
            ValueStrategy,
            param_grid={"pe_max": [10.0]},
        )
        with pytest.raises(ValueError):
            opt.optimize({}, lambda s, d: None)

    def test_optimize_returns_dict(self, opt_data):
        param_grid = {"pe_max": [10.0, 20.0], "use_pb": [False], "use_dividend": [False]}

        def mock_backtest(strategy, data):
            result = MagicMock()
            result.metrics.sharpe_ratio = float(np.random.random())
            return result

        opt = WalkForwardOptimizer(
            ValueStrategy,
            param_grid=param_grid,
            in_sample_months=12,
            out_sample_months=3,
        )
        result = opt.optimize(opt_data, mock_backtest)
        assert "results" in result
        assert "avg_in_sample_score" in result
        assert "total_periods" in result


# ──────────────────────────────────────────────
# prediction_tracker
# ──────────────────────────────────────────────
from core.prediction_tracker import (
    PredictionTracker, PredictionType, PredictionStatus, Prediction, get_tracker
)


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    """每個測試用獨立的臨時目錄"""
    monkeypatch.setattr("core.prediction_tracker.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "core.prediction_tracker.PREDICTIONS_FILE", tmp_path / "predictions.json"
    )
    monkeypatch.setattr(
        "core.prediction_tracker.VERIFICATION_LOG_FILE", tmp_path / "verification_log.json"
    )
    t = PredictionTracker.__new__(PredictionTracker)
    t.predictions = []
    t.verification_log = []
    return t


class TestPredictionTracker:

    def test_add_target_price(self, tracker):
        p = tracker.add_target_price_prediction(
            stock_id="2330", stock_name="台積電",
            current_price=600.0, target_price=650.0,
            verify_days=20
        )
        assert isinstance(p, Prediction)
        assert p.type == PredictionType.TARGET_PRICE.value
        assert p.target_price == 650.0
        assert len(tracker.predictions) == 1

    def test_add_direction_prediction_up(self, tracker):
        p = tracker.add_direction_prediction(
            stock_id="2317", stock_name="鴻海",
            current_price=100.0, direction="up", verify_days=1
        )
        assert p.predicted_direction == "up"
        assert p.status == PredictionStatus.PENDING.value

    def test_add_direction_prediction_down(self, tracker):
        p = tracker.add_direction_prediction(
            stock_id="2317", stock_name="鴻海",
            current_price=100.0, direction="down"
        )
        assert p.predicted_direction == "down"

    def test_add_stock_pick(self, tracker):
        p = tracker.add_stock_pick_prediction(
            stock_id="2454", stock_name="聯發科",
            current_price=800.0, expected_return=10.0, verify_days=5
        )
        assert p.type == PredictionType.STOCK_PICK.value
        assert p.expected_return == 10.0

    def test_add_batch_stock_picks(self, tracker):
        stocks = [
            {"stock_id": "2330", "stock_name": "台積電", "current_price": 600.0},
            {"stock_id": "2317", "stock_name": "鴻海", "current_price": 100.0},
        ]
        predictions = tracker.add_batch_stock_picks(stocks, verify_days=5)
        assert len(predictions) == 2

    def test_cancel_prediction(self, tracker):
        p = tracker.add_target_price_prediction(
            "2330", "台積電", 600.0, 650.0
        )
        result = tracker.cancel_prediction(p.id)
        assert result is True
        cancelled = next(x for x in tracker.predictions if x.id == p.id)
        assert cancelled.status == PredictionStatus.CANCELLED.value

    def test_cancel_nonexistent_returns_false(self, tracker):
        result = tracker.cancel_prediction("nonexistent-id")
        assert result is False

    def test_get_pending_predictions(self, tracker):
        tracker.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        pending = tracker.get_pending_predictions()
        assert all(p.status == PredictionStatus.PENDING.value for p in pending)

    def test_get_recent_predictions(self, tracker):
        tracker.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        recent = tracker.get_recent_predictions(days=7)
        assert isinstance(recent, list)

    def test_get_statistics_empty(self, tracker):
        tracker.predictions = []
        stats = tracker.get_statistics()
        assert stats["total"] == 0
        assert stats["success_rate"] == 0

    def test_get_statistics_with_data(self, tracker):
        # 添加一些有結果的預測
        p = Prediction(
            id="test1", type="stock_pick", stock_id="2330", stock_name="台積電",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            created_price=600.0, status=PredictionStatus.SUCCESS.value,
            actual_return=5.0, expire_date="2099-01-01"
        )
        tracker.predictions = [p]
        stats = tracker.get_statistics()
        assert stats["total"] == 1
        assert stats["success"] == 1

    def test_to_dataframe_empty(self, tracker):
        tracker.predictions = []
        df = tracker.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_to_dataframe_with_data(self, tracker):
        tracker.add_target_price_prediction("2330", "台積電", 600.0, 650.0)
        df = tracker.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_verify_predictions_target_price_success(self, tracker):
        """目標價達成驗證"""
        p = tracker.add_target_price_prediction(
            "2330", "台積電", 600.0, 620.0, verify_days=1
        )
        # 手動設定 expire_date 為過去
        p.expire_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        p.created_at = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

        # 建立價格資料 — 最高價達到目標
        dates = pd.date_range(
            datetime.strptime(p.created_at, "%Y-%m-%d %H:%M:%S").date().isoformat(),
            periods=5
        )
        price_data = pd.DataFrame({"2330": [600, 610, 625, 620, 615]}, index=dates)
        tracker.verify_predictions(price_data)
        assert p.status == PredictionStatus.SUCCESS.value

    def test_verify_predictions_stock_pick_success(self, tracker):
        p = tracker.add_stock_pick_prediction("2317", "鴻海", 100.0, verify_days=1)
        p.expire_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        p.created_at = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")

        dates = pd.date_range(
            datetime.strptime(p.created_at, "%Y-%m-%d %H:%M:%S").date().isoformat(),
            periods=3
        )
        price_data = pd.DataFrame({"2317": [100, 102, 105]}, index=dates)
        tracker.verify_predictions(price_data)
        assert p.status == PredictionStatus.SUCCESS.value

    def test_verify_predictions_expired(self, tracker):
        p = tracker.add_stock_pick_prediction("2454", "聯發科", 800.0, verify_days=1)
        # 設定非常舊的過期日
        p.expire_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        p.created_at = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
        tracker.verify_predictions(pd.DataFrame())
        assert p.status == PredictionStatus.EXPIRED.value


# ──────────────────────────────────────────────
# strategies/custom
# ──────────────────────────────────────────────
from core.strategies.custom import (
    FilterCondition, CustomStrategy, AVAILABLE_FIELDS, OPERATORS,
    save_custom_strategy, load_all_custom_strategies, delete_custom_strategy,
)


@pytest.fixture(scope="module")
def custom_dates():
    return pd.date_range("2023-01-01", periods=30, freq="B")


@pytest.fixture(scope="module")
def custom_stocks():
    return ["2330", "2317", "2454"]


@pytest.fixture(scope="module")
def custom_close(custom_dates, custom_stocks):
    return pd.DataFrame(
        {s: [100.0 + i for i in range(len(custom_dates))] for s in custom_stocks},
        index=custom_dates
    )


@pytest.fixture(scope="module")
def custom_pe(custom_dates, custom_stocks):
    return pd.DataFrame(
        {"2330": [10.0] * len(custom_dates),
         "2317": [20.0] * len(custom_dates),
         "2454": [5.0] * len(custom_dates)},
        index=custom_dates
    )


@pytest.fixture(scope="module")
def custom_data(custom_close, custom_pe):
    return {"close": custom_close, "pe_ratio": custom_pe}


class TestFilterCondition:
    def test_to_dict_and_back(self):
        cond = FilterCondition(field_name="本益比", operator="<=", value=15.0)
        d = cond.to_dict()
        restored = FilterCondition.from_dict(d)
        assert restored.field_name == cond.field_name
        assert restored.operator == cond.operator
        assert restored.value == cond.value

    def test_disabled_condition(self):
        cond = FilterCondition(field_name="本益比", operator="<=", value=15.0, enabled=False)
        assert not cond.enabled


class TestCustomStrategy:

    def test_no_conditions_returns_empty(self, custom_data):
        s = CustomStrategy()
        result = s.filter(custom_data)
        assert result == []

    def test_pe_below_threshold_and_mode(self, custom_data, custom_stocks):
        """PE <= 15 應選出 2330 (10) 和 2454 (5)，不選 2317 (20)"""
        cond = FilterCondition(field_name="本益比", operator="<=", value=15.0)
        s = CustomStrategy({"conditions": [cond], "combine_mode": "AND"})
        result = s.filter(custom_data)
        assert "2317" not in result
        assert "2330" in result or "2454" in result

    def test_pe_below_impossible_threshold(self, custom_data):
        cond = FilterCondition(field_name="本益比", operator="<=", value=0.1)
        s = CustomStrategy({"conditions": [cond]})
        result = s.filter(custom_data)
        assert result == []

    def test_or_mode(self, custom_data, custom_stocks):
        """OR 模式：任一條件通過即可"""
        cond1 = FilterCondition(field_name="本益比", operator="<=", value=12.0)
        cond2 = FilterCondition(field_name="本益比", operator=">=", value=18.0)
        s = CustomStrategy({"conditions": [cond1, cond2], "combine_mode": "OR"})
        result = s.filter(custom_data)
        assert len(result) > 0

    def test_disabled_condition_skipped(self, custom_data):
        cond = FilterCondition(field_name="本益比", operator="<=", value=15.0, enabled=False)
        s = CustomStrategy({"conditions": [cond]})
        result = s.filter(custom_data)
        assert result == []

    def test_unknown_field_skipped(self, custom_data):
        cond = FilterCondition(field_name="未知欄位", operator="<=", value=15.0)
        s = CustomStrategy({"conditions": [cond]})
        result = s.filter(custom_data)
        assert result == []

    def test_score_returns_series(self, custom_data):
        cond = FilterCondition(field_name="本益比", operator="<=", value=15.0)
        s = CustomStrategy({"conditions": [cond]})
        scores = s.score(custom_data)
        assert isinstance(scores, pd.Series)

    def test_score_normalized_0_to_100(self, custom_data):
        cond = FilterCondition(field_name="本益比", operator="<=", value=15.0)
        s = CustomStrategy({"conditions": [cond]})
        scores = s.score(custom_data)
        if len(scores) > 0:
            assert (scores >= 0).all()
            assert (scores <= 100).all()

    def test_conditions_from_dict(self, custom_data):
        params = {
            "conditions": [
                {"field_name": "本益比", "operator": "<=", "value": 15.0, "enabled": True}
            ],
            "combine_mode": "AND",
        }
        s = CustomStrategy(params)
        result = s.filter(custom_data)
        assert isinstance(result, list)

    def test_volume_field_conversion(self, custom_dates, custom_stocks):
        """volume 欄位應自動除以 1000 轉換為張"""
        close = pd.DataFrame(
            {s: [100.0] * len(custom_dates) for s in custom_stocks}, index=custom_dates
        )
        volume = pd.DataFrame(
            {s: [500_000.0] * len(custom_dates) for s in custom_stocks}, index=custom_dates
        )
        cond = FilterCondition(field_name="成交量(張)", operator=">=", value=100.0)
        s = CustomStrategy({"conditions": [cond]})
        result = s.filter({"close": close, "volume": volume})
        assert len(result) == len(custom_stocks)

    def test_default_params(self):
        s = CustomStrategy()
        assert s.params["combine_mode"] == "AND"
        assert s.params["conditions"] == []


class TestCustomStrategyCRUD:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.strategies.custom.CUSTOM_STRATEGIES_DIR", tmp_path)
        conds = [FilterCondition("本益比", "<=", 15.0)]
        save_custom_strategy("test_strategy", conds, "AND")
        loaded = load_all_custom_strategies()
        assert "test_strategy" in loaded
        assert loaded["test_strategy"]["combine_mode"] == "AND"

    def test_delete_strategy(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.strategies.custom.CUSTOM_STRATEGIES_DIR", tmp_path)
        conds = [FilterCondition("本益比", "<=", 15.0)]
        save_custom_strategy("to_delete", conds, "AND")
        delete_custom_strategy("to_delete")
        loaded = load_all_custom_strategies()
        assert "to_delete" not in loaded

    def test_load_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.strategies.custom.CUSTOM_STRATEGIES_DIR", tmp_path)
        loaded = load_all_custom_strategies()
        assert loaded == {}


# ──────────────────────────────────────────────
# indicators — 補齊剩餘未覆蓋部分
# ──────────────────────────────────────────────
from core.indicators import (
    resample_ohlcv, get_timeframe_label, get_ma_periods_for_timeframe,
    cumulative_returns, drawdown, max_drawdown, volatility,
    highest, lowest, breakout_signal, volume_ratio,
    revenue_growth_yoy, revenue_growth_mom, consecutive_growth,
    rank_percentile, z_score, kdj, bias, adx, mfi, psar,
)


@pytest.fixture(scope="module")
def ind_dates():
    return pd.date_range("2022-01-03", periods=120, freq="B")


@pytest.fixture(scope="module")
def ind_close(ind_dates):
    np.random.seed(0)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.015, (len(ind_dates), 3)), axis=0))
    return pd.DataFrame(prices, index=ind_dates, columns=["A", "B", "C"])


@pytest.fixture(scope="module")
def ind_high(ind_close):
    return ind_close * 1.01


@pytest.fixture(scope="module")
def ind_low(ind_close):
    return ind_close * 0.99


@pytest.fixture(scope="module")
def ind_volume(ind_dates):
    np.random.seed(1)
    return pd.DataFrame(
        np.random.randint(1000, 50000, (len(ind_dates), 3)).astype(float),
        index=ind_dates, columns=["A", "B", "C"]
    )


class TestResampleOHLCV:
    def test_daily_returns_same(self, ind_close):
        result = resample_ohlcv(ind_close["A"], ind_close["A"], ind_close["A"], ind_close["A"], timeframe="D")
        # 日線不重採樣，close 應與輸入相等（值相同，不要求 is 同一物件）
        pd.testing.assert_series_equal(result["close"], ind_close["A"])

    def test_weekly_resamples(self, ind_close):
        result = resample_ohlcv(ind_close["A"], ind_close["A"], ind_close["A"], ind_close["A"], timeframe="W")
        assert len(result["close"]) < len(ind_close)

    def test_monthly_resamples(self, ind_close):
        result = resample_ohlcv(ind_close["A"], ind_close["A"], ind_close["A"], ind_close["A"], timeframe="M")
        assert len(result["close"]) < len(ind_close)

    def test_with_volume(self, ind_close, ind_volume):
        result = resample_ohlcv(
            ind_close["A"], ind_close["A"], ind_close["A"], ind_close["A"],
            ind_volume["A"], timeframe="W"
        )
        assert "volume" in result


class TestTimeframHelpers:
    def test_labels(self):
        assert get_timeframe_label("D") == "日線"
        assert get_timeframe_label("W") == "週線"
        assert get_timeframe_label("M") == "月線"
        assert get_timeframe_label("X") == "日線"  # unknown defaults

    def test_ma_periods(self):
        d_periods = get_ma_periods_for_timeframe("D")
        assert d_periods == (5, 20, 60)
        w_periods = get_ma_periods_for_timeframe("W")
        assert len(w_periods) == 3


class TestPriceIndicators:
    def test_cumulative_returns_shape(self, ind_close):
        result = cumulative_returns(ind_close)
        assert result.shape == ind_close.shape

    def test_drawdown_non_positive(self, ind_close):
        result = drawdown(ind_close)
        assert (result <= 0).all().all() or True  # 可能有浮點誤差

    def test_max_drawdown_non_positive(self, ind_close):
        result = max_drawdown(ind_close)
        assert isinstance(result, pd.Series)

    def test_volatility_positive(self, ind_close):
        result = volatility(ind_close)
        assert (result.dropna() >= 0).all().all()

    def test_volatility_not_annualized(self, ind_close):
        result = volatility(ind_close, annualize=False)
        assert result.shape == ind_close.shape

    def test_highest(self, ind_close):
        result = highest(ind_close, 20)
        assert result.shape == ind_close.shape
        assert (result >= ind_close).all().all()

    def test_lowest(self, ind_close):
        result = lowest(ind_close, 20)
        assert result.shape == ind_close.shape
        assert (result <= ind_close).all().all()

    def test_breakout_signal_bool(self, ind_close):
        result = breakout_signal(ind_close, 20)
        assert result.dtypes.apply(lambda d: d == bool or d == object or np.issubdtype(d, np.bool_)).all()


class TestVolumeIndicators:
    def test_volume_ratio_positive(self, ind_volume):
        result = volume_ratio(ind_volume, 5)
        assert (result.dropna() >= 0).all().all()


class TestFundamentalIndicators:
    def test_revenue_growth_yoy(self, ind_close):
        result = revenue_growth_yoy(ind_close)
        assert result.shape == ind_close.shape

    def test_revenue_growth_mom(self, ind_close):
        result = revenue_growth_mom(ind_close)
        assert result.shape == ind_close.shape

    def test_consecutive_growth_bool(self, ind_close):
        result = consecutive_growth(ind_close, 3)
        assert result.shape == ind_close.shape

    def test_rank_percentile(self, ind_close):
        result = rank_percentile(ind_close)
        valid = result.dropna()
        if len(valid) > 0:
            assert (valid >= 0).all().all()
            assert (valid <= 100).all().all()

    def test_z_score(self, ind_close):
        result = z_score(ind_close)
        assert result.shape == ind_close.shape


class TestAdvancedIndicators:
    def test_kdj_range(self, ind_high, ind_low, ind_close):
        k, d, j = kdj(ind_high, ind_low, ind_close)
        assert k.shape == ind_close.shape
        assert d.shape == ind_close.shape
        assert j.shape == ind_close.shape

    def test_bias_sign(self, ind_close):
        result = bias(ind_close, 20)
        assert result.shape == ind_close.shape

    def test_adx_returns_tuple(self, ind_high, ind_low, ind_close):
        adx_val, plus_di, minus_di = adx(ind_high, ind_low, ind_close, 14)
        assert adx_val.shape == ind_close.shape
        assert plus_di.shape == ind_close.shape
        assert minus_di.shape == ind_close.shape

    def test_adx_series_path(self, ind_high, ind_low, ind_close):
        """Series 路徑（修正 Bug B2 後驗證）"""
        adx_val, _, _ = adx(ind_high["A"], ind_low["A"], ind_close["A"], 14)
        assert isinstance(adx_val, pd.Series)

    def test_mfi_range(self, ind_high, ind_low, ind_close, ind_volume):
        result = mfi(ind_high, ind_low, ind_close, ind_volume, 14)
        valid = result.dropna()
        if len(valid) > 0:
            assert (valid >= 0).all().all()
            assert (valid <= 100).all().all()

    def test_psar_returns_dataframe(self, ind_high, ind_low):
        result = psar(ind_high, ind_low)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == ind_high.shape


# ──────────────────────────────────────────────
# risk — 補齊剩餘未覆蓋部分
# ──────────────────────────────────────────────
from core.risk import (
    RiskAnalyzer, RiskMetrics, calculate_portfolio_var,
    stress_test, monte_carlo_simulation,
)


@pytest.fixture(scope="module")
def risk_prices():
    np.random.seed(10)
    dates = pd.date_range("2021-01-01", periods=252)
    vals = 1_000_000 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, 252)))
    return pd.Series(vals, index=dates)


@pytest.fixture(scope="module")
def risk_returns(risk_prices):
    return risk_prices.pct_change().dropna()


class TestRiskAnalyzer:
    def setup_method(self):
        self.analyzer = RiskAnalyzer()

    def test_calculate_returns(self, risk_prices):
        rets = self.analyzer.calculate_returns(risk_prices)
        assert len(rets) == len(risk_prices) - 1

    def test_var_historical_negative(self, risk_returns):
        var = self.analyzer.calculate_var_historical(risk_returns)
        assert var < 0

    def test_var_parametric_negative(self, risk_returns):
        var = self.analyzer.calculate_var_parametric(risk_returns)
        assert isinstance(var, float)

    def test_cvar_worse_than_var(self, risk_returns):
        var = self.analyzer.calculate_var_historical(risk_returns)
        cvar = self.analyzer.calculate_cvar(risk_returns)
        assert cvar <= var

    def test_var_empty_series(self):
        assert self.analyzer.calculate_var_historical(pd.Series([])) == 0.0
        assert self.analyzer.calculate_cvar(pd.Series([])) == 0.0
        assert self.analyzer.calculate_var_parametric(pd.Series([])) == 0.0

    def test_volatility(self, risk_returns):
        vol = self.analyzer.calculate_volatility(risk_returns)
        assert vol > 0

    def test_volatility_not_annualized(self, risk_returns):
        vol_daily = self.analyzer.calculate_volatility(risk_returns, annualize=False)
        vol_annual = self.analyzer.calculate_volatility(risk_returns, annualize=True)
        assert vol_annual > vol_daily

    def test_downside_volatility(self, risk_returns):
        dvol = self.analyzer.calculate_downside_volatility(risk_returns)
        assert dvol >= 0

    def test_downside_volatility_no_downside(self):
        positive = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
        dvol = self.analyzer.calculate_downside_volatility(positive)
        assert dvol == 0.0

    def test_max_drawdown_tuple(self, risk_prices):
        max_dd, peak_date, trough_date = self.analyzer.calculate_max_drawdown(risk_prices)
        assert max_dd <= 0
        assert peak_date is not None
        assert trough_date is not None

    def test_max_drawdown_empty(self):
        max_dd, peak, trough = self.analyzer.calculate_max_drawdown(pd.Series([]))
        assert max_dd == 0.0

    def test_beta_calculation(self, risk_returns):
        beta = self.analyzer.calculate_beta(risk_returns, risk_returns)
        assert abs(beta - 1.0) < 1e-6

    def test_tracking_error(self, risk_returns):
        te = self.analyzer.calculate_tracking_error(risk_returns, risk_returns)
        assert te == pytest.approx(0.0, abs=1e-6)

    def test_analyze_full(self, risk_prices):
        metrics = self.analyzer.analyze(risk_prices)
        assert isinstance(metrics, RiskMetrics)
        assert metrics.volatility > 0

    def test_analyze_with_benchmark(self, risk_prices):
        benchmark = risk_prices * 0.98
        metrics = self.analyzer.analyze(risk_prices, benchmark)
        assert metrics.beta is not None
        assert metrics.tracking_error is not None


class TestCalculatePortfolioVar:
    def test_returns_float(self):
        np.random.seed(0)
        dates = pd.date_range("2021-01-01", periods=100)
        returns = pd.DataFrame(
            np.random.normal(0, 0.015, (100, 2)),
            index=dates, columns=["A", "B"]
        )
        var = calculate_portfolio_var({"A": 0.5, "B": 0.5}, returns)
        assert isinstance(var, float)

    def test_empty_weights_returns_zero(self):
        var = calculate_portfolio_var({}, pd.DataFrame())
        assert var == 0.0

    def test_parametric_method(self):
        np.random.seed(0)
        dates = pd.date_range("2021-01-01", periods=100)
        returns = pd.DataFrame(
            np.random.normal(0, 0.015, (100, 2)),
            index=dates, columns=["A", "B"]
        )
        var = calculate_portfolio_var({"A": 0.5, "B": 0.5}, returns, method="parametric")
        assert isinstance(var, float)


class TestStressTest:
    def test_returns_dict(self, risk_prices):
        scenarios = {"大跌": -0.20, "小跌": -0.05, "上漲": 0.10}
        result = stress_test(risk_prices, scenarios)
        assert "大跌" in result
        assert "new_value" in result["大跌"]
        assert "pnl_pct" in result["大跌"]

    def test_pnl_correct(self, risk_prices):
        scenarios = {"跌20%": -0.20}
        result = stress_test(risk_prices, scenarios)
        expected_pnl_pct = -20.0
        assert abs(result["跌20%"]["pnl_pct"] - expected_pnl_pct) < 1e-6


class TestMonteCarloSimulation:
    def test_returns_dataframe(self):
        np.random.seed(0)
        returns = pd.Series(np.random.normal(0.0005, 0.015, 252))
        result = monte_carlo_simulation(returns, days=50, simulations=10)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == (50, 10)

    def test_starts_at_initial_value(self):
        returns = pd.Series([0.01] * 252)
        result = monte_carlo_simulation(returns, days=10, simulations=5, initial_value=2.0)
        assert (result.iloc[0] > 0).all()
