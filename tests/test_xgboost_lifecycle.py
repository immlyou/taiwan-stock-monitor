"""Execution accounting must preserve frozen picks and never fabricate fills."""
import numpy as np
import pandas as pd
import pytest

from core.xgboost_lifecycle import reconcile_study


def fixture():
    dates = pd.bdate_range("2025-01-01", periods=7)
    close = pd.DataFrame({"A": [100., 100., 101., 102., 110., 112., 113.]}, index=dates)
    volume = close * 0 + 10000
    study = {"model_version": "test", "methodology_version": "fixed", "assumptions": {
        "buy_cost_rate": 0., "sell_cost_rate": 0., "slippage_bps_each_side": 0.},
        "summary": {"periods_requested": 1, "complete_top_n_periods": 1, "mean_ic": 0.01},
        "periods": [{"date": str(dates[0])[:10], "entry_date": str(dates[1])[:10],
                     "exit_date": str(dates[4])[:10], "selected_stocks": ["A"]}]}
    return study, close, volume


def run(study, close, volume, events=()):
    return reconcile_study(study, close, volume, list(events))


def test_exact_quote_exit_costs_and_frozen_selection():
    study, close, volume = fixture()
    study["assumptions"].update(buy_cost_rate=.001, sell_cost_rate=.003, slippage_bps_each_side=10.)
    result = run(study, close, volume)
    row = result["periods"][0]["positions"][0]
    assert row["status"] == "closed_on_schedule"
    assert row["net_return"] == pytest.approx(110 * .999 * .997 / (100 * 1.001 * 1.001) - 1)
    assert result["periods"][0]["selected_stocks"] == ["A"]
    assert result["summary"]["settled_periods"] == 1


def test_no_entry_quote_is_cash_not_replacement_or_stock_win():
    study, close, volume = fixture()
    close.iloc[1, 0], volume.iloc[1, 0] = np.nan, 0
    row = run(study, close, volume)["periods"][0]
    assert row["positions"][0]["status"] == "unfilled_cash"
    assert row["positions"][0]["stock_return"] is None
    assert row["net_return"] == 0
    assert row["closed_trade_hit_rate"] is None


def test_missing_data_is_not_silently_cash_or_completed():
    study, close, volume = fixture()
    close.iloc[1, 0], volume.iloc[1, 0] = np.nan, np.nan
    result = run(study, close, volume)
    assert result["summary"]["accounted_periods"] == 0
    assert result["periods"][0]["net_return"] is None


def test_delayed_exit_applies_split_not_a_95_percent_loss():
    study, close, volume = fixture()
    close.iloc[4, 0], volume.iloc[4, 0] = np.nan, np.nan
    close.iloc[5, 0] = 5.
    events = [{"id": "split", "stock_id": "A", "type": "split", "date": str(close.index[5])[:10],
               "ratio": 22, "source_url": "https://www.twse.com.tw/example"}]
    row = run(study, close, volume, events)["periods"][0]["positions"][0]
    assert row["status"] == "closed_delayed"
    assert row["share_multiplier"] == 22
    assert row["net_return"] == pytest.approx(.1)
    assert row["exit_date"] == str(close.index[5])[:10]


def test_suspended_owned_position_stays_open_not_realized_or_zero():
    study, close, volume = fixture()
    close.iloc[3:, 0], volume.iloc[3:, 0] = np.nan, np.nan
    events = [{"id": "halt", "stock_id": "A", "type": "halt", "date": str(close.index[3])[:10],
               "source_url": "https://www.twse.com.tw/example"}]
    result = run(study, close, volume, events)
    row = result["periods"][0]
    assert result["summary"]["accounted_periods"] == 1
    assert result["summary"]["settled_periods"] == 0
    assert row["positions"][0]["status"] == "open_suspended"
    assert row["positions"][0]["net_return"] is None
    assert row["net_return"] is None
    assert row["marked_return"] == pytest.approx(.01)


def test_verified_cash_settlement_and_invalid_events():
    study, close, volume = fixture()
    close.iloc[3:, 0], volume.iloc[3:, 0] = np.nan, np.nan
    event = {"id": "settled", "stock_id": "A", "type": "cash_settlement", "date": str(close.index[5])[:10],
             "cash_per_share": 50., "source_url": "https://www.twse.com.tw/example"}
    row = run(study, close, volume, [event])["periods"][0]["positions"][0]
    assert row["status"] == "settled_cash"
    assert row["net_return"] == -.5
    with pytest.raises(ValueError):
        run(study, close, volume, [{**event, "source_url": ""}])


def test_dividend_applies_only_to_held_shares_without_mutating_input():
    from copy import deepcopy
    study, close, volume = fixture()
    original = deepcopy(study)
    event = {"id": "cash", "stock_id": "A", "type": "cash_dividend", "date": str(close.index[3])[:10],
             "cash_per_share": 2., "source_url": "https://www.twse.com.tw/example"}
    row = run(study, close, volume, [event])["periods"][0]["positions"][0]
    assert row["net_return"] == pytest.approx(.12)
    assert study == original


def test_halt_and_valid_quote_conflict_is_not_a_fill():
    study, close, volume = fixture()
    event = {"id": "halt", "stock_id": "A", "type": "halt", "date": str(close.index[1])[:10],
             "source_url": "https://www.twse.com.tw/example"}
    result = run(study, close, volume, [event])
    assert result["summary"]["accounted_periods"] == 0


def test_unconfirmed_unquoted_exit_is_unresolved_not_marked_complete():
    study, close, volume = fixture()
    close.iloc[4:, 0] = np.nan
    result = run(study, close, volume)
    assert result["summary"]["unresolved_periods"] == 1
    assert result["summary"]["settled_periods"] == 0


def test_stale_mark_after_split_and_dividend_does_not_create_value():
    study, close, volume = fixture()
    close.iloc[3:, 0], volume.iloc[3:, 0] = np.nan, np.nan
    base = {"stock_id": "A", "source_url": "https://www.twse.com.tw/example"}
    events = [{**base, "id": "halt", "type": "halt", "date": str(close.index[3])[:10]},
              {**base, "id": "split", "type": "split", "date": str(close.index[4])[:10], "ratio": 2},
              {**base, "id": "dividend", "type": "cash_dividend", "date": str(close.index[5])[:10], "cash_per_share": 2}]
    row = run(study, close, volume, events)["periods"][0]["positions"][0]
    assert row["net_return"] is None
    assert row["share_multiplier"] == 2
    assert row["cash_distributions"] == 4
    assert row["marked_return"] == pytest.approx(.01)


def test_bundled_24_period_ledger_preserves_all_480_original_picks():
    import json
    from core.xgboost_lifecycle import REPORT_PATH, load_lifecycle_report
    report = load_lifecycle_report()
    study = json.loads((REPORT_PATH.parent / "xgboost-frozen-study-2026-09-21.json").read_text())
    assert report["summary"]["accounted_periods"] == 24
    assert report["summary"]["settled_periods"] == 23
    assert report["summary"]["positions"] == 480
    assert report["original_summary"] == study["summary"]
    for original, reconciled in zip(study["periods"], report["periods"], strict=True):
        assert original["selected_stocks"] == reconciled["selected_stocks"]
        assert [p["stock_id"] for p in reconciled["positions"]] == original["selected_stocks"]
        assert sum(p["weight"] for p in reconciled["positions"]) == pytest.approx(1)
        if reconciled["settled"]:
            assert reconciled["net_return"] == pytest.approx(np.mean([p["net_return"] for p in reconciled["positions"]]))
        else:
            assert reconciled["net_return"] is None
    open_positions = [p for period in report["periods"] for p in period["positions"] if p["status"] == "open_suspended"]
    assert [p["stock_id"] for p in open_positions] == ["1589"]


def test_report_missing_and_wrong_version_fail_closed(monkeypatch, tmp_path):
    from core import xgboost_lifecycle as module
    path = tmp_path / "missing.json"
    monkeypatch.setattr(module, "REPORT_PATH", path)
    assert module.load_lifecycle_report()["status"] == "not_computed"
    path.write_text('{"schema_version":"unknown"}')
    with pytest.raises(ValueError):
        module.load_lifecycle_report()
