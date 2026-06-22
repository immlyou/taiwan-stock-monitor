"""系統層端點：/ 、/health 、/ready 與 /refresh"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.deps import rate_limit, verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["系統"])

# 同一時間只允許一個手動更新進行，避免重複下載浪費 FinLab 額度。
_refresh_lock = threading.Lock()

# 手動更新時強制重新下載的核心價格資料集（最新股價／成交量）。
# 只更新每日會變動的價格資料，避免一次重抓全部資料集而爆掉 FinLab 額度。
_REFRESH_KEYS = ["close", "open", "high", "low", "volume"]


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

    # 排程器狀態（純記憶體查詢，不觸發任何下載）。
    try:
        from core.scheduler import get_scheduler_status
        scheduler_info = get_scheduler_status()
    except Exception:  # noqa: BLE001 — health 不應因此失敗
        scheduler_info = {"enabled": False, "running": False}

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
            "scheduler": scheduler_info,
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
            "scheduler": scheduler_info,
            "timestamp": datetime.now().isoformat(),
        }

    # 服務本身健康；資料尚在背景預熱或尚未被請求觸發載入。
    return {
        "status": "ok",
        "version": "2.0.0",
        "data_status": "warming_up",
        "finlab": finlab_info,
        "scheduler": scheduler_info,
        "timestamp": datetime.now().isoformat(),
    }


# /ready 最多允許輪詢等待的秒數上限，避免部署腳本傳入過大值把連線卡住。
_READY_MAX_WAIT_SECONDS = 10.0
# 輪詢間隔（秒），等待期間每隔此秒數重新檢查一次快取。
_READY_POLL_INTERVAL = 0.2


def _close_ready() -> bool:
    """核心價格資料（close）是否已就緒。

    與 /health 同規則：只讀 DataCache 記憶體快取，絕不呼叫 loader.get()
    或觸發任何 FinLab 下載。
    """
    from core.data_loader import DataCache

    close = DataCache().get("close")
    return close is not None and not close.empty


@router.get("/ready")
async def ready(
    response: Response,
    wait: float = Query(
        default=0.0,
        ge=0.0,
        description="尚未就緒時最多輪詢等待的秒數（上限 10 秒，預設 0 即非阻塞）。",
    ),
) -> Dict[str, Any]:
    """就緒探針（readiness probe）。

    核心價格資料（DataCache 的 'close' 存在且非空）就緒時回 200
    ``{"status": "ready"}``；否則回 503 ``{"status": "warming_up"}``。

    與 /health 同規則：只讀記憶體快取，絕不觸發任何 FinLab 下載；用於讓
    Railway 等部署平台區分「活著」(/health) 與「資料就緒可服務」(/ready)。

    可選 ``?wait=<秒>``：尚未就緒時最多輪詢等待 N 秒（上限 10 秒）再回應，
    方便部署腳本等待預熱完成；預設 0 即立即回應、非阻塞。
    """
    # clamp 等待秒數，避免過大值把連線長時間卡住。
    wait_seconds = max(0.0, min(wait, _READY_MAX_WAIT_SECONDS))

    ready_flag = _close_ready()
    deadline = time.monotonic() + wait_seconds
    while not ready_flag and time.monotonic() < deadline:
        time.sleep(_READY_POLL_INTERVAL)
        ready_flag = _close_ready()

    if ready_flag:
        return {
            "status": "ready",
            "timestamp": datetime.now().isoformat(),
        }

    response.status_code = 503
    return {
        "status": "warming_up",
        "timestamp": datetime.now().isoformat(),
    }


@router.post(
    "/refresh",
    dependencies=[
        Depends(verify_api_key),
        # 手動更新會觸發 FinLab 重新下載，限制每 IP 每 5 分鐘最多 3 次，
        # 配合 _refresh_lock 的單飛行 409，避免額度被惡意燒光。
        Depends(rate_limit(max_calls=3, window_seconds=300)),
    ],
)
async def refresh_data() -> Dict[str, Any]:
    """強制手動更新最新股票資料。

    清除核心價格資料集（close/open/high/low/volume）的記憶體快取後，
    立即重新下載一次（雲端模式走 FinLab API；本地模式重讀 pickle），
    讓後續查詢取得最新資料。回傳更新後的最新資料日期與結果。

    同一時間僅允許一個更新進行，重複請求會收到 409，避免浪費 FinLab 額度。
    """
    from core.data_loader import DataCache, FinLabQuotaExceededError
    from api.state import loader

    if not _refresh_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="資料更新進行中，請稍候再試。")

    try:
        cache = DataCache()

        def _reload() -> Dict[str, Any]:
            # 先清掉舊快取，讓 get() 強制重新下載並重新填入快取。
            # 同時清除 Volume 持久化快取，否則 get() 會從磁碟讀回舊資料而非重新下載。
            for key in _REFRESH_KEYS:
                cache.clear_key(key)
            try:
                loader.clear_finlab_disk_cache(_REFRESH_KEYS)
            except Exception:  # noqa: BLE001 — 清磁碟快取失敗不應中斷更新
                logger.warning("清除 FinLab 磁碟快取失敗，繼續嘗試重新下載")

            loaded: list[str] = []
            failed: list[str] = []
            for key in _REFRESH_KEYS:
                try:
                    loader.get(key)  # use_cache=True：重新下載並回填快取
                    loaded.append(key)
                except FinLabQuotaExceededError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning("手動更新 %s 失敗: %s", key, exc)
                    failed.append(key)

            latest_date = None
            close = cache.get("close")
            if close is not None and not close.empty:
                latest_date = close.index.max().strftime("%Y-%m-%d")

            return {"loaded": loaded, "failed": failed, "latest_date": latest_date}

        # 重新下載可能耗時（全市場資料集），放到 thread pool 執行，
        # 避免阻塞事件迴圈。FinLabQuotaExceededError 由全域 handler 轉成 503。
        result = await asyncio.get_event_loop().run_in_executor(None, _reload)
    finally:
        _refresh_lock.release()

    return {
        "status": "ok",
        "refreshed": result["loaded"],
        "failed": result["failed"],
        "latest_data_date": result["latest_date"],
        "timestamp": datetime.now().isoformat(),
    }
