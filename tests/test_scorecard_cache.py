"""calculate_score_table 全市場 memoize + smart-alerts 去重測試

驗證：
- 全市場（stock_ids=None, date=None）評分表會被 memoize 到 DataCache，
  第二次呼叫回傳同一物件（不重算）→ 這是 smart-preview 由 ~23s 變快的關鍵。
- 指定 stock_ids 的子集呼叫不走全市場快取。
- DataCache.clear() 後會重新計算（/refresh、reset_all_caches 能強制刷新）。
- evaluate_smart_alerts 仍正常產出。
"""
import pandas as pd
import pytest

from core.data_loader import DataCache
from core.stock_score import calculate_score_table
from core.intelligence import evaluate_smart_alerts


@pytest.fixture(autouse=True)
def _clear_cache():
    DataCache().clear()
    yield
    DataCache().clear()


def _scorecard_keys():
    return [k for k in DataCache().get_stats().get("cached_keys", []) if k.startswith("_scorecard_")]


def test_full_market_scorecard_is_memoized(mock_loader):
    first = calculate_score_table(mock_loader)
    assert not first.empty
    keys = _scorecard_keys()
    assert len(keys) == 1, f"應有一個 _scorecard_ 快取鍵，實際: {keys}"

    second = calculate_score_table(mock_loader)
    # 命中快取 → 回傳同一物件（未重算）
    assert second is first


def test_clear_forces_recompute(mock_loader):
    first = calculate_score_table(mock_loader)
    DataCache().clear()
    assert _scorecard_keys() == []
    second = calculate_score_table(mock_loader)
    assert second is not first  # 重新計算後是新物件
    assert not second.empty


def test_subset_call_not_cached(mock_loader):
    cols = list(mock_loader.get("close").columns)[:2]
    calculate_score_table(mock_loader, stock_ids=cols)
    # 指定子集不應建立全市場 _scorecard_ 快取
    assert _scorecard_keys() == []


def test_scorecard_cache_caps_at_30(mock_loader):
    # 評分表 memo 改為「按日期快取、保留最近 30 份」（供 score-history 近 20 日共用）。
    # 塞 35 個假的舊日期表，再觸發一次計算（cache miss → set 當日 → 修剪），應 cap ≤ 30。
    for i in range(35):
        DataCache().set(f"_scorecard_2000{i:02d}01", pd.DataFrame({"x": [1]}))
    calculate_score_table(mock_loader)  # 當日 key 不在假表中 → miss → set + 修剪
    keys = _scorecard_keys()
    assert len(keys) <= 30, f"應 cap 到 30，實際 {len(keys)}"
    # 最舊的假表應被刪、最新的（含當日）應保留
    assert "_scorecard_20000001" not in keys


def test_recent_scorecard_not_pruned(mock_loader):
    # 少量（<30）時不應被刪：塞一個歷史日期表，算當日後兩者都在
    DataCache().set("_scorecard_20250101", pd.DataFrame({"x": [1]}))
    calculate_score_table(mock_loader)
    keys = _scorecard_keys()
    assert "_scorecard_20250101" in keys, "未達上限時舊表不應被刪"
    assert len(keys) == 2


def test_evaluate_smart_alerts_still_works(mock_loader):
    # 傳明確 stock_ids 走子集路徑，避免 get_active_stocks() 自建真實 loader
    # （venv 無 finlab/pickle）。重點是去重後仍正常產出。
    cols = list(mock_loader.get("close").columns)
    result = evaluate_smart_alerts(mock_loader, stock_ids=cols, top_n=5)
    assert "alerts" in result and "total" in result
    assert isinstance(result["alerts"], list)
