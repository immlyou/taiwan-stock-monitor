"""
測試 core/cache.py

覆蓋:
- InMemoryCache get/set/expiry/clear
- 序列化（NaN / Infinity / numpy）
- 工廠函式 get_cache() 在 REDIS_URL 未設定時回退 InMemoryCache
- Redis 連線失敗時自動降級（mock）
- make_key 的鍵穩定性與順序無關
"""
from __future__ import annotations

import math
import time
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from core import cache as cache_mod
from core.cache import (
    InMemoryCache,
    RedisCache,
    get_cache,
    make_key,
    reset_cache_for_testing,
    _dumps,
    _loads,
)


@pytest.fixture(autouse=True)
def _reset_backend():
    """每個測試前後都重置 backend，避免互相污染"""
    reset_cache_for_testing()
    yield
    reset_cache_for_testing()


class TestInMemoryCache:
    def test_set_then_get(self):
        c = InMemoryCache()
        c.set("k", {"a": 1}, ttl_seconds=60)
        assert c.get("k") == {"a": 1}

    def test_miss_returns_none(self):
        c = InMemoryCache()
        assert c.get("nothing") is None

    def test_expiry(self):
        c = InMemoryCache()
        c.set("k", "v", ttl_seconds=1)
        assert c.get("k") == "v"
        # 時間快轉
        with patch("core.cache.time.time", return_value=time.time() + 10):
            assert c.get("k") is None

    def test_clear(self):
        c = InMemoryCache()
        c.set("a", 1, 60)
        c.set("b", 2, 60)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_name(self):
        assert InMemoryCache().name() == "memory"


class TestSerialization:
    def test_nan_becomes_null(self):
        raw = _dumps({"v": float("nan")})
        assert _loads(raw) == {"v": None}

    def test_infinity_becomes_null(self):
        raw = _dumps({"v": float("inf"), "w": float("-inf")})
        assert _loads(raw) == {"v": None, "w": None}

    def test_numpy_float_nan(self):
        raw = _dumps({"v": np.float64("nan")})
        assert _loads(raw) == {"v": None}

    def test_numpy_int(self):
        raw = _dumps({"v": np.int64(42)})
        assert _loads(raw) == {"v": 42}

    def test_numpy_array(self):
        raw = _dumps({"v": np.array([1, 2, 3])})
        assert _loads(raw) == {"v": [1, 2, 3]}

    def test_ascii_chinese(self):
        raw = _dumps({"名稱": "台積電"})
        # ensure_ascii=False → 中文不被 escape
        assert "台積電" in raw
        assert _loads(raw) == {"名稱": "台積電"}


class TestMakeKey:
    def test_order_independent(self):
        k1 = make_key("foo", {"a": 1, "b": 2})
        k2 = make_key("foo", {"b": 2, "a": 1})
        assert k1 == k2

    def test_different_args_different_key(self):
        k1 = make_key("foo", {"a": 1})
        k2 = make_key("foo", {"a": 2})
        assert k1 != k2

    def test_has_prefix(self):
        k = make_key("bar", {})
        assert k.startswith("stock-api:")

    def test_includes_func_name(self):
        k = make_key("my_func", {"x": 1})
        assert "my_func" in k


class TestGetCacheFactory:
    def test_no_redis_url_uses_inmemory(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        backend = get_cache()
        assert backend.name() == "memory"

    def test_empty_redis_url_uses_inmemory(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "   ")
        backend = get_cache()
        assert backend.name() == "memory"

    def test_singleton_within_session(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        assert get_cache() is get_cache()

    def test_redis_connection_failure_falls_back(self, monkeypatch):
        """REDIS_URL 有設但連線失敗 → 自動降級 in-memory"""
        monkeypatch.setenv("REDIS_URL", "redis://invalid-host-xyz:6379/0")

        with patch.object(cache_mod, "RedisCache") as mock_redis_cls:
            mock_redis_cls.side_effect = ConnectionError("cannot connect")
            backend = get_cache()
            assert backend.name() == "memory"


class TestRedisCacheMocked:
    """用 mock 確認 RedisCache 會把錯誤吞掉（API 不被 Redis 故障影響）"""

    def _make_with_mock_client(self, mock_client):
        rc = RedisCache.__new__(RedisCache)
        rc._client = mock_client
        return rc

    def test_get_returns_deserialized(self):
        client = MagicMock()
        client.get.return_value = '{"a": 1}'
        rc = self._make_with_mock_client(client)
        assert rc.get("k") == {"a": 1}

    def test_get_miss(self):
        client = MagicMock()
        client.get.return_value = None
        rc = self._make_with_mock_client(client)
        assert rc.get("k") is None

    def test_get_exception_returns_none(self):
        client = MagicMock()
        client.get.side_effect = RuntimeError("boom")
        rc = self._make_with_mock_client(client)
        assert rc.get("k") is None  # 不拋錯

    def test_set_serializes_and_sets_ttl(self):
        client = MagicMock()
        rc = self._make_with_mock_client(client)
        rc.set("k", {"v": 1}, ttl_seconds=60)
        client.set.assert_called_once()
        _, kwargs = client.set.call_args
        assert kwargs.get("ex") == 60

    def test_set_exception_swallowed(self):
        client = MagicMock()
        client.set.side_effect = RuntimeError("boom")
        rc = self._make_with_mock_client(client)
        # 不應拋錯
        rc.set("k", {"v": 1}, ttl_seconds=60)

    def test_set_with_nan_value(self):
        """確認 NaN 能被序列化（不拋 ValueError）"""
        client = MagicMock()
        rc = self._make_with_mock_client(client)
        rc.set("k", {"v": float("nan")}, ttl_seconds=60)
        client.set.assert_called_once()

    def test_clear_scans_with_prefix(self):
        client = MagicMock()
        client.scan_iter.return_value = iter(["stock-api:a", "stock-api:b"])
        rc = self._make_with_mock_client(client)
        rc.clear()
        # 只掃 stock-api: 前綴
        client.scan_iter.assert_called_once()
        args, kwargs = client.scan_iter.call_args
        assert kwargs.get("match", "").startswith("stock-api:")
        assert client.delete.call_count == 2

    def test_name(self):
        rc = self._make_with_mock_client(MagicMock())
        assert rc.name() == "redis"


class TestMaskUrl:
    def test_masks_password(self):
        from core.cache import _mask_url

        masked = _mask_url("redis://user:secret@host:6379/0")
        assert "secret" not in masked
        assert "host:6379/0" in masked

    def test_no_credentials_unchanged(self):
        from core.cache import _mask_url

        assert _mask_url("redis://host:6379/0") == "redis://host:6379/0"
