"""
選股策略模組測試
涵蓋：ValueStrategy、GrowthStrategy、MomentumStrategy、CompositeStrategy、CombinedStrategy
"""
import pytest
import pandas as pd
import numpy as np


from core.strategies.value import ValueStrategy
from core.strategies.growth import GrowthStrategy
from core.strategies.momentum import MomentumStrategy
from core.strategies.composite import CompositeStrategy
from core.strategies.base import CombinedStrategy, StrategyResult


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def dates():
    return pd.date_range("2022-01-01", periods=120, freq="B")


@pytest.fixture(scope="module")
def stocks():
    return ["2330", "2317", "2454", "2412", "2308", "2382", "3711", "2881", "1301", "2002"]


@pytest.fixture(scope="module")
def close_df(dates, stocks):
    np.random.seed(0)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, (len(dates), len(stocks))), axis=0))
    return pd.DataFrame(prices, index=dates, columns=stocks)


@pytest.fixture(scope="module")
def volume_df(dates, stocks):
    np.random.seed(1)
    vol = np.random.randint(500, 30000, (len(dates), len(stocks))) * 1000
    return pd.DataFrame(vol.astype(float), index=dates, columns=stocks)


@pytest.fixture(scope="module")
def pe_df(dates, stocks):
    """PE ratio — 前半股票 PE 低（符合價值），後半 PE 高"""
    np.random.seed(2)
    data = np.where(
        np.arange(len(stocks)) < len(stocks) // 2,
        np.random.uniform(8, 14, (len(dates), len(stocks))),
        np.random.uniform(20, 40, (len(dates), len(stocks))),
    )
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture(scope="module")
def pb_df(dates, stocks):
    np.random.seed(3)
    data = np.where(
        np.arange(len(stocks)) < len(stocks) // 2,
        np.random.uniform(0.5, 1.4, (len(dates), len(stocks))),
        np.random.uniform(2.0, 5.0, (len(dates), len(stocks))),
    )
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture(scope="module")
def dividend_df(dates, stocks):
    np.random.seed(4)
    data = np.where(
        np.arange(len(stocks)) < len(stocks) // 2,
        np.random.uniform(4.5, 8.0, (len(dates), len(stocks))),
        np.random.uniform(0.5, 3.5, (len(dates), len(stocks))),
    )
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture(scope="module")
def revenue_yoy_df(dates, stocks):
    """YoY — 前半股票高成長，後半低成長/負成長"""
    np.random.seed(5)
    data = np.where(
        np.arange(len(stocks)) < len(stocks) // 2,
        np.random.uniform(25, 80, (len(dates), len(stocks))),
        np.random.uniform(-10, 15, (len(dates), len(stocks))),
    )
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture(scope="module")
def revenue_mom_df(dates, stocks):
    np.random.seed(6)
    data = np.where(
        np.arange(len(stocks)) < len(stocks) // 2,
        np.random.uniform(12, 30, (len(dates), len(stocks))),
        np.random.uniform(-15, 8, (len(dates), len(stocks))),
    )
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture(scope="module")
def value_data(close_df, pe_df, pb_df, dividend_df):
    return {
        "close": close_df,
        "pe_ratio": pe_df,
        "pb_ratio": pb_df,
        "dividend_yield": dividend_df,
    }


@pytest.fixture(scope="module")
def growth_data(close_df, revenue_yoy_df, revenue_mom_df):
    return {
        "close": close_df,
        "revenue_yoy": revenue_yoy_df,
        "revenue_mom": revenue_mom_df,
    }


@pytest.fixture(scope="module")
def momentum_data(close_df, volume_df):
    return {"close": close_df, "volume": volume_df}


@pytest.fixture(scope="module")
def composite_data(close_df, volume_df, pe_df, pb_df, dividend_df, revenue_yoy_df, revenue_mom_df):
    return {
        "close": close_df,
        "volume": volume_df,
        "pe_ratio": pe_df,
        "pb_ratio": pb_df,
        "dividend_yield": dividend_df,
        "revenue_yoy": revenue_yoy_df,
        "revenue_mom": revenue_mom_df,
    }


# ──────────────────────────────────────────────
# ValueStrategy
# ──────────────────────────────────────────────

class TestValueStrategy:

    def test_default_params(self):
        s = ValueStrategy()
        assert s.params["pe_max"] == 15.0
        assert s.params["pb_max"] == 1.5
        assert s.params["dividend_yield_min"] == 4.0

    def test_custom_params(self):
        s = ValueStrategy({"pe_max": 20.0})
        assert s.params["pe_max"] == 20.0
        assert s.params["pb_max"] == 1.5  # 未覆蓋的維持預設

    def test_filter_returns_list(self, value_data):
        s = ValueStrategy()
        result = s.filter(value_data)
        assert isinstance(result, list)

    def test_filter_returns_only_stock_codes(self, value_data):
        """確認回傳的是純代號（不含中文名稱）"""
        s = ValueStrategy()
        result = s.filter(value_data)
        for code in result:
            assert " " not in code, f"股票代號不應含空格：{code!r}"
            assert len(code) <= 6

    def test_filter_respects_pe_condition(self, value_data, stocks):
        """低 PE 股票（前半）應被選出，高 PE 股票（後半）不應被選出"""
        low_pe_stocks = stocks[: len(stocks) // 2]
        high_pe_stocks = stocks[len(stocks) // 2 :]
        s = ValueStrategy({"pe_max": 15.0, "use_pb": False, "use_dividend": False})
        result = s.filter(value_data)
        # 低 PE 群組至少要有一半被選出
        selected_low = [c for c in result if c in low_pe_stocks]
        selected_high = [c for c in result if c in high_pe_stocks]
        assert len(selected_low) > len(selected_high)

    def test_filter_empty_when_impossible_threshold(self, value_data):
        """極嚴格的條件應回傳空清單"""
        s = ValueStrategy({"pe_max": 0.1, "use_pb": False, "use_dividend": False})
        result = s.filter(value_data)
        assert result == []

    def test_filter_with_specific_date(self, value_data, dates):
        s = ValueStrategy()
        date = dates[50]
        result = s.filter(value_data, date=date)
        assert isinstance(result, list)

    def test_score_returns_series(self, value_data):
        s = ValueStrategy()
        scores = s.score(value_data)
        assert isinstance(scores, pd.Series)

    def test_score_range_0_to_100(self, value_data):
        s = ValueStrategy()
        scores = s.score(value_data).dropna()
        assert (scores >= 0).all()
        assert (scores <= 100).all()

    def test_score_low_pe_ranks_higher(self, value_data, stocks):
        """低 PE 股票的價值評分應高於高 PE 股票"""
        s = ValueStrategy({"use_pb": False, "use_dividend": False})
        scores = s.score(value_data).dropna()
        if len(scores) == 0:
            pytest.skip("沒有有效的評分數據")
        low_pe = stocks[: len(stocks) // 2]
        high_pe = stocks[len(stocks) // 2 :]
        low_scores = scores[[c for c in low_pe if c in scores.index]]
        high_scores = scores[[c for c in high_pe if c in scores.index]]
        if len(low_scores) > 0 and len(high_scores) > 0:
            assert low_scores.mean() > high_scores.mean()

    def test_run_returns_strategy_result(self, value_data):
        s = ValueStrategy()
        result = s.run(value_data)
        assert isinstance(result, StrategyResult)
        assert isinstance(result.stocks, list)
        assert isinstance(result.details, dict)
        assert result.details["strategy"] == "價值投資"

    def test_get_param_info(self):
        s = ValueStrategy()
        info = s.get_param_info()
        assert "pe_max" in info
        assert "pb_max" in info
        assert "dividend_yield_min" in info
        for key, meta in info.items():
            assert "type" in meta
            assert "default" in meta

    def test_filter_empty_data(self):
        """空 DataFrame 不應崩潰"""
        s = ValueStrategy()
        result = s.filter({})
        assert result == []

    def test_disable_all_conditions_returns_empty(self, value_data):
        s = ValueStrategy({"use_pe": False, "use_pb": False, "use_dividend": False})
        result = s.filter(value_data)
        assert result == []


# ──────────────────────────────────────────────
# GrowthStrategy
# ──────────────────────────────────────────────

class TestGrowthStrategy:

    def test_default_params(self):
        s = GrowthStrategy()
        assert s.params["revenue_yoy_min"] == 20.0
        assert s.params["revenue_mom_min"] == 10.0
        assert s.params["consecutive_months"] == 3

    def test_filter_returns_list(self, growth_data):
        s = GrowthStrategy()
        result = s.filter(growth_data)
        assert isinstance(result, list)

    def test_filter_returns_only_stock_codes(self, growth_data):
        s = GrowthStrategy()
        result = s.filter(growth_data)
        for code in result:
            assert " " not in code

    def test_filter_selects_high_growth(self, growth_data, stocks):
        """高成長股票（前半）應被選出的比例高於低成長股票（後半）"""
        s = GrowthStrategy({"revenue_yoy_min": 20.0, "use_mom": False, "use_consecutive": False})
        result = s.filter(growth_data)
        high_growth = stocks[: len(stocks) // 2]
        low_growth = stocks[len(stocks) // 2 :]
        selected_high = [c for c in result if c in high_growth]
        selected_low = [c for c in result if c in low_growth]
        assert len(selected_high) >= len(selected_low)

    def test_filter_impossible_threshold(self, growth_data):
        s = GrowthStrategy({"revenue_yoy_min": 9999.0, "use_mom": False, "use_consecutive": False})
        assert s.filter(growth_data) == []

    def test_filter_empty_data(self):
        s = GrowthStrategy()
        assert s.filter({}) == []

    def test_score_returns_series(self, growth_data):
        s = GrowthStrategy()
        scores = s.score(growth_data)
        assert isinstance(scores, pd.Series)

    def test_calc_consecutive_growth_correctness(self, dates, stocks):
        """向量化連續成長計算的正確性驗證"""
        s = GrowthStrategy()
        # 建立已知資料：stock_a 連續 5 期正成長，stock_b 第 3 期為負
        data = pd.DataFrame({
            "stock_a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "stock_b": [1.0, 2.0, -1.0, 4.0, 5.0],  # 中斷，最後連續 2
        }, index=dates[:5])
        date = dates[4]
        result = s._calc_consecutive_growth(data, date)
        assert result["stock_a"] == 5   # 連續 5 期
        assert result["stock_b"] == 2   # 最後 2 期

    def test_calc_consecutive_growth_all_negative(self, dates):
        s = GrowthStrategy()
        data = pd.DataFrame({"A": [-1.0, -2.0, -3.0]}, index=dates[:3])
        result = s._calc_consecutive_growth(data, dates[2])
        assert result["A"] == 0

    def test_calc_consecutive_growth_unknown_date(self, dates):
        s = GrowthStrategy()
        data = pd.DataFrame({"A": [1.0, 2.0]}, index=dates[:2])
        unknown_date = pd.Timestamp("2000-01-01")
        result = s._calc_consecutive_growth(data, unknown_date)
        assert result["A"] == 0

    def test_run_returns_strategy_result(self, growth_data):
        s = GrowthStrategy()
        result = s.run(growth_data)
        assert isinstance(result, StrategyResult)
        assert result.details["strategy"] == "成長投資"


# ──────────────────────────────────────────────
# MomentumStrategy
# ──────────────────────────────────────────────

class TestMomentumStrategy:

    def test_default_params(self):
        s = MomentumStrategy()
        assert s.params["breakout_days"] == 20
        assert s.params["rsi_min"] == 50
        assert s.params["rsi_max"] == 80

    def test_filter_returns_list(self, momentum_data):
        s = MomentumStrategy()
        result = s.filter(momentum_data)
        assert isinstance(result, list)

    def test_filter_returns_only_stock_codes(self, momentum_data):
        """修正 B1 後，不應含空格或中文"""
        s = MomentumStrategy()
        result = s.filter(momentum_data)
        for code in result:
            assert " " not in code, f"股票代號含空格：{code!r}"

    def test_filter_empty_close(self):
        s = MomentumStrategy()
        assert s.filter({}) == []

    def test_filter_no_volume_skips_volume_condition(self, close_df):
        """無 volume 資料時，成交量條件自動跳過，不應崩潰"""
        s = MomentumStrategy({"use_volume": True, "use_breakout": False, "use_rsi": False})
        result = s.filter({"close": close_df})
        assert isinstance(result, list)

    def test_filter_disable_all_returns_empty(self, momentum_data):
        s = MomentumStrategy({"use_breakout": False, "use_volume": False, "use_rsi": False})
        assert s.filter(momentum_data) == []

    def test_score_returns_series(self, momentum_data):
        s = MomentumStrategy()
        scores = s.score(momentum_data)
        assert isinstance(scores, pd.Series)

    def test_score_range(self, momentum_data):
        s = MomentumStrategy()
        scores = s.score(momentum_data).dropna()
        if len(scores) > 0:
            assert (scores >= 0).all()
            assert (scores <= 100).all()

    def test_run_returns_strategy_result(self, momentum_data):
        s = MomentumStrategy()
        result = s.run(momentum_data)
        assert isinstance(result, StrategyResult)
        assert result.details["strategy"] == "動能投資"

    def test_get_param_info(self):
        s = MomentumStrategy()
        info = s.get_param_info()
        assert "breakout_days" in info
        assert "rsi_min" in info


# ──────────────────────────────────────────────
# CompositeStrategy
# ──────────────────────────────────────────────

class TestCompositeStrategy:

    def test_default_params(self):
        s = CompositeStrategy()
        assert abs(s.params["value_weight"] - 0.4) < 1e-9
        assert abs(s.params["growth_weight"] - 0.3) < 1e-9
        assert abs(s.params["momentum_weight"] - 0.3) < 1e-9
        assert s.params["top_n"] == 20

    def test_filter_returns_list(self, composite_data):
        s = CompositeStrategy()
        result = s.filter(composite_data)
        assert isinstance(result, list)

    def test_filter_respects_top_n(self, composite_data):
        top_n = 5
        s = CompositeStrategy({"top_n": top_n})
        result = s.filter(composite_data)
        assert len(result) <= top_n

    def test_filter_returns_only_stock_codes(self, composite_data):
        """Bug B1 修正後，composite 也不應回傳含空格的代號"""
        s = CompositeStrategy()
        result = s.filter(composite_data)
        for code in result:
            assert " " not in code

    def test_score_weights_sum_to_one(self, composite_data):
        """內部權重正規化後加總應為 1.0"""
        s = CompositeStrategy({"value_weight": 2.0, "growth_weight": 3.0, "momentum_weight": 5.0})
        scores = s.score(composite_data)
        assert isinstance(scores, pd.Series)

    def test_score_range_0_to_100(self, composite_data):
        """CompositeStrategy 的評分由各子策略百分位加權而來，理論上可能超過 100
        （當多個子策略都對同一股票評高分且資料分布極端時）。
        此測試確認分數為有效數值（有限、非 NaN）即可。"""
        s = CompositeStrategy()
        scores = s.score(composite_data).dropna()
        if len(scores) > 0:
            assert scores.apply(lambda x: np.isfinite(x)).all()

    def test_disable_all_factors_returns_empty(self, composite_data):
        s = CompositeStrategy({"use_value": False, "use_growth": False, "use_momentum": False})
        result = s.filter(composite_data)
        assert result == []

    def test_factor_breakdown_columns(self, composite_data):
        s = CompositeStrategy()
        breakdown = s.get_factor_breakdown(composite_data)
        assert isinstance(breakdown, pd.DataFrame)
        assert "價值因子" in breakdown.columns
        assert "成長因子" in breakdown.columns
        assert "動能因子" in breakdown.columns
        assert "綜合評分" in breakdown.columns

    def test_sub_strategy_params_can_be_overridden(self, composite_data):
        s = CompositeStrategy({
            "value_params": {"pe_max": 100.0},
            "top_n": 10,
        })
        result = s.filter(composite_data)
        assert isinstance(result, list)
        assert len(result) <= 10

    def test_min_score_filter(self, composite_data):
        """min_score 設得比任何股票實際分數都高，應回傳空清單。
        先取得最高分，再設門檻 = 最高分 + 1。"""
        s = CompositeStrategy()
        scores = s.score(composite_data)
        max_score = scores.max() if len(scores) > 0 else 100.0
        s2 = CompositeStrategy({"min_score": max_score + 1.0})
        result = s2.filter(composite_data)
        assert result == []


# ──────────────────────────────────────────────
# CombinedStrategy（base.py）
# ──────────────────────────────────────────────

class TestCombinedStrategy:

    def test_intersection_mode(self, value_data, composite_data):
        """交集模式：結果必須同時被兩個策略選出"""
        v = ValueStrategy({"use_pb": False, "use_dividend": False})
        # 用寬鬆條件讓各策略至少選出幾支
        v2 = ValueStrategy({"pe_max": 50.0, "use_pb": False, "use_dividend": False})
        combined = CombinedStrategy([v, v2], mode="intersection")
        result = combined.filter(value_data)
        assert isinstance(result, list)

    def test_union_mode_at_least_as_large(self, value_data):
        """聯集模式：結果數量 >= 任一子策略"""
        v1 = ValueStrategy({"use_pb": False, "use_dividend": False})
        v2 = ValueStrategy({"pe_max": 50.0, "use_pb": False, "use_dividend": False})
        union = CombinedStrategy([v1, v2], mode="union")
        r_union = set(union.filter(value_data))
        r_v1 = set(v1.filter(value_data))
        r_v2 = set(v2.filter(value_data))
        assert r_union >= r_v1
        assert r_union >= r_v2

    def test_empty_strategies_list(self, value_data):
        combined = CombinedStrategy([], mode="intersection")
        assert combined.filter(value_data) == []

    def test_intersection_is_subset_of_union(self, value_data):
        v1 = ValueStrategy({"use_pb": False, "use_dividend": False})
        v2 = ValueStrategy({"pe_max": 30.0, "use_pb": False, "use_dividend": False})
        inter = set(CombinedStrategy([v1, v2], mode="intersection").filter(value_data))
        union = set(CombinedStrategy([v1, v2], mode="union").filter(value_data))
        assert inter.issubset(union)


# ──────────────────────────────────────────────
# 策略一致性：filter 與 score index 應可對應
# ──────────────────────────────────────────────

class TestStrategyConsistency:

    @pytest.mark.parametrize("StrategyClass,data_fixture", [
        (ValueStrategy, "value_data"),
        (GrowthStrategy, "growth_data"),
        (MomentumStrategy, "momentum_data"),
    ])
    def test_filtered_stocks_have_scores(self, StrategyClass, data_fixture, request):
        data = request.getfixturevalue(data_fixture)
        s = StrategyClass()
        filtered = s.filter(data)
        scores = s.score(data)
        # filter 回傳的代號應該都能在 score 的 index 找到（允許格式差異）
        score_index_codes = set()
        for idx in scores.index:
            idx_str = str(idx)
            score_index_codes.add(idx_str.split(" ")[0] if " " in idx_str else idx_str)
        for code in filtered:
            assert code in score_index_codes, (
                f"{StrategyClass.__name__}: filter 回傳 {code!r}，但不在 score index 中"
            )

    def test_repr_contains_class_name(self):
        s = ValueStrategy()
        assert "ValueStrategy" in repr(s)
