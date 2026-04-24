"""FastAPI 依賴：API Key 驗證

未設定 STOCK_API_KEY 時允許所有請求通過（本地開發模式）。
生產環境務必設定此環境變數。
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

API_KEY: str = os.getenv("STOCK_API_KEY", "")
security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> bool:
    """驗證 API Key（若有設定）。"""
    if not API_KEY:
        logger.debug("API_KEY 未設定，跳過認證（本地開發模式）")
        return True
    if not credentials or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="無效的 API Key")
    return True
