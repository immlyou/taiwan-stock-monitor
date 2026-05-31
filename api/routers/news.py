"""新聞端點：/news/latest"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.state import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter(tags=["新聞"], dependencies=[Depends(verify_api_key)])


@router.get("/news/latest")
async def news_latest(
    limit: int = Query(default=20, ge=1, le=100),
    stock_id: Optional[str] = Query(default=None, description="依股票代號篩選"),
):
    """取得最新股市新聞。

    快取存在且在 10 分鐘內則直接回傳；否則即時觸發 RSS 掃描後回傳。
    回傳格式已對應前端欄位（url、publishedAt、id）。
    """
    try:
        cache_path = DATA_DIR / "news_cache.json"
        CACHE_TTL_SECONDS = 600  # 10 分鐘

        # 檢查快取是否存在且未過期
        cache_valid = False
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                updated_at_str = cache.get("updated_at") if isinstance(cache, dict) else None
                if updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    if (datetime.now() - updated_at).total_seconds() < CACHE_TTL_SECONDS:
                        cache_valid = True
            except Exception:
                cache_valid = False

        # 快取無效則即時掃描
        if not cache_valid:
            try:
                from core.news_scanner import NewsScanner
                scanner = NewsScanner()
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, scanner.fetch_all_feeds
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning("新聞掃描超時（30s），使用現有快取")
            except Exception as e:
                logger.error(f"新聞掃描失敗: {e}")

        # 讀取（可能剛更新的）快取
        if not cache_path.exists():
            return {"total": 0, "news": []}

        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)

        raw_items = cache if isinstance(cache, list) else cache.get("news", cache.get("items", []))

        if stock_id:
            raw_items = [n for n in raw_items if stock_id in n.get("stocks", [])]

        def _normalize_news_item(n: dict) -> dict:
            return {
                "id": n.get("content_hash") or n.get("id") or "",
                "title": n.get("title", ""),
                "source": n.get("source", ""),
                "url": n.get("url") or n.get("link", ""),
                "publishedAt": n.get("publishedAt") or n.get("published", ""),
                "category": n.get("category", ""),
                "summary": n.get("summary", ""),
                "stocks": n.get("stocks", []),
                "sentiment": n.get("sentiment", "neutral"),
                "keywords": n.get("keywords", []),
            }

        items = [_normalize_news_item(n) for n in raw_items[:limit]]

        return {
            "total": len(raw_items),
            "news": items,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
