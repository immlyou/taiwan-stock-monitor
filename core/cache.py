"""
API 回應快取層

支援兩種 backend:
- InMemoryCache: 程序內 dict，適合本地開發與測試
- RedisCache:    Upstash / 任何 Redis，適合生產環境（重啟後仍保留快取）

自動切換邏輯:
- 未設定 REDIS_URL → InMemoryCache
- REDIS_URL 已設但連線失敗 → 降級為 InMemoryCache（log warning）
- 執行期 Redis 錯誤 → 該次請求 skip cache，不阻斷 API

序列化:
- 存值時 json.dumps，NaN/Inf → null，numpy 型別 → Python 原生
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

_KEY_PREFIX = "stock-api:"

# 快取版本維度：API 回應結構改變（新增/改欄位）時 bump，舊版 key 不再被命中
# （隨各自 TTL 自然過期），免去部署後手動 SCAN+DEL Redis。
# 預設用程式常數 _CACHE_VERSION；可用環境變數 CACHE_VERSION 覆寫（無需改碼）。
# 注意：bump 後該版所有快取會一次性 cold miss 重算（例如 XGBoost ~14s），屬預期。
_CACHE_VERSION_DEFAULT = "3"  # v3：清掉 v2 期間被快取的錯誤回應（舊 Claude model 404 殘留）
CACHE_VERSION = os.getenv("CACHE_VERSION", "").strip() or _CACHE_VERSION_DEFAULT


def _sanitize(obj: Any) -> Any:
    """遞迴地將 NaN / Infinity / numpy 型別轉為 JSON-safe 原生型別

    必須在 json.dumps 之前執行，因為 Python JSON encoder 對 float 直接
    處理，不會呼叫 default hook（只有未知型別才會）。
    """
    # 優先處理 numpy（在 isinstance float 檢查之前，因為 np.floating 會被 float() 化）
    try:
        import numpy as np

        if isinstance(obj, np.floating):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return [_sanitize(x) for x in obj.tolist()]
    except ImportError:
        pass

    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _dumps(value: Any) -> str:
    # allow_nan=False 讓殘留的 NaN/Inf（sanitize 漏網之魚）直接拋錯而非產生無效 JSON
    return json.dumps(_sanitize(value), ensure_ascii=False, allow_nan=False)


def _loads(raw: str) -> Any:
    return json.loads(raw)


class CacheBackend(Protocol):
    """統一快取介面"""

    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def clear(self) -> None: ...
    def name(self) -> str: ...


class InMemoryCache:
    """程序內 dict 實作（原 _api_cache 的等效實作）"""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._data:
            return None
        if time.time() >= self._expiry.get(key, 0):
            self._data.pop(key, None)
            self._expiry.pop(key, None)
            return None
        return self._data[key]

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._data[key] = value
        self._expiry[key] = time.time() + max(ttl_seconds, 1)

    def clear(self) -> None:
        self._data.clear()
        self._expiry.clear()

    def name(self) -> str:
        return "memory"


class RedisCache:
    """Redis 實作（Upstash / self-hosted 皆可）

    失敗策略：任何 Redis 錯誤 → 降級，該次請求視同 cache miss / skip set。
    不丟出錯誤，保護 API 可用性。
    """

    def __init__(self, url: str) -> None:
        import redis  # type: ignore

        # decode_responses=True 讓回傳是 str 而非 bytes
        # socket_timeout: 避免 Redis 慢導致 API latency
        self._client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            health_check_interval=30,
        )
        # 主動 ping 驗證連線（失敗時 __init__ 會拋錯，讓 factory 捕捉並降級）
        self._client.ping()

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return _loads(raw)
        except Exception as e:
            logger.warning("Redis GET failed (%s), treating as miss: %s", key, e)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            raw = _dumps(value)
            self._client.set(key, raw, ex=max(ttl_seconds, 1))
        except Exception as e:
            logger.warning("Redis SET failed (%s), skipping: %s", key, e)

    def clear(self) -> None:
        """清除 stock-api:* 前綴下的所有鍵（避免誤刪其他 app）"""
        try:
            for key in self._client.scan_iter(match=f"{_KEY_PREFIX}*", count=100):
                self._client.delete(key)
        except Exception as e:
            logger.warning("Redis clear failed: %s", e)

    def name(self) -> str:
        return "redis"


_backend: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """取得快取 backend，自動選擇 Redis 或 In-memory

    優先序：
    1. REDIS_URL 環境變數有值 → 嘗試連 Redis
    2. 連線失敗或未設定 → InMemoryCache
    """
    global _backend
    if _backend is not None:
        return _backend

    url = os.getenv("REDIS_URL", "").strip()
    if url:
        try:
            _backend = RedisCache(url)
            logger.info("API cache backend: Redis (%s)", _mask_url(url))
            return _backend
        except Exception as e:
            logger.warning(
                "Redis init failed, falling back to in-memory cache: %s", e
            )

    _backend = InMemoryCache()
    logger.info("API cache backend: in-memory")
    return _backend


def reset_cache_for_testing() -> None:
    """測試專用：重置全域 backend，下次 get_cache() 會重新挑選"""
    global _backend
    if _backend is not None:
        try:
            _backend.clear()
        except Exception:
            pass
    _backend = None


def make_key(func_name: str, kwargs: dict[str, Any]) -> str:
    """從函式名 + 參數組出快取鍵（含版本維度）"""
    # 排序確保 kwargs 順序不影響 key
    parts = sorted((str(k), str(v)) for k, v in kwargs.items())
    # 版本放在 prefix 之後：clear() 的 "stock-api:*" 仍涵蓋所有版本的 key。
    return f"{_KEY_PREFIX}v{CACHE_VERSION}:{func_name}:{parts}"


def _mask_url(url: str) -> str:
    """避免 log 洩漏 password"""
    try:
        if "@" in url:
            head, tail = url.rsplit("@", 1)
            scheme_and_creds = head.split("://", 1)
            if len(scheme_and_creds) == 2:
                return f"{scheme_and_creds[0]}://***@{tail}"
        return url
    except Exception:
        return "<masked>"
