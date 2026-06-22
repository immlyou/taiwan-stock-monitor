#!/usr/bin/env python3
"""跑 XGBoost 選股的 walk-forward 回測，輸出命中率與 IC。

用法：
    python scripts/backtest_xgboost.py --periods 8 --step 20 --top-n 20
結果同時印到 stdout 並存到 reports/xgboost_backtest.json。
"""
import argparse
import json
import sys
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


def main() -> None:
    ap = argparse.ArgumentParser(description="XGBoost 選股 walk-forward 回測")
    ap.add_argument("--periods", type=int, default=8, help="評估期數（每期重訓，越多越慢）")
    ap.add_argument("--step", type=int, default=20, help="相鄰再平衡日間隔（交易日）")
    ap.add_argument("--top-n", type=int, default=20, help="命中率/報酬取前 N 名")
    ap.add_argument("--forward", type=int, default=20, help="前向報酬視窗（交易日）")
    ap.add_argument("--out", default=str(ROOT / "reports" / "xgboost_backtest.json"))
    args = ap.parse_args()

    print(f"載入資料並回測（periods={args.periods}, step={args.step}, top_n={args.top_n}, forward={args.forward}）…")
    loader = get_loader()
    res = walk_forward_backtest(
        loader,
        n_periods=args.periods,
        step_days=args.step,
        top_n=args.top_n,
        forward_days=args.forward,
    )

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
