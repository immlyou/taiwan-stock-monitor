"""排程器與通知節流測試

涵蓋：
- NotificationThrottle.allow 冷卻邏輯（含跨實例的檔案持久化）
- NotificationManager.send 的 dedup_key 節流
- scheduler_enabled 的環境開關
- start_scheduler 在停用 / 啟用下的行為
- get_scheduler_status 內容
"""
import importlib

import pytest

from core.notification import NotificationThrottle, NotificationManager
import core.scheduler as scheduler


# ──────────────────────────────────────────────
# NotificationThrottle
# ──────────────────────────────────────────────

def test_throttle_first_call_allowed(tmp_path):
    th = NotificationThrottle(path=tmp_path / "t.json")
    assert th.allow("k1", cooldown_sec=60, now=1000.0) is True


def test_throttle_within_cooldown_blocked(tmp_path):
    th = NotificationThrottle(path=tmp_path / "t.json")
    assert th.allow("k1", cooldown_sec=60, now=1000.0) is True
    # 30 秒後仍在冷卻期內 → 擋下
    assert th.allow("k1", cooldown_sec=60, now=1030.0) is False


def test_throttle_after_cooldown_allowed(tmp_path):
    th = NotificationThrottle(path=tmp_path / "t.json")
    assert th.allow("k1", cooldown_sec=60, now=1000.0) is True
    # 超過冷卻期 → 放行
    assert th.allow("k1", cooldown_sec=60, now=1061.0) is True


def test_throttle_independent_keys(tmp_path):
    th = NotificationThrottle(path=tmp_path / "t.json")
    assert th.allow("a", cooldown_sec=60, now=1000.0) is True
    assert th.allow("b", cooldown_sec=60, now=1000.0) is True  # 不同 key 互不影響


def test_throttle_zero_cooldown_never_blocks(tmp_path):
    th = NotificationThrottle(path=tmp_path / "t.json")
    assert th.allow("k", cooldown_sec=0, now=1000.0) is True
    assert th.allow("k", cooldown_sec=0, now=1000.0) is True


def test_throttle_persists_across_instances(tmp_path):
    path = tmp_path / "t.json"
    assert NotificationThrottle(path=path).allow("k", cooldown_sec=60, now=1000.0) is True
    # 新實例（模擬 redeploy 後重啟）讀同一檔，仍記得冷卻
    assert NotificationThrottle(path=path).allow("k", cooldown_sec=60, now=1010.0) is False


def test_throttle_corrupt_file_recovers(tmp_path):
    path = tmp_path / "t.json"
    path.write_text("{ not json", encoding="utf-8")
    th = NotificationThrottle(path=path)
    # 壞檔不應炸；視為空狀態並放行
    assert th.allow("k", cooldown_sec=60, now=1000.0) is True


# ──────────────────────────────────────────────
# NotificationManager.send 節流（無已註冊頻道時不送，但節流路徑仍生效）
# ──────────────────────────────────────────────

def test_manager_send_dedup_skips_second(tmp_path, monkeypatch):
    # 把全域節流器指向暫存檔，避免汙染 data/
    th = NotificationThrottle(path=tmp_path / "t.json")
    monkeypatch.setattr("core.notification._throttle", th)

    mgr = NotificationManager()
    # 無頻道註冊時 send 回傳空 dict；重點是第二次因節流被擋（同樣回 {}）
    first = mgr.send("t", "m", dedup_key="dk", cooldown_sec=3600)
    second = mgr.send("t", "m", dedup_key="dk", cooldown_sec=3600)
    assert first == {}
    assert second == {}
    # 第三個不同 key 不受影響（仍會嘗試送出 → 空頻道下為 {}）
    assert mgr.send("t", "m", dedup_key="dk2", cooldown_sec=3600) == {}


# ──────────────────────────────────────────────
# scheduler_enabled 環境開關
# ──────────────────────────────────────────────

@pytest.mark.parametrize("val,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("false", False), ("no", False), ("off", False),
])
def test_scheduler_enabled_explicit(monkeypatch, val, expected):
    monkeypatch.setenv("ENABLE_SCHEDULER", val)
    assert scheduler.scheduler_enabled() is expected


def test_scheduler_enabled_default_local(monkeypatch):
    monkeypatch.delenv("ENABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("api.deps.IS_CLOUD", False, raising=False)
    assert scheduler.scheduler_enabled() is False


# ──────────────────────────────────────────────
# start_scheduler / status
# ──────────────────────────────────────────────

def test_start_scheduler_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("ENABLE_SCHEDULER", "0")
    scheduler.shutdown_scheduler()  # 確保乾淨起點
    assert scheduler.start_scheduler() is None
    status = scheduler.get_scheduler_status()
    assert status["enabled"] is False
    assert status["running"] is False


def test_start_scheduler_live_registers_job(monkeypatch):
    pytest.importorskip("apscheduler")
    monkeypatch.setenv("ENABLE_SCHEDULER", "1")
    scheduler.shutdown_scheduler()
    try:
        sched = scheduler.start_scheduler()
        assert sched is not None
        status = scheduler.get_scheduler_status()
        assert status["enabled"] is True
        assert status["running"] is True
        job_ids = {j["id"] for j in status["jobs"]}
        assert "alert_check" in job_ids
        # 重複呼叫回傳同一實例（不重複註冊）
        assert scheduler.start_scheduler() is sched
    finally:
        scheduler.shutdown_scheduler()
        assert scheduler.get_scheduler_status()["running"] is False
