"""API 層共用工具函式

從 api_server.py 抽出，供所有 router 共用：
- JSON 型別安全轉換
- data/ 目錄下的 JSON 檔案讀寫
- 股票代號 → 名稱 / 產業對照表
- cached_response 裝飾器（走 core/cache.py 的 backend）
"""
from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any, Dict

import numpy as np
import pandas as pd
from fastapi import HTTPException

from api.state import DATA_DIR, loader
from core.cache import get_cache, make_key

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
def _load_json_file(filename: str, default=None):
    """安全讀取 data/ 目錄下的 JSON 檔案"""
    path = DATA_DIR / filename
    if default is None:
        default = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _save_json_file(filename: str, data) -> None:
    """安全寫入 data/ 目錄下的 JSON 檔案"""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


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


# ─── API 回應快取裝飾器 ────────────────────────────────
def cached_response(ttl_seconds: int = 300):
    """快取 API 回應的裝飾器，預設 5 分鐘 TTL。

    Backend 在程序啟動時決定（Redis / in-memory，由 REDIS_URL 控制），
    失敗自動降級。僅適合無路徑參數的 GET 端點。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            cache_key = make_key(func.__name__, kwargs)
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl_seconds)
            return result
        return wrapper
    return decorator
