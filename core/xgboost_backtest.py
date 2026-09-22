"""XGBoost 選股模型的 walk-forward 回測

目的：用「歷史上若照模型選股，實際結果如何」來量化它有沒有用，
而不是看 in-sample 的預測值。產出命中率(hit rate)與資訊係數(IC)。

避免 look-ahead bias 的關鍵
--------------------------
在每個訊號日 T，用 `_AsOfLoader` 截斷資料到 ≤ T。
IC 衡量 T → T+forward_days 的價格預測；交易情境則 T+1 收盤進場、
T+forward_days 收盤出場，扣除明列的費用與滑價假設。
這只能限制索引時序，不能證明上游歷史資料未被事後修訂。
（模型訓練時的目標雖是前向報酬，但那是 ≤T 已實現的部分，未實現的會被 NaN 濾掉。）

指標
----
- IC（Spearman 等級相關）：每期預測與實際前向報酬的橫截面等級相關。
  不以任意固定 IC 閾值宣稱模型有效；仍需不確定性、成本與資料品質驗證。
- IC IR：mean(IC) / std(IC)，衡量 IC 的穩定度。
- 命中率：Top-N 選股中「實際前向報酬 > 0」的比例；對照 base rate（全體候選為正的比例）。
- Top-N 平均報酬 vs 全體候選平均（等權）：超額 = Top-N − 全體。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from core.market_timing import as_of_frame

logger = logging.getLogger(__name__)

# 回測結果持久化位置（Railway Volume，跨 redeploy 保留；供 /strategy/ai-xgboost/backtest 讀取）
DEFAULT_RESULT_PATH = Path(__file__).parent.parent / "data" / "xgboost_backtest.json"
# 內建 seed（隨程式碼版控）：Volume 尚無有效結果時的 fallback，讓端點一上線就有資料。
# 放在 repo 根目錄而非 data/，因為 Railway 的 Volume 掛在 /app/data 會「遮蔽」image 內的 data/。
SEED_RESULT_PATH = Path(__file__).parent.parent / "xgboost_backtest_seed.json"
METHODOLOGY_VERSION = "wf-2-next-session-costs-fixed-selection"


class _AsOfLoader:
    """包裝 DataLoader：所有 get() 結果截斷到 as_of 日期（含），其餘行為透傳。

    讓模型把 as_of 當成「最新交易日」，只用該日（含）以前的資料，杜絕 look-ahead。
    """

    def __init__(self, loader: Any, as_of: pd.Timestamp):
        self._loader = loader
        self._as_of = as_of

    def get(self, key: str, *args, **kwargs):
        df = self._loader.get(key, *args, **kwargs)
        if df is None:
            return df
        return as_of_frame(df, self._as_of)

    def __getattr__(self, name):
        # 其他方法（get_stock_info 等）透傳給底層 loader
        return getattr(self._loader, name)


def _spearman_ic(pred: Dict[str, float], actual: Dict[str, float]) -> float:
    """預測報酬 vs 實際前向報酬的 Spearman 等級相關（橫截面 IC）。"""
    common = [s for s in pred if s in actual
              and pred[s] is not None and actual[s] is not None
              and np.isfinite(pred[s]) and np.isfinite(actual[s])]
    if len(common) < 5:
        return float("nan")
    p = pd.Series({s: pred[s] for s in common})
    a = pd.Series({s: actual[s] for s in common})
    ic = p.corr(a, method="spearman")
    return float(ic) if ic is not None and np.isfinite(ic) else float("nan")


def walk_forward_backtest(
    loader: Any,
    n_periods: int = 8,
    step_days: int = 20,
    top_n: int = 20,
    forward_days: int = 20,
    min_train_gap: int = 60,
    buy_cost_rate: float = 0.001425,
    sell_cost_rate: float = 0.004425,
    slippage_bps: float = 10.0,
) -> Dict[str, Any]:
    """對 XGBoostStockPicker 做 walk-forward 回測。

    Parameters
    ----------
    n_periods : 評估的再平衡期數（每期都要重訓模型，越多越慢）
    step_days : 相鄰再平衡日的間隔（交易日）
    top_n     : 命中率/報酬以前 N 名計算
    forward_days : 前向報酬視窗（與模型目標一致，預設 20）
    min_train_gap : 第一個再平衡日之前，除了 LOOKBACK 還要再留的緩衝交易日
    """
    from core.ai_models import XGBoostStockPicker

    if min(n_periods, step_days, top_n) < 1 or forward_days < 2 or min_train_gap < 0:
        raise ValueError("periods/step/top_n must be positive; forward_days >= 2")
    if not all(np.isfinite(v) and v >= 0 for v in (buy_cost_rate, sell_cost_rate, slippage_bps)):
        raise ValueError("costs must be finite and non-negative")
    if sell_cost_rate >= 1 or slippage_bps >= 10000:
        raise ValueError("costs must be below 100%")

    close = loader.get("close")
    if close is None or close.empty:
        raise RuntimeError("close 資料為空，無法回測")
    close = as_of_frame(close, close.index.max())
    dates = close.index
    picker = XGBoostStockPicker()
    picker.FORWARD_DAYS = forward_days
    lookback = getattr(picker, "LOOKBACK_DAYS", 252)

    last_eval_pos = len(dates) - 1 - forward_days       # T 後要有 forward_days 已實現
    first_pos = lookback + forward_days + min_train_gap  # T 前要有足夠訓練資料
    if last_eval_pos <= first_pos:
        raise RuntimeError(
            f"資料長度不足以回測（需 > {first_pos + forward_days} 個交易日，現有 {len(dates)}）"
        )

    positions = sorted(set(range(last_eval_pos, first_pos, -step_days)))[-n_periods:]

    periods: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for pos in positions:
        t_date = dates[pos]
        try:
            picks = picker.predict(_AsOfLoader(loader, t_date))
        except Exception as exc:  # noqa: BLE001 — 單期失敗不應中斷整個回測
            logger.warning("回測 %s 期預測失敗：%s", str(t_date)[:10], exc)
            skipped.append({"date": str(t_date)[:10], "reason": "prediction_failed"})
            continue

        pred = {p["stock_id"]: float(p["predicted_return"]) for p in picks
                if p.get("predicted_return") is not None and np.isfinite(p["predicted_return"])}
        # Freeze selection BEFORE examining future quote availability.
        top = list(pred)[:top_n]

        c_now = close.iloc[pos]
        c_fut = close.iloc[pos + forward_days]
        actual: Dict[str, float] = {}
        net_actual: Dict[str, float] = {}
        entry = close.iloc[pos + 1]
        slip = slippage_bps / 10000
        for sid in pred:
            try:
                pn, pf = float(c_now.get(sid)), float(c_fut.get(sid))
                if pn > 0 and pf > 0 and np.isfinite(pn) and np.isfinite(pf):
                    actual[sid] = pf / pn - 1.0
                    pe = float(entry.get(sid))
                    if pe > 0 and np.isfinite(pe):
                        net_actual[sid] = pf * (1 - slip) * (1 - sell_cost_rate) / (pe * (1 + slip) * (1 + buy_cost_rate)) - 1
            except Exception:
                pass
        if len(actual) < 10:
            skipped.append({"date": str(t_date)[:10], "reason": "insufficient_realized_outcomes"})
            continue

        ic = _spearman_ic(pred, actual)
        # Incomplete selected baskets stay unavailable; do not replace failed /
        # delisted picks with lower ranks or silently average only survivors.
        complete = bool(top) and all(s in net_actual for s in top)
        top_rets = [net_actual[s] for s in top] if complete else []
        all_rets = list(net_actual.values()) if len(net_actual) == len(pred) else []

        periods.append({
            "date": str(t_date)[:10],
            "entry_date": str(dates[pos + 1])[:10],
            "exit_date": str(dates[pos + forward_days])[:10],
            "n_candidates": len(pred),
            "outcome_coverage": len(net_actual) / len(pred) if pred else 0,
            "selected_stocks": top,
            "missing_selected": [s for s in top if s not in net_actual],
            "ic": round(ic, 4) if np.isfinite(ic) else None,
            "top_n_hit_rate": round(float(np.mean([1 if r > 0 else 0 for r in top_rets])), 4) if top_rets else None,
            "base_hit_rate": round(float(np.mean([1 if r > 0 else 0 for r in all_rets])), 4) if all_rets else None,
            "top_n_return": round(float(np.mean(top_rets)), 4) if top_rets else None,
            "all_avg_return": round(float(np.mean(all_rets)), 4) if all_rets else None,
            "excess_return": round(float(np.mean(top_rets) - np.mean(all_rets)), 4) if top_rets and all_rets else None,
        })

    if not periods:
        raise RuntimeError("沒有任何有效回測期，請放寬參數或確認資料")

    ics = [p["ic"] for p in periods if p["ic"] is not None]
    hits = [p["top_n_hit_rate"] for p in periods if p["top_n_hit_rate"] is not None]
    base_hits = [p["base_hit_rate"] for p in periods if p["base_hit_rate"] is not None]
    top_rets = [p["top_n_return"] for p in periods if p["top_n_return"] is not None]
    excess = [p["excess_return"] for p in periods if p["excess_return"] is not None]

    mean_ic = float(np.mean(ics)) if ics else float("nan")
    std_ic = float(np.std(ics)) if len(ics) > 1 else float("nan")

    summary = {
        "periods_evaluated": len(periods),
        "periods_requested": n_periods,
        "complete_top_n_periods": len(top_rets),
        "complete_benchmark_periods": len(base_hits),
        "forward_days": forward_days,
        "top_n": top_n,
        "date_range": f"{periods[0]['date']} ~ {periods[-1]['date']}",
        "mean_ic": round(mean_ic, 4) if np.isfinite(mean_ic) else None,
        "ic_ir": round(mean_ic / std_ic, 4) if std_ic and np.isfinite(std_ic) and std_ic > 0 else None,
        "ic_positive_ratio": round(float(np.mean([1 if i > 0 else 0 for i in ics])), 4) if ics else None,
        "mean_top_n_hit_rate": round(float(np.mean(hits)), 4) if hits else None,
        "mean_base_hit_rate": round(float(np.mean(base_hits)), 4) if base_hits else None,
        "mean_top_n_return": round(float(np.mean(top_rets)), 4) if top_rets else None,
        "mean_excess_return": round(float(np.mean(excess)), 4) if excess else None,
    }
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "model_version": XGBoostStockPicker.MODEL_VERSION,
        "validation_status": "research_only",
        "assumptions": {
            "signal": "after_T_close", "entry": "T_plus_1_close", "exit": f"T_plus_{forward_days}_close",
            "holding_sessions": forward_days - 1, "ic_target": "T_to_T_plus_forward_gross_return",
            "buy_cost_rate": buy_cost_rate, "sell_cost_rate": sell_cost_rate, "slippage_bps_each_side": slippage_bps,
            "costs_are_scenario_assumptions": True, "minimum_commission_modeled": False,
            "overlapping_periods": step_days < forward_days,
            "limitations": ["snapshot_revisions_not_point_in_time_verified", "raw_close_not_total_return",
                            "no_delisting_or_limit_liquidity_model", "period_means_not_portfolio_CAGR"],
        },
        "summary": summary, "periods": periods, "skipped_periods": skipped,
    }


# ── 結果持久化（供端點讀取）────────────────────────────────

def save_result(result: Dict[str, Any], path: Any = DEFAULT_RESULT_PATH) -> Dict[str, Any]:
    """存回測結果到 JSON（附上台北時間戳），回傳含 computed_at 的結果。"""
    from core.json_store import save_json_atomic
    from core.timeutils import now_taipei

    stamped = {**result, "computed_at": now_taipei().isoformat()}
    save_json_atomic(path, stamped)
    return stamped


def load_result(path: Any = DEFAULT_RESULT_PATH) -> Any:
    """讀取上次回測結果。

    先讀 Volume 的結果（path），無效/空/不存在時 fallback 到內建 seed；
    都沒有才回 None。Volume 上一旦有有效結果即優先（覆蓋 seed）。
    """
    for candidate in (Path(path), SEED_RESULT_PATH):
        try:
            if candidate.exists():
                with open(candidate, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("summary"), dict) and isinstance(data.get("periods"), list):
                    from core.ai_models import XGBoostStockPicker
                    current = (candidate != SEED_RESULT_PATH
                               and data.get("methodology_version") == METHODOLOGY_VERSION
                               and data.get("model_version") == XGBoostStockPicker.MODEL_VERSION)
                    return {**data, "source": "seed" if candidate == SEED_RESULT_PATH else "persisted",
                            "current_model_comparable": current,
                            "validation_status": "research_only" if current else "legacy_not_comparable"}
        except Exception:
            continue
    return None


# ── 前向追蹤：記錄當前選股供日後驗證 ────────────────────────

def record_live_xgboost_picks(loader: Any, top_n: int = 20, verify_days: int = 20) -> int:
    """把當前 XGBoost top-N 選股記入 prediction_tracker，到期後由驗證流程比對實際報酬。

    與歷史回測互補：這是「即時下注、未來驗證」的真實 track record。
    回傳實際記錄的筆數。
    """
    from core.ai_models import XGBoostStockPicker
    from core.prediction_tracker import get_tracker

    if verify_days < 1 or top_n < 1:
        raise ValueError("top_n and verify_days must be positive")
    picker = XGBoostStockPicker()
    picker.FORWARD_DAYS = verify_days
    picks = picker.predict(loader)[:top_n]
    close = loader.get("close")
    try:
        from core.intelligence import _latest_name_map
        name_map = _latest_name_map(loader)
    except Exception:
        name_map = {}

    stocks: List[Dict[str, Any]] = []
    for p in picks:
        sid = p["stock_id"]
        try:
            series = close[sid].dropna() if (close is not None and sid in close.columns) else None
            price = float(series.iloc[-1]) if series is not None and not series.empty else None
        except Exception:
            price = None
        if price is None:
            continue
        stocks.append({
            "stock_id": sid,
            "stock_name": name_map.get(sid, ""),
            "current_price": price,
            "expected_return": p.get("predicted_return"),
        })

    if not stocks:
        return 0
    tracker = get_tracker()
    signal_date = str(close.index[-1])[:10]
    recorded = {p.stock_id for p in tracker.predictions
                if p.source == "xgboost" and (p.strategy_params or {}).get("signal_date") == signal_date
                and (p.strategy_params or {}).get("model_version") == XGBoostStockPicker.MODEL_VERSION
                and p.verify_days == verify_days}
    stocks = [s for s in stocks if s["stock_id"] not in recorded]
    tracker.add_batch_stock_picks(
        stocks, verify_days=verify_days, source="xgboost",
        strategy_params={"top_n": top_n, "model_version": XGBoostStockPicker.MODEL_VERSION,
                         "horizon_unit": "trading_sessions", "signal_date": signal_date},
    )
    return len(stocks)
