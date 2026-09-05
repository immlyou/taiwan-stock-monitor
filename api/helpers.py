"""API 層共用工具函式

從 api_server.py 抽出，供所有 router 共用：
- JSON 型別安全轉換
- data/ 目錄下的 JSON 檔案讀寫
- 股票代號 → 名稱 / 產業對照表
- cached_response 裝飾器（走 core/cache.py 的 backend）
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from functools import wraps
from typing import Dict

import numpy as np
import pandas as pd
from fastapi import HTTPException

from api.state import DATA_DIR, loader
from core.cache import get_cache, make_key
from core.user_storage import DEFAULT_USER_ID, user_data_path

logger = logging.getLogger(__name__)


# ─── JSON 型別轉換 ───────────────────────────────────────
def _safe_json(obj):
    """安全轉換 numpy/pandas 物件為 JSON 可序列化格式"""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return round(float(obj), 4) if not np.isnan(obj) else None
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    return obj


# ─── 個股數據存取 ───────────────────────────────────────
def _get_stock_latest(stock_id: str, days: int = 1):
    """取得個股最新數據"""
    close = loader.get("close")
    if stock_id not in close.columns:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    data = close[stock_id].dropna().tail(days)
    return data


# ─── data/ 目錄 JSON 檔案 I/O ────────────────────────────
def _user_json_path(filename: str, *, user_id: str = DEFAULT_USER_ID):
    return user_data_path(user_id, filename, DATA_DIR)


def _load_json_file(filename: str, default=None, *, user_id: str = DEFAULT_USER_ID):
    """安全讀取 data/ 目錄下的 JSON 檔案"""
    path = _user_json_path(filename, user_id=user_id)
    if default is None:
        default = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _save_json_file(filename: str, data, *, user_id: str = DEFAULT_USER_ID) -> None:
    """安全寫入 data/ 目錄下的 JSON 檔案（atomic write）"""
    from core.json_store import save_json_atomic

    save_json_atomic(_user_json_path(filename, user_id=user_id), data)


# ─── 股票對照表 ─────────────────────────────────────────
def _get_stock_name_map() -> Dict[str, str]:
    """取得股票代號 -> 名稱的對照表"""
    try:
        cats = loader.get("categories")
        if "stock_id" in cats.columns and "name" in cats.columns:
            return dict(zip(cats["stock_id"].astype(str), cats["name"].astype(str)))
        elif cats.index.name == "stock_id" or cats.index.dtype == object:
            if "name" in cats.columns:
                return dict(zip(cats.index.astype(str), cats["name"].astype(str)))
    except Exception:
        pass
    return {}


def _get_industry_map() -> Dict[str, str]:
    """取得股票代號 -> 產業的對照表"""
    try:
        cats = loader.get("categories")
        for col in ["category", "industry", "產業", "類別"]:
            if col in cats.columns:
                id_col = "stock_id" if "stock_id" in cats.columns else cats.index
                if isinstance(id_col, str):
                    return dict(zip(cats[id_col].astype(str), cats[col].astype(str)))
                else:
                    return dict(zip(id_col.astype(str), cats[col].astype(str)))
    except Exception:
        pass
    return {}


# ─── "default" 別名解析 ────────────────────────────────
# 前端（自選股、投資組合、雷達健檢）固定打 id="default"，但 default 並非
# 真實名稱。統一解析規則，讓這些端點不會對新使用者回 404：
#   - 請求的 id 存在 -> 用它
#   - id == "default" 且無同名 -> 退回第一個既有項目；完全沒有則回 None（呼叫端回空結構）
#   - 其他不存在的明確 id -> 回 (None, False)（呼叫端維持 404）
def resolve_default_id(items: Dict, requested: str):
    """回傳 (resolved_id, is_empty_default)。

    is_empty_default=True 代表「default 但完全沒有資料」→ 呼叫端應回空結構（200）。
    resolved_id=None 且 is_empty_default=False 代表「明確 id 不存在」→ 呼叫端回 404。
    """
    if requested in items:
        return requested, False
    if requested == "default":
        first = next(iter(items), None)
        return first, first is None
    return None, False


# ─── API 回應快取裝飾器 ────────────────────────────────
_singleflight_locks: dict[str, threading.Lock] = {}
_singleflight_locks_guard = threading.Lock()


def _singleflight_lock(cache_key: str) -> threading.Lock:
    """Return the process-local lock for one cache key."""
    with _singleflight_locks_guard:
        return _singleflight_locks.setdefault(cache_key, threading.Lock())


async def _acquire_without_blocking_loop(lock: threading.Lock) -> bool:
    """Acquire a cross-event-loop lock and report whether another caller led."""
    waited = False
    while not lock.acquire(blocking=False):
        waited = True
        await asyncio.sleep(0.01)
    return waited


def cached_response(ttl_seconds: int = 300, *, singleflight: bool = False):
    """快取 API 回應的裝飾器，預設 5 分鐘 TTL。

    Backend 在程序啟動時決定（Redis / in-memory，由 REDIS_URL 控制），
    失敗自動降級。快取 key 由 ``make_key(func.__name__, kwargs)`` 產生，已把端點
    函式收到的所有 kwargs（含路徑參數，FastAPI 以 kwargs 傳入）納入，因此路徑參數
    端點也可安全使用（如 ``/stock/{stock_id}/score-history``）；僅需避免用在回應
    依賴 header/cookie 等未進入函式 kwargs 之輸入的端點。

    ``singleflight=True`` 會讓同一進程、同一 cache key 的並行 cold miss 共用一次
    計算。背景預熱可在直接呼叫 decorated function 時傳入保留參數
    ``_refresh_cache=True`` 強制更新；它不會成為 FastAPI 的公開參數。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            force_refresh = bool(kwargs.pop("_refresh_cache", False))
            cache = get_cache()
            cache_key = make_key(func.__name__, kwargs)
            if not force_refresh:
                cached = cache.get(cache_key)
                if cached is not None:
                    return cached

            lock = _singleflight_lock(cache_key) if singleflight else None
            waited_for_leader = False
            if lock is not None:
                waited_for_leader = await _acquire_without_blocking_loop(lock)

            try:
                # A follower always re-checks after the leader finishes. A normal
                # leader also closes the race between the first GET and lock acquire.
                if waited_for_leader or not force_refresh:
                    cached = cache.get(cache_key)
                    if cached is not None:
                        return cached

                result = await func(*args, **kwargs)
                # 不要快取錯誤回應：許多端點把例外包成 {"error": ...} + HTTP 200，
                # 若快取下去，一次暫時性失敗會被釘住整個 TTL（曾導致舊 model 404 殘留）。
                if not (isinstance(result, dict) and result.get("error")):
                    cache.set(cache_key, result, ttl_seconds)
                return result
            finally:
                if lock is not None:
                    lock.release()
        return wrapper
    return decorator
