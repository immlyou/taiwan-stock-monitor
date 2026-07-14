"""DataLoader.get 併發下載鎖回歸測試（2026-07-15 P2a）。

背景：get() 的「檢查快取 miss → 下載 → 寫快取」是複合操作，DataCache 的 _rw_lock
只保護單次 get/set，不保護跨下載的臨界區。多執行緒（cache_warmer 背景緒 vs 請求緒，
或 market 端點 run_in_executor 卸載後的多請求緒）同時 miss 同一 key 會各自下載一次。

修法：per-key 下載鎖 + double-checked locking → 同一 key 併發 miss 只真的下載一次，
其餘執行緒等鎖後從快取取回。保護稀缺的 FinLab 額度。
"""
from __future__ import annotations

import threading
import time

import pandas as pd

import core.data_loader as dl
from core.data_loader import DataLoader


def _make_local_loader():
    """__new__ 建一個本地快取模式的 loader（繞過 __init__ 的環境偵測）。"""
    loader = DataLoader.__new__(DataLoader)
    loader._use_finlab_api = False
    loader._use_global_cache = False
    loader._cache = {}
    loader._download_locks = {}
    loader._download_locks_meta = threading.Lock()
    return loader


def test_concurrent_miss_downloads_once(monkeypatch):
    loader = _make_local_loader()

    calls = {"n": 0}
    call_lock = threading.Lock()

    def _slow_load(filename):
        with call_lock:
            calls["n"] += 1
        time.sleep(0.2)  # 放大競爭窗口，確保 8 條緒都先擠到 miss
        return pd.DataFrame({"2330": [1.0, 2.0]})

    monkeypatch.setattr(dl, "DATA_FILES", {"testkey": "testfile.pkl"})
    monkeypatch.setattr(loader, "_load_pickle", _slow_load)

    results = []
    res_lock = threading.Lock()

    def worker():
        df = loader.get("testkey")
        with res_lock:
            results.append(df)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 核心斷言：8 條緒同時 miss 同一 key，底層 load 只被呼叫一次
    assert calls["n"] == 1, f"併發 miss 應只下載一次，實際 {calls['n']} 次"
    assert len(results) == 8
    # 所有執行緒都拿到同一份快取物件（等鎖後走 double-check 命中快取）
    assert all(r is results[0] for r in results)


def test_different_keys_not_serialized(monkeypatch):
    """不同 key 用不同鎖，不應互相阻塞（各自下載一次）。"""
    loader = _make_local_loader()

    calls = {}
    call_lock = threading.Lock()

    def _load(filename):
        with call_lock:
            calls[filename] = calls.get(filename, 0) + 1
        return pd.DataFrame({"x": [1.0]})

    monkeypatch.setattr(dl, "DATA_FILES", {"a": "a.pkl", "b": "b.pkl"})
    monkeypatch.setattr(loader, "_load_pickle", _load)

    loader.get("a")
    loader.get("b")
    loader.get("a")  # 第二次 a → cache hit，不再下載

    assert calls == {"a.pkl": 1, "b.pkl": 1}
