"""Regression tests for model semantics, market calendars and independent formulas."""
import numpy as np
import pandas as pd
import pytest

from core import indicators
from core.stock_score import _percentile_score, calculate_score_table
from core.backtest.metrics import calculate_sharpe_ratio, calculate_sortino_ratio


class Loader:
    def __init__(self, **frames):
        self.frames = frames

    def get(self, key):
        return self.frames.get(key, pd.DataFrame())


def test_rsi_wilder_seed_and_one_sided_markets():
    # First 3 moves: +2, -1, +2 -> gains=4/3, losses=1/3 -> RSI=80.
    # Next -1: gains=8/9, losses=5/9 -> RSI=800/13.
    prices = pd.Series([10., 12., 11., 13., 12.])
    result = indicators.rsi(prices, 3)
    assert result.iloc[:3].isna().all()
    np.testing.assert_allclose(result.iloc[3:], [80., 800 / 13])
    for values, expected in [(np.arange(20.) + 1, 100.), (20 - np.arange(20.), 0.), (np.ones(20), 0.)]:
        assert indicators.rsi(pd.Series(values), 14).iloc[-1] == expected


def test_rsi_missing_session_requires_new_warmup():
    result = indicators.rsi(pd.Series([1., 2., 3., 4., np.nan, 6., 7., 8., 9.]), 3)
    assert result.iloc[4:8].isna().all()
    assert result.iloc[8] == 100


def test_weekly_bars_are_monday_to_friday_not_tuesday_to_monday():
    prices = pd.Series(range(1, 7), index=pd.bdate_range("2026-09-14", periods=6))
    bars = indicators.resample_ohlcv(prices, prices, prices, prices, timeframe="W")
    assert bars["open"].tolist() == [1, 6]
    assert bars["close"].tolist() == [5, 6]
    assert bars["close"].index[0] == pd.Timestamp("2026-09-18")


def test_atr_uses_wilder_recursion_not_rolling_average():
    close = pd.Series([10., 12., 11., 15., 14.])
    result = indicators.atr(close + 1, close - 1, close, 3)
    # TR after first day: 3, 2, 5, 2; initial ATR=10/3, next=(20/3+2)/3.
    assert result.iloc[:3].isna().all()
    np.testing.assert_allclose(result.iloc[3:], [10 / 3, 26 / 9])


def test_mfi_handles_no_negative_flow_and_flat_market():
    close = pd.Series(np.arange(20.) + 10)
    assert indicators.mfi(close, close, close, close * 0 + 1, 14).iloc[-1] == 100
    flat = close * 0 + 10
    assert indicators.mfi(flat, flat, flat, flat, 14).iloc[-1] == 0


def test_psar_preserves_missing_quotes_and_restarts_after_a_gap():
    high = pd.DataFrame({"A": [np.nan, 11., 12., np.nan, 15., 16.], "B": [np.nan] * 6})
    result = indicators.psar(high, high - 2)
    assert result["B"].isna().all()
    assert result["A"].iloc[[0, 3]].isna().all()
    assert result["A"].iloc[[1, 2, 4, 5]].notna().all()
    assert result["A"].iloc[4] == 13
    assert indicators.psar(high.iloc[:0], high.iloc[:0]).empty


def test_percentile_directions_have_symmetric_endpoints():
    values = pd.Series([1., 2., 3., 4.])
    np.testing.assert_allclose(_percentile_score(values, higher_is_better=False), [100, 75, 50, 25])


def test_missing_quality_is_not_a_perfect_quality_score():
    close = pd.DataFrame({"A": np.arange(150.) + 10}, index=pd.bdate_range("2025-01-01", periods=150))
    table = calculate_score_table(Loader(close=close), stock_ids=["A"])
    assert pd.isna(table.loc["A", "quality"])


def test_subset_score_keeps_market_reference_population():
    dates = pd.bdate_range("2025-01-01", periods=150)
    close = pd.DataFrame({"A": np.arange(150.) + 10, "B": np.arange(150.) + 100}, index=dates)
    loader = Loader(close=close, pe_ratio=pd.DataFrame({"A": [10.], "B": [20.]}, index=dates[-1:]))
    full = calculate_score_table(loader)
    subset = calculate_score_table(loader, stock_ids=["A"])
    assert subset.loc["A", "value"] == full.loc["A", "value"]


def test_sharpe_and_sortino_use_period_excess_returns():
    moves = np.array([.10, -.05, .02, -.05])
    nav = pd.Series(np.r_[100., 100 * np.cumprod(1 + moves)], index=pd.bdate_range("2025-01-01", periods=5))
    expected_sharpe = moves.mean() / moves.std(ddof=1) * np.sqrt(252)
    expected_sortino = moves.mean() / np.sqrt(np.mean(np.minimum(moves, 0) ** 2)) * np.sqrt(252)
    assert calculate_sharpe_ratio(nav, 0) == pytest.approx(expected_sharpe)
    assert calculate_sortino_ratio(nav, 0) == pytest.approx(expected_sortino)


def test_constant_loss_sortino_is_negative_not_positive_infinity():
    nav = pd.Series([100., 90., 81., 72.9], index=pd.bdate_range("2025-01-01", periods=4))
    assert calculate_sortino_ratio(nav, 0) == pytest.approx(-np.sqrt(252))


def test_adx_matches_independent_talib_reference():
    # Golden values generated with TA-Lib C / Python wrapper 0.8.1 (period=3).
    # No optional TA-Lib dependency is needed to run CI.
    close = pd.Series([10., 12., 11., 13., 12., 14., 11., 12., 14., 13., 15., 14.])
    high = close + np.array([1, 2, 1, 3, 1, 2, 1, 1, 3, 2, 1, 2])
    low = close - 1
    adx, plus_di, minus_di = indicators.adx(high, low, close, 3)
    assert adx.iloc[:5].isna().all()
    np.testing.assert_allclose(adx.iloc[5:], [65.96283206019838, 44.585315660764536, 35.83657722251661,
                                           43.67518284004265, 40.48234645069684, 42.573191494859394, 33.02563550216566])
    assert plus_di.iloc[-1] == pytest.approx(26.651992918321447)
    assert minus_di.iloc[-1] == pytest.approx(20.134403028321397)
    assert indicators.mfi(high, low, close, pd.Series(np.arange(12.) + 100), 3).iloc[-1] == pytest.approx(35.14876091741815)


def test_score_cache_invalidates_same_day_input_revision():
    dates = pd.bdate_range("2025-01-01", periods=150)
    close = pd.DataFrame({"A": np.arange(150.) + 10, "B": np.arange(150.) + 100}, index=dates)
    loader = Loader(close=close, pe_ratio=pd.DataFrame({"A": [10.], "B": [20.]}, index=dates[-1:]))
    first = calculate_score_table(loader)
    loader.frames["pe_ratio"].loc[dates[-1], "A"] = 30.
    second = calculate_score_table(loader)
    assert first.loc["A", "value"] != second.loc["A", "value"]


def test_backtest_callback_cannot_see_execution_day_or_future():
    from core.backtest.engine import BacktestEngine
    dates = pd.bdate_range("2025-01-01", periods=5)
    close = pd.DataFrame({"A": [100., 101., 102., 103., 104.]}, index=dates)
    seen = []

    def strategy(data, date):
        assert data["close"].index.max() == date
        seen.append(date)
        return ["A"]

    result = BacktestEngine().run(strategy, {"close": close}, rebalance_freq="D")
    assert seen[0] == dates[0]
    assert result.trades.iloc[0]["entry_date"] == dates[1]
    assert result.portfolio_values.iloc[0] == result.config["initial_capital"]


def test_backtest_missing_quote_keeps_mark_and_partial_sales_reconcile():
    from core.backtest.engine import BacktestEngine
    engine = BacktestEngine(initial_capital=10000)
    date = pd.Timestamp("2025-01-01")
    engine._buy("A", date, 100., 5000.)
    engine._record_portfolio_value(date, pd.Series({"A": 110.}))
    engine._record_portfolio_value(date + pd.Timedelta(days=1), pd.Series({"A": np.nan}))
    assert engine.portfolio_history[-1]["value"] == engine.portfolio_history[-2]["value"]
    engine._partial_sell("A", date + pd.Timedelta(days=2), 110., 20)
    engine._sell("A", date + pd.Timedelta(days=3), 105.)
    assert len(engine.trades) == 2
    assert sum(t.pnl for t in engine.trades) == pytest.approx(engine.cash - engine.initial_capital)


def test_open_positions_do_not_count_as_losing_trades():
    from core.backtest.metrics import calculate_metrics
    nav = pd.Series([100., 110.], index=pd.bdate_range("2025-01-01", periods=2))
    trades = pd.DataFrame({"exit_date": [pd.Timestamp("2025-01-02"), None], "return": [10., 0.], "pnl": [10., 0.]})
    assert calculate_metrics(nav, trades).win_rate == 100
    assert calculate_metrics(nav, trades).total_trades == 1


def test_asof_rejects_unknown_time_semantics_and_sorts_before_slicing():
    from core.xgboost_backtest import _AsOfLoader
    with pytest.raises(ValueError, match="DatetimeIndex"):
        _AsOfLoader(Loader(close=pd.DataFrame({"A": [1.]}, index=["2025-M01"])), pd.Timestamp("2025-01-01")).get("close")
    data = pd.DataFrame({"A": [3., 1., 2.]}, index=pd.to_datetime(["2025-01-03", "2025-01-01", "2025-01-02"]))
    result = _AsOfLoader(Loader(close=data), pd.Timestamp("2025-01-02")).get("close")
    assert result["A"].tolist() == [1., 2.]


def test_xgb_keeps_zero_features_and_common_calendar():
    from core.ai_models import XGBoostStockPicker
    picker = XGBoostStockPicker()
    dates = pd.bdate_range("2024-01-01", periods=332)
    close = pd.DataFrame({"A": np.full(332, 100.)}, index=dates)
    close.iloc[10, 0] = np.nan
    features, _ = picker._compute_stock_features("A", close, {"volume": close * 0 + 1000})
    assert features is not None  # RSI/MACD/returns of zero are valid observations.
    assert features.index.equals(dates)
    assert pd.isna(features.iloc[-1]["pe_ratio"])  # missing != zero
    assert features.iloc[-1]["ret20"] == 0
    close.iloc[-1, 0] = np.nan
    assert picker._compute_stock_features("A", close, {"volume": close}) == (None, None)


def test_lstm_fallback_is_disclosed_and_stale_stock_is_rejected(monkeypatch):
    from core import ai_models
    monkeypatch.setattr(ai_models, "HAS_TORCH", False)
    close = pd.DataFrame({"A": np.arange(40.) + 100}, index=pd.bdate_range("2025-01-01", periods=40))
    result = ai_models.LSTMTrendPredictor().predict("A", Loader(close=close))
    assert result["model_used"] == "ewma"
    assert result["score_kind"] == "heuristic_not_probability"
    assert result["data_as_of"] == "2025-02-25"
    close.iloc[-1, 0] = np.nan
    with pytest.raises(ValueError, match="最新交易日"):
        ai_models.LSTMTrendPredictor().predict("A", Loader(close=close))


def test_walkforward_fixed_selection_costs_and_model_horizon(monkeypatch):
    from core import ai_models
    from core.xgboost_backtest import walk_forward_backtest
    dates = pd.bdate_range("2024-01-01", periods=100)
    close = pd.DataFrame({str(i): np.linspace(100, 120 + i, 100) for i in range(12)}, index=dates)
    horizons = []

    class Picker:
        LOOKBACK_DAYS = 20
        MODEL_VERSION = "fixture"

        def predict(self, loader):
            horizons.append(self.FORWARD_DAYS)
            assert loader.get("close").index[-1] == dates[-6]
            return [{"stock_id": str(i), "predicted_return": float(12-i)} for i in range(12)]

    monkeypatch.setattr(ai_models, "XGBoostStockPicker", Picker)
    args = dict(n_periods=1, top_n=2, forward_days=5, min_train_gap=0)
    clean = walk_forward_backtest(Loader(close=close), **args)
    period = clean["periods"][0]
    assert horizons == [5]
    assert period["entry_date"] == str(dates[-5])[:10]
    expected = np.mean([close[str(i)].iloc[-1] * .999 * .995575 / (close[str(i)].iloc[-5] * 1.001 * 1.001425) - 1 for i in range(2)])
    assert period["top_n_return"] == round(expected, 4)
    close.iloc[-1, 0] = np.nan
    incomplete = walk_forward_backtest(Loader(close=close), **args)["periods"][0]
    assert incomplete["selected_stocks"] == ["0", "1"]
    assert incomplete["missing_selected"] == ["0"]
    assert incomplete["top_n_return"] is None


def test_old_backtest_seed_is_not_current_model_evidence(tmp_path):
    from core.xgboost_backtest import load_result
    result = load_result(tmp_path / "absent.json")
    assert result["source"] == "seed"
    assert result["current_model_comparable"] is False
    assert result["validation_status"] == "legacy_not_comparable"


def test_live_model_verification_uses_exact_market_session_and_source(monkeypatch):
    from datetime import datetime
    from core import prediction_tracker as module
    tracker = module.PredictionTracker.__new__(module.PredictionTracker)
    tracker.predictions, tracker.verification_log = [], []
    monkeypatch.setattr(tracker, "_save_data", lambda: None)
    monkeypatch.setattr(module, "_now", lambda: datetime(2026, 9, 22, 17))
    monkeypatch.setattr("core.timeutils.today_taipei", lambda: datetime(2026, 9, 22).date())
    params = {"horizon_unit": "trading_sessions", "signal_date": "2026-09-14", "model_version": "v2"}
    record = tracker.add_stock_pick_prediction("A", "A", 100, verify_days=3, source="xgboost", strategy_params=params)
    record.created_at = "2026-09-14 17:00:00"
    record.expire_date = "2026-09-17"
    dates = pd.to_datetime(["2026-09-14", "2026-09-15", "2026-09-18", "2026-09-21", "2026-09-22"])
    prices = pd.DataFrame({"A": [100., 101., 102., 103., 90.]}, index=dates)
    tracker.verify_predictions(prices.iloc[:3])
    assert record.status == "pending"  # calendar expiry must not expire the model target
    tracker.verify_predictions(prices)
    assert record.status == "success"
    assert record.verified_price == 103  # third actual market session, not latest 90
    assert record.expire_date == "2026-09-21"
    tracker.add_stock_pick_prediction("A", "A", 100, source="other", strategy_params=params)
    tracker.add_stock_pick_prediction("A", "A", 100, source="xgboost", strategy_params={"model_version": "old"})
    stats = tracker.get_statistics(source="xgboost", model_version="v2")
    assert stats["total"] == 1
    assert stats["success_rate"] == 100


def test_lstm_training_is_repeatable_without_changing_rng():
    from core import ai_models
    if not ai_models.HAS_TORCH:
        pytest.skip("optional PyTorch dependency unavailable")
    prices = 100 + np.sin(np.arange(90.) / 3) + np.arange(90.) * .1
    volumes = np.arange(90.) + 1000
    before = ai_models.torch.random.get_rng_state().clone()
    first = ai_models._predict_torch(prices, volumes)
    second = ai_models._predict_torch(prices, volumes)
    assert first == second
    assert ai_models.torch.equal(before, ai_models.torch.random.get_rng_state())


def test_advisor_does_not_invent_return_from_percentile_score(monkeypatch):
    from core import advisor
    table = pd.DataFrame({"stock_id": ["A"], "total_score": [99.], "latest_price": [100.], "rating": ["A"]})
    monkeypatch.setattr(advisor, "calculate_score_table", lambda loader: table)
    result = advisor.analyze_portfolio(None, holdings=[{"stock_id": "A", "shares": 100, "cost_price": 100}], target_roi=1)
    assert result["feasibility"]["estimated_annual_return"] is None
    assert result["feasibility"]["verdict"] == "尚無法評估"


def test_risk_downside_uses_threshold_and_all_observations():
    from core.risk import RiskAnalyzer
    returns = pd.Series([.04, .01, -.02])
    assert RiskAnalyzer().calculate_downside_volatility(returns, .02, annualize=False) == pytest.approx(np.sqrt((.01**2 + .04**2) / 3))


def test_minimum_commission_can_still_buy_one_share():
    from core.backtest.engine import BacktestEngine
    engine = BacktestEngine(initial_capital=125)
    engine._buy("A", pd.Timestamp("2025-01-01"), 100, 200)
    assert engine.positions["A"]["shares"] == 1
    assert engine.cash == 5


def test_real_xgboost_training_can_coexist_with_optional_torch():
    """Subprocess catches native crashes without taking down the pytest runner."""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-c", """
import numpy as np
from core.ai_models import XGBoostStockPicker, HAS_TORCH, _predict_torch
rng = np.random.default_rng(42)
if HAS_TORCH:
    prices = 100 + np.sin(np.arange(90.) / 3) + np.arange(90.) * .1
    assert len(_predict_torch(prices, np.arange(90.) + 1000)) == 5
model, scaler, _ = XGBoostStockPicker(n_estimators=2)._train(rng.normal(size=(30, 14)), rng.normal(size=30))
assert np.isfinite(model.predict(scaler.transform(np.ones((2, 14))))).all()
print('fit-ok')
"""], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "fit-ok" in result.stdout
