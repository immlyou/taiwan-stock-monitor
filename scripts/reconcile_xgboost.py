#!/usr/bin/env python3
"""Reconcile a frozen walk-forward manifest; never retrain or replace picks."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.backtest_xgboost import SnapshotLoader  # noqa: E402
from core.xgboost_lifecycle import reconcile_study  # noqa: E402
from core.json_store import save_json_atomic  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--snapshot-tar", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--events", type=Path, default=ROOT / "research/xgboost-corporate-actions.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-accounted", type=int, default=24)
    args = parser.parse_args()
    study_bytes, event_bytes = args.study.read_bytes(), args.events.read_bytes()
    study = json.loads(study_bytes)
    loader = SnapshotLoader(args.snapshot_tar, args.as_of)
    original = study.get("reproducibility", {}).get("data_manifest", {})
    for key in ("close", "volume"):
        if original.get(key, {}).get("sha256") != loader.manifest[key]["sha256"]:
            raise ValueError(f"Frozen study and snapshot mismatch: {key}")
    report = reconcile_study(study, loader.get("close"), loader.get("volume"), json.loads(event_bytes)["events"])
    report["reproducibility"] = {
        "study_sha256": hashlib.sha256(study_bytes).hexdigest(),
        "events_sha256": hashlib.sha256(event_bytes).hexdigest(),
        "data_manifest": loader.manifest,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                          ("core/xgboost_lifecycle.py", "scripts/reconcile_xgboost.py")},
    }
    save_json_atomic(args.out, report)
    print(json.dumps(report["summary"], indent=2))
    for period in report["periods"]:
        if not period["settled"]:
            print(period["date"], period["status"], [(p["stock_id"], p["status"]) for p in period["positions"] if p["net_return"] is None])
    if (report["summary"]["accounted_periods"] != args.require_accounted
            or report["summary"]["periods_requested"] != args.require_accounted):
        raise SystemExit("FAIL: requested accounting completeness not achieved; see report")
    print("PASS: accounting complete. Settled is a separate count; no profit-validity claim.")


if __name__ == "__main__":
    main()
