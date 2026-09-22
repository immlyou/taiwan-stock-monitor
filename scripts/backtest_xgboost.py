#!/usr/bin/env python3
"""跑 XGBoost 選股的 walk-forward 回測，輸出命中率與 IC。

用法：
    python scripts/backtest_xgboost.py --periods 8 --step 20 --top-n 20
結果同時印到 stdout 並存到 reports/xgboost_backtest.json。
"""
import argparse
import json
import sys
import hashlib
import importlib.metadata
import pickle
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from core.data_loader import get_loader  # noqa: E402
from core.xgboost_backtest import walk_forward_backtest  # noqa: E402


class SnapshotLoader:
    """Read ONLY the user's trusted snapshot; never fetch network data or extract files.

    Pickle is executable: do not use this option for untrusted downloaded archives.
    """
    KEYS = {"close", "volume", "pe_ratio", "pb_ratio", "dividend_yield", "revenue_yoy", "revenue_mom", "foreign_investors"}

    def __init__(self, archive: str, as_of: str | None = None):
        import pandas as pd
        from core.market_timing import as_of_frame
        self.frames = {}
        self.manifest = {}
        with tarfile.open(archive, "r:gz") as source:
            for key in sorted(self.KEYS):
                member = source.getmember(f"data/finlab_cache/{key}.pkl")
                if not member.isfile():
                    raise ValueError(f"Invalid snapshot member: {key}")
                content = source.extractfile(member).read()
                frame = pickle.loads(content)
                frame = as_of_frame(frame, pd.Timestamp(as_of) if as_of else frame.index.max())
                self.frames[key] = frame
                self.manifest[key] = {"sha256": hashlib.sha256(content).hexdigest(), "rows": len(frame),
                                      "columns": len(frame.columns), "as_of": str(frame.index.max())[:10]}

    def get(self, key):
        return self.frames[key]


def main() -> None:
    ap = argparse.ArgumentParser(description="XGBoost 選股 walk-forward 回測")
    ap.add_argument("--periods", type=int, default=8, help="評估期數（每期重訓，越多越慢）")
    ap.add_argument("--step", type=int, default=20, help="相鄰再平衡日間隔（交易日）")
    ap.add_argument("--top-n", type=int, default=20, help="命中率/報酬取前 N 名")
    ap.add_argument("--forward", type=int, default=20, help="前向報酬視窗（交易日）")
    ap.add_argument("--snapshot-tar", help="本機可信任的 data/finlab_cache/*.pkl 備份；不連網")
    ap.add_argument("--as-of", help="快照截止日期 YYYY-MM-DD（搭配 --snapshot-tar）")
    ap.add_argument("--slippage-bps", type=float, default=10.0, help="每邊滑價情境（bps，不是實測）")
    ap.add_argument("--buy-cost-rate", type=float, default=0.001425)
    ap.add_argument("--sell-cost-rate", type=float, default=0.004425)
    ap.add_argument("--out", default=str(ROOT / "reports" / "xgboost_backtest.json"))
    args = ap.parse_args()

    print(f"載入資料並回測（periods={args.periods}, step={args.step}, top_n={args.top_n}, forward={args.forward}）…")
    if args.as_of and not args.snapshot_tar:
        ap.error("--as-of requires --snapshot-tar")
    loader = SnapshotLoader(args.snapshot_tar, args.as_of) if args.snapshot_tar else get_loader()
    res = walk_forward_backtest(
        loader,
        n_periods=args.periods,
        step_days=args.step,
        top_n=args.top_n,
        forward_days=args.forward,
        buy_cost_rate=args.buy_cost_rate,
        sell_cost_rate=args.sell_cost_rate,
        slippage_bps=args.slippage_bps,
    )
    res["reproducibility"] = {
        "data_source": "trusted_local_snapshot" if args.snapshot_tar else "live_loader",
        "data_manifest": getattr(loader, "manifest", None),
        "parameters": {k: v for k, v in vars(args).items() if k not in {"snapshot_tar", "out"}},
        "packages": {name: importlib.metadata.version(name) for name in ("pandas", "numpy", "xgboost", "scikit-learn")},
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                          ("core/ai_models.py", "core/indicators.py", "core/xgboost_backtest.py", "core/market_timing.py")},
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 各期 ===")
    for p in res["periods"]:
        print(f"  {p['date']}  IC={p['ic']}  TopN命中={p['top_n_hit_rate']}  "
              f"TopN報酬={p['top_n_return']}  全體均={p['all_avg_return']}  超額={p['excess_return']}")
    print("\n=== 摘要 ===")
    for k, v in res["summary"].items():
        print(f"  {k}: {v}")
    print(f"\n已存：{out}")


if __name__ == "__main__":
    main()
