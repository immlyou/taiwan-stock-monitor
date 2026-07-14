"""GET /ready 就緒探針合約測試。

涵蓋：
- close 快取為空（或無資料）→ 503 / warming_up
- close 快取有資料 → 200 / ready
- wait 參數會被 clamp 到上限（傳入超大值不會真的睡很久）

策略：直接操作 DataCache 單例塞入／清除小 DataFrame，模擬背景預熱前後的
記憶體快取狀態；只讀記憶體、不觸發任何下載，與 /ready 實作同規則。
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ready_client(monkeypatch):
    """提供 TestClient，並確保每個測試前 close 快取為已知狀態。"""
    import api.deps
    from api_server import app
    from core.data_loader import DataCache

    # /ready 無 auth，但保險起見強制關閉，避免上一個測試殘留 API_KEY。
    monkeypatch.setattr(api.deps, "API_KEY", "", raising=False)

    cache = DataCache()
    cache.clear_key("close")  # 測試前先清空，從 warming_up 狀態起跑

    with TestClient(app) as client:
        yield client, cache

    cache.clear_key("close")  # 測試後清理，避免污染其他測試


def _make_close() -> pd.DataFrame:
    """建立一個非空的小型 close DataFrame。"""
    dates = pd.date_range("2024-01-01", periods=3, freq="B")
    return pd.DataFrame(
        {"2330": [100.0, 101.0, 102.0], "2317": [50.0, 51.0, 52.0]},
        index=dates,
    )


def test_ready_returns_503_when_close_cache_empty(ready_client):
    """close 快取為空 → 503 / warming_up。"""
    client, cache = ready_client
    cache.clear_key("close")

    resp = client.get("/ready")

    assert resp.status_code == 503
    assert resp.json()["status"] == "warming_up"


def test_ready_returns_503_when_close_is_empty_dataframe(ready_client):
    """close 為空 DataFrame（非 None 但 .empty）→ 仍視為未就緒 → 503。"""
    client, cache = ready_client
    cache.set("close", pd.DataFrame())

    resp = client.get("/ready")

    assert resp.status_code == 503
    assert resp.json()["status"] == "warming_up"


def test_ready_returns_200_when_close_cache_present(ready_client):
    """close 快取有資料 → 200 / ready。"""
    client, cache = ready_client
    cache.set("close", _make_close())

    resp = client.get("/ready")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_ready_does_not_trigger_download(ready_client, monkeypatch):
    """/ready 只讀記憶體快取，絕不呼叫 loader.get() 觸發下載。"""
    client, cache = ready_client
    cache.clear_key("close")

    from api import state as api_state

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("/ready 不應觸發 loader.get() 下載")

    monkeypatch.setattr(api_state.loader, "get", _boom, raising=False)

    resp = client.get("/ready")

    # 即使 loader.get 會炸，/ready 也不該呼叫它，所以正常回 503。
    assert resp.status_code == 503
    assert resp.json()["status"] == "warming_up"


def test_ready_wait_is_clamped(ready_client, monkeypatch):
    """傳入超大 wait 值時，輪詢上限被 clamp，且不會真的睡很久。

    用 monkeypatch 掉 asyncio.sleep 計次，確認輪詢次數受 _READY_MAX_WAIT_SECONDS
    與 _READY_POLL_INTERVAL 共同 clamp，而非依使用者傳入的超大值。
    （ready 輪詢用 await asyncio.sleep，不是 time.sleep——後者會凍結單 worker 的
    事件迴圈，見 api/routers/system.py 內註解。）
    """
    client, cache = ready_client
    cache.clear_key("close")

    import api.routers.system as system_mod

    # 用一個假時鐘：sleep 不真的睡，而是推進 monotonic，讓 deadline 迴圈
    # 仍會結束、且不依賴真實時間（測試快又穩定）。
    clock = {"t": 0.0}
    sleep_calls = {"count": 0}

    def _fake_monotonic():
        return clock["t"]

    async def _fake_async_sleep(seconds):  # noqa: ANN001
        sleep_calls["count"] += 1
        clock["t"] += seconds

    monkeypatch.setattr(system_mod.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(system_mod.asyncio, "sleep", _fake_async_sleep)

    # 傳入遠大於上限的 wait；clamp 後最多 ceil(MAX/INTERVAL) 次輪詢。
    resp = client.get("/ready", params={"wait": 999999})

    assert resp.status_code == 503
    assert resp.json()["status"] == "warming_up"

    max_iters = int(system_mod._READY_MAX_WAIT_SECONDS / system_mod._READY_POLL_INTERVAL) + 2
    assert sleep_calls["count"] <= max_iters


def test_ready_negative_wait_rejected(ready_client):
    """wait 為負數時，因 Query(ge=0.0) 驗證 → 422，不會進入 handler。"""
    client, _cache = ready_client

    resp = client.get("/ready", params={"wait": -5})

    assert resp.status_code == 422
