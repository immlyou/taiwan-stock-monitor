"""系統層端點：/ 與 /health"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["系統"])


@router.get("/")
async def root() -> Dict[str, Any]:
    """API 根目錄"""
    return {
        "name": "台股戰情中心 API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@router.get("/health")
async def health() -> Dict[str, Any]:
    """系統健康檢查。

    回傳 API 服務狀態、資料載入狀態、最新資料日期及 FinLab API 流量統計。
    """
    from core.data_loader import (
        DataCache,
        FINLAB_CACHE_TTL,
        _finlab_quota_exceeded,
        _finlab_usage_mb,
    )

    cache = DataCache()
    cache_stats = cache.get_stats()

    finlab_info = {
        "estimated_usage_mb": round(_finlab_usage_mb, 1),
        "quota_exceeded": _finlab_quota_exceeded,
        "cache_ttl_seconds": FINLAB_CACHE_TTL,
        "cached_datasets": cache_stats.get("total_items", 0),
    }

    if _finlab_quota_exceeded:
        return {
            "status": "degraded",
            "error": (
                "FinLab API 額度超限，已啟用多源 fallback "
                "(yfinance/TWSE/FinMind)"
            ),
            "fallback_active": True,
            "fallback_sources": ["yfinance", "twse", "finmind"],
            "finlab": finlab_info,
            "timestamp": datetime.now().isoformat(),
        }

    # 只從記憶體快取讀取資料新鮮度，絕不在 healthcheck 內觸發 FinLab 下載；
    # 否則雲端模式下 healthcheck 會因下載大資料集而超時，導致 Railway 判定
    # 啟動失敗並回 502（應用程式無法回應）。
    close = cache.get("close")
    if close is not None and not close.empty:
        return {
            "status": "ok",
            "version": "2.0.0",
            "latest_data_date": close.index.max().strftime("%Y-%m-%d"),
            "total_stocks": len(close.columns),
            "finlab": finlab_info,
            "timestamp": datetime.now().isoformat(),
        }

    # 服務本身健康；資料尚在背景預熱或尚未被請求觸發載入。
    return {
        "status": "ok",
        "version": "2.0.0",
        "data_status": "warming_up",
        "finlab": finlab_info,
        "timestamp": datetime.now().isoformat(),
    }
