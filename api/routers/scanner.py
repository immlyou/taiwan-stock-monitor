"""掃描器端點：/scanner/hidden-gems"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends

from api.deps import verify_api_key
from api.helpers import cached_response
from api.state import loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略"], dependencies=[Depends(verify_api_key)])


@router.get("/scanner/hidden-gems")
@cached_response(ttl_seconds=14400)  # 4 小時快取（盤後資料每日更新一次）
async def scanner_hidden_gems():
    """遺珠掃描器 — 全盤掃描台股市場，找出被忽略但潛力巨大的股票。

    掃描 6 大面向：低估價值、營收爆發、法人布局、技術反轉、小型成長、籌碼集中。
    計算量大，結果快取 4 小時。
    """
    from core.hidden_gems import HiddenGemsScanner

    loop = asyncio.get_event_loop()

    def _scan():
        scanner = HiddenGemsScanner()
        return scanner.scan(loader)

    return await loop.run_in_executor(None, _scan)
