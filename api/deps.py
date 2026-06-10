"""FastAPI 依賴：API Key 驗證與輕量 rate limit

驗證策略（fail-closed）：
- 雲端環境（偵測到 Railway 注入的環境變數）未設定 STOCK_API_KEY 時，
  一律回 503 拒絕存取，避免生產環境意外全開。
- 本地開發（非雲端且未設定金鑰）才允許所有請求通過。
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

API_KEY: str = os.getenv("STOCK_API_KEY", "")
# Railway 部署時會自動注入這些變數；任一存在即視為雲端環境
IS_CLOUD: bool = bool(
    os.getenv("RAILWAY_ENVIRONMENT")
    or os.getenv("RAILWAY_ENVIRONMENT_NAME")
    or os.getenv("RAILWAY_PROJECT_ID")
)
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> bool:
    """驗證 API Key。雲端未設定金鑰時 fail-closed。"""
    if not API_KEY:
        if IS_CLOUD:
            raise HTTPException(
                status_code=503,
                detail="伺服器尚未設定 STOCK_API_KEY，暫不開放存取",
            )
        return True  # 本地開發模式
    if not credentials or not secrets.compare_digest(
        credentials.credentials.encode(), API_KEY.encode()
    ):
        raise HTTPException(status_code=401, detail="無效的 API Key")
    return True


def rate_limit(max_calls: int, window_seconds: float):
    """每個來源 IP 在 window_seconds 內最多 max_calls 次的滑動視窗限流。

    單進程記憶體實作（Railway 跑單 worker monolith，足夠用）。
    超限回 429。
    """
    calls: Dict[str, Deque[float]] = defaultdict(deque)
    lock = threading.Lock()

    async def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with lock:
            q = calls[ip]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_calls:
                raise HTTPException(
                    status_code=429, detail="請求過於頻繁，請稍後再試"
                )
            q.append(now)
            # 順手清掉已閒置的其他 IP，避免長期累積
            if len(calls) > 1024:
                stale = [
                    k for k, v in calls.items()
                    if k != ip and (not v or now - v[-1] > window_seconds)
                ]
                for key in stale:
                    del calls[key]

    return dependency
