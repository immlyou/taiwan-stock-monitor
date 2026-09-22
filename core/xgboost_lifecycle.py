"""Reconcile frozen selections without changing model scores or inventing trades.

This is an execution scenario, NOT a new IC estimate or a continuous portfolio.
Accounted (including disclosed open positions) and settled are distinct gates.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.market_timing import as_of_frame

VERSION = "lifecycle-1-frozen-picks"
REPORT_PATH = Path(__file__).resolve().parent.parent / "research/xgboost-lifecycle-2026-09-21.json"


def load_lifecycle_report():
    """Bundled, dated research artifact; never silently replace live model results."""
    if not REPORT_PATH.exists():
        return {"status": "not_computed", "note": "尚未產生交易生命週期研究報告"}
    result = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if result.get("schema_version") != VERSION:
        raise ValueError("Unsupported lifecycle report version")
    return {**result, "status": "ok"}


def _valid(value):
    return value is not None and np.isfinite(value) and value > 0


def _halt(events, date):
    return next((e for e in events if e["type"] == "halt" and e["date"] <= date
                 and (not e.get("end_date") or date <= e["end_date"])), None)


def _validate_events(events):
    ids = set()
    for event in events:
        if (not event.get("id") or event["id"] in ids or not event.get("stock_id")
                or not event.get("source_url", "").startswith("https://")):
            raise ValueError("Corporate actions require unique IDs, stock IDs and evidence URLs")
        ids.add(event["id"])
        if pd.Timestamp(event["date"]).strftime("%Y-%m-%d") != event["date"]:
            raise ValueError("Event dates must be ISO calendar dates")
        if event.get("end_date") and event["end_date"] < event["date"]:
            raise ValueError("Halt end precedes start")
        kind = event["type"]
        if kind not in {"split", "halt", "cash_settlement", "cash_dividend"}:
            raise ValueError("Unsupported corporate action")
        if kind == "split" and not _valid(event.get("ratio")):
            raise ValueError("Split ratio must be finite and positive")
        if kind in {"cash_settlement", "cash_dividend"}:
            amount = event.get("cash_per_share")
            if amount is None or not np.isfinite(amount) or amount < 0:
                raise ValueError("Cash amount must be finite and non-negative")


def _position(sid, period, close, volume, events, costs):
    entry_date, target_date = period["entry_date"], period["exit_date"]
    prices = close[sid] if sid in close else pd.Series(np.nan, index=close.index)
    pe = prices.get(pd.Timestamp(entry_date), np.nan)
    ve = volume[sid].get(pd.Timestamp(entry_date), np.nan) if sid in volume else np.nan
    actions = sorted((e for e in events if e["stock_id"] == sid), key=lambda e: e["date"])
    row = {"stock_id": sid, "scheduled_entry": entry_date, "scheduled_exit": target_date,
           "entry_date": None, "exit_date": None, "entry_price": None, "exit_price": None,
           "net_return": None, "stock_return": None, "marked_return": None,
           "share_multiplier": 1., "cash_distributions": 0., "events": [],
           "weight": 1 / len(period["selected_stocks"])}
    if _valid(pe) and _halt(actions, entry_date):
        row.update(status="unresolved_data", reason="quote_conflicts_with_verified_halt")
        return row
    if not _valid(pe):
        halt = _halt(actions, entry_date)
        # No daily regular-session close plus <1 lot observed turnover is a
        # no-fill under THIS daily-close scenario, not a zero stock return.
        if halt or (np.isfinite(ve) and 0 <= ve < 1000):
            row.update(status="unfilled_cash", net_return=0., marked_return=0.,
                       reason="verified_halt" if halt else "no_regular_close_low_or_zero_volume")
            if halt:
                row["events"] = [halt["id"]]
        else:
            row.update(status="unresolved_data", reason="missing_entry_quote_without_no_fill_evidence")
        return row

    buy, sell, slip = costs
    basis = float(pe) * (1 + slip) * (1 + buy)
    row.update(entry_date=entry_date, entry_price=float(pe))
    future = prices.loc[target_date:]
    future = future.loc[np.isfinite(future) & (future > 0)]
    exit_date = str(future.index[0])[:10] if len(future) else None
    if exit_date and _halt(actions, exit_date):
        row.update(status="unresolved_data", reason="quote_conflicts_with_verified_halt")
        return row
    cutoff = exit_date or str(close.index[-1])[:10]
    shares, cash, settlement = 1., 0., None
    for event in actions:
        if not entry_date < event["date"] <= cutoff:
            continue
        if event["type"] == "split":
            shares *= event["ratio"]
        elif event["type"] == "cash_dividend":
            cash += shares * event["cash_per_share"]
        elif event["type"] == "cash_settlement":
            cash += shares * event["cash_per_share"]
            settlement = event
        row["events"].append(event["id"])
        if settlement:
            break
    row.update(share_multiplier=shares, cash_distributions=cash)
    if settlement:
        row.update(status="settled_cash", exit_date=settlement["date"],
                   net_return=cash / basis - 1, stock_return=cash / float(pe) - 1)
    elif exit_date:
        pf = float(future.iloc[0])
        row.update(status="closed_on_schedule" if exit_date == target_date else "closed_delayed",
                   exit_date=exit_date, exit_price=pf,
                   delay_sessions=int(((close.index > pd.Timestamp(target_date)) &
                                       (close.index <= pd.Timestamp(exit_date))).sum()),
                   stock_return=(shares * pf + cash) / float(pe) - 1,
                   net_return=(shares * pf * (1 - slip) * (1 - sell) + cash) / basis - 1)
    else:
        halt = _halt(actions, str(close.index[-1])[:10])
        row.update(status="open_suspended" if halt else "unresolved_data",
                   reason="verified_halt_no_exit_by_cutoff" if halt else "missing_exit_without_verified_event")
        mark = prices.loc[entry_date:].dropna()
        mark = mark.loc[np.isfinite(mark) & (mark > 0)]
        mark_date = str(mark.index[-1])[:10]
        # Quotes before a split are on the old share basis: normalize the mark,
        # do not multiply stale pre-split prices by post-split share counts.
        mark_price = float(mark.iloc[-1])
        for event in actions:
            if mark_date < event["date"] <= cutoff:
                if event["type"] == "split":
                    mark_price /= event["ratio"]
                elif event["type"] == "cash_dividend":
                    # A pre-ex-date stale quote still contains the distributed
                    # cash. Strip it before adding the cash ledger separately.
                    mark_price = max(0., mark_price - event["cash_per_share"])
        row.update(mark_date=mark_date, mark_price=mark_price,
                   marked_return=(shares * mark_price + cash) / basis - 1,
                   mark_is_stale=True)
        if halt and halt["id"] not in row["events"]:
            row["events"].append(halt["id"])
    if row["net_return"] is not None:
        row["marked_return"] = row["net_return"]
    return row


def reconcile_study(study, close, volume, events):
    """Preserve every selection and retain unknown outcomes as unknown."""
    _validate_events(events)
    close = as_of_frame(close, close.index.max())
    if close.empty:
        raise ValueError("Empty close data")
    assumptions = study["assumptions"]
    costs = (assumptions["buy_cost_rate"], assumptions["sell_cost_rate"], assumptions["slippage_bps_each_side"] / 10000)
    if not all(np.isfinite(c) and 0 <= c < 1 for c in costs):
        raise ValueError("Invalid cost assumptions")
    periods = []
    for period in study["periods"]:
        picks = period["selected_stocks"]
        if not picks or len(picks) != len(set(picks)):
            raise ValueError("Frozen picks must be unique and nonempty")
        if not period["date"] < period["entry_date"] <= period["exit_date"] <= str(close.index[-1])[:10]:
            raise ValueError("Invalid or not-yet-mature period")
        if any(pd.Timestamp(period[k]) not in close.index for k in ("date", "entry_date", "exit_date")):
            raise ValueError("Period dates must be market sessions in the snapshot")
        rows = [_position(s, period, close, volume, events, costs) for s in picks]
        accounted = all(r["status"] != "unresolved_data" for r in rows)
        settled = all(r["net_return"] is not None for r in rows)
        trades = [r["net_return"] for r in rows if r["net_return"] is not None and r["status"] != "unfilled_cash"]
        periods.append({"date": period["date"], "entry_date": period["entry_date"], "exit_date": period["exit_date"],
                        "selected_stocks": list(picks), "positions": rows, "accounted": accounted, "settled": settled,
                        "status": "settled" if settled else "open_position" if accounted else "unresolved_data",
                        "net_return": float(np.mean([r["net_return"] for r in rows])) if settled else None,
                        "marked_return": float(np.mean([r["marked_return"] for r in rows])) if accounted else None,
                        "closed_trade_hit_rate": float(np.mean(np.array(trades) > 0)) if trades else None})
    counts = Counter(r["status"] for p in periods for r in p["positions"])
    return {"schema_version": VERSION, "source": "frozen_research_snapshot", "data_as_of": str(close.index[-1])[:10],
            "model_version": study["model_version"], "validation_status": "research_only",
            "original_summary": deepcopy(study["summary"]), "events": deepcopy(events),
            "summary": {"periods_requested": study["summary"]["periods_requested"], "periods_evaluated": len(periods),
                        "accounted_periods": sum(p["accounted"] for p in periods),
                        "settled_periods": sum(p["settled"] for p in periods),
                        "open_periods": sum(p["status"] == "open_position" for p in periods),
                        "unresolved_periods": sum(not p["accounted"] for p in periods),
                        "positions": sum(counts.values()), "position_status_counts": dict(counts)},
            "assumptions": {**deepcopy(assumptions), "entry_policy": "scheduled_close_or_keep_cash_no_replacement",
                            "exit_policy": "first_valid_close_on_or_after_target_or_verified_cash_settlement",
                            "open_policy": "disclose_stale_mark_not_realized", "corporate_actions": "explicit_evidence_ledger_only",
                            "limitations": ["not_a_continuous_portfolio_or_CAGR", "delayed_exits_change_holding_horizon",
                                            "daily_close_does_not_guarantee_fill_or_capacity", "corporate_action_ledger_not_exhaustive",
                                            "not_total_return_without_complete_dividend_events", "original_IC_not_recomputed"]},
            "periods": periods}
