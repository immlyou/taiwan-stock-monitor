"""FinLab 熔斷器 + Volume 持久化快取測試

涵蓋：
- _reset_finlab_counters_if_new_day 跨日重置（額度午夜重置）
- 熔斷器：同日額度超限 → _load_from_finlab 直接短路 raise（不碰網路）
- 磁碟快取 roundtrip / TTL 過期 / ignore_ttl stale
- get() 在額度超限時供應磁碟舊快取（stale fallback）
- clear_finlab_disk_cache 失效
"""
import datetime
import os
import time

import pandas as pd
import pytest

import core.data_loader as dl
from core.data_loader import DataLoader, FinLabQuotaExceededError
from core.timeutils import today_taipei


@pytest.fixture
def cloud_loader(tmp_path, monkeypatch):
    """雲端模式 loader，磁碟快取隔離到 tmp_path。"""
    monkeypatch.setattr(DataLoader, "_FINLAB_DISK_CACHE_DIR", tmp_path)
    loader = DataLoader.__new__(DataLoader)
    loader._use_finlab_api = True
    loader._use_global_cache = False
    loader._cache = {}
    # 每測重置模組級熔斷狀態
    dl._finlab_quota_exceeded = False
    dl._finlab_usage_mb = 0.0
    dl._finlab_counter_date = today_taipei()
    return loader


@pytest.fixture
def df():
    return pd.DataFrame({"2330": [1.0, 2.0], "2317": [3.0, 4.0]})


# ── 熔斷器 ──────────────────────────────────────────────

def test_breaker_open_short_circuits(cloud_loader):
    dl._finlab_quota_exceeded = True
    dl._finlab_counter_date = today_taipei()
    with pytest.raises(FinLabQuotaExceededError):
        cloud_loader._load_from_finlab("close")  # 應在 init_finlab/網路前就 raise


def test_breaker_resets_on_new_day():
    dl._finlab_counter_date = today_taipei() - datetime.timedelta(days=1)
    dl._finlab_quota_exceeded = True
    dl._finlab_usage_mb = 4999.0
    dl._reset_finlab_counters_if_new_day()
    assert dl._finlab_quota_exceeded is False
    assert dl._finlab_usage_mb == 0.0
    assert dl._finlab_counter_date == today_taipei()


def test_breaker_same_day_no_reset():
    dl._finlab_counter_date = today_taipei()
    dl._finlab_quota_exceeded = True
    dl._finlab_usage_mb = 100.0
    dl._reset_finlab_counters_if_new_day()
    assert dl._finlab_quota_exceeded is True  # 同日不重置
    assert dl._finlab_usage_mb == 100.0


# ── 磁碟持久化快取 ──────────────────────────────────────

def test_disk_cache_roundtrip(cloud_loader, df):
    cloud_loader._save_finlab_disk_cache("close", df)
    got = cloud_loader._load_finlab_disk_cache("close")
    assert got is not None and got.equals(df)


def test_disk_cache_ttl_expiry(cloud_loader, df, monkeypatch):
    monkeypatch.setattr(dl, "FINLAB_CACHE_TTL", 1)
    cloud_loader._save_finlab_disk_cache("close", df)
    path = cloud_loader._finlab_disk_path("close")
    os.utime(path, (time.time() - 10, time.time() - 10))  # 10 秒前 → 過 TTL
    assert cloud_loader._load_finlab_disk_cache("close") is None
    # ignore_ttl 仍可取得（stale）
    assert cloud_loader._load_finlab_disk_cache("close", ignore_ttl=True) is not None


def test_disk_cache_missing_returns_none(cloud_loader):
    assert cloud_loader._load_finlab_disk_cache("nonexistent") is None


def test_get_serves_stale_disk_on_quota(cloud_loader, df, monkeypatch):
    """記憶體 miss + 磁碟過期 + 下載觸發額度超限 → 供應 stale 磁碟快取。"""
    monkeypatch.setattr(dl, "FINLAB_CACHE_TTL", 86400)
    cloud_loader._save_finlab_disk_cache("close", df)
    path = cloud_loader._finlab_disk_path("close")
    os.utime(path, (time.time() - 10 ** 7, time.time() - 10 ** 7))  # 遠超 TTL

    def boom(_k):
        raise FinLabQuotaExceededError("quota")

    monkeypatch.setattr(cloud_loader, "_load_from_finlab", boom)
    cloud_loader._cache.clear()
    res = cloud_loader.get("close")
    assert res.equals(df)


def test_get_reraises_quota_without_disk(cloud_loader, monkeypatch):
    """無任何磁碟快取時，額度超限應往上拋（無 stale 可供）。"""
    def boom(_k):
        raise FinLabQuotaExceededError("quota")

    monkeypatch.setattr(cloud_loader, "_load_from_finlab", boom)
    cloud_loader._cache.clear()
    with pytest.raises(FinLabQuotaExceededError):
        cloud_loader.get("close")


def test_clear_disk_cache(cloud_loader, df):
    cloud_loader._save_finlab_disk_cache("close", df)
    cloud_loader._save_finlab_disk_cache("volume", df)
    cloud_loader.clear_finlab_disk_cache(["close"])
    assert cloud_loader._load_finlab_disk_cache("close", ignore_ttl=True) is None
    assert cloud_loader._load_finlab_disk_cache("volume", ignore_ttl=True) is not None
    cloud_loader.clear_finlab_disk_cache()  # 全清
    assert cloud_loader._load_finlab_disk_cache("volume", ignore_ttl=True) is None


def test_get_uses_fresh_disk_before_finlab(cloud_loader, df, monkeypatch):
    """記憶體 miss 但磁碟新鮮 → 直接讀磁碟，不呼叫 FinLab。"""
    monkeypatch.setattr(dl, "FINLAB_CACHE_TTL", 86400)
    cloud_loader._save_finlab_disk_cache("close", df)

    def should_not_call(_k):
        raise AssertionError("不應呼叫 FinLab")

    monkeypatch.setattr(cloud_loader, "_load_from_finlab", should_not_call)
    cloud_loader._cache.clear()
    res = cloud_loader.get("close")
    assert res.equals(df)
