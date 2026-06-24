"""每日晨報端點：GET /morning-report"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from api.deps import verify_api_key
from api.helpers import _safe_json, cached_response
from api.routers.strategy import run_strategy
from api.state import DATA_DIR, loader
from core.data_loader import get_active_stocks, get_data_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["報告"], dependencies=[Depends(verify_api_key)])


@router.get("/morning-report")
@cached_response(ttl_seconds=1800)
async def morning_report():
    """
    產生每日晨報摘要，包含市場概況、漲跌排行、策略選股結果、新聞摘要。
    OpenClaw 可每日早上自動呼叫此端點取得晨報。

    回傳欄位包含前端所需的 summary、keyPoints、marketOutlook。
    """
    close = loader.get("close")
    active = get_active_stocks()

    latest = close[active].iloc[-1]
    prev = close[active].iloc[-2]
    changes = ((latest - prev) / prev * 100).dropna()

    top_gainers = changes.nlargest(5)
    top_losers = changes.nsmallest(5)

    strategies_summary = {}
    for stype in ("value", "growth", "momentum"):
        try:
            resp = await run_strategy(stype, preset="standard", top_n=5)
            strategies_summary[stype] = {
                "total": resp["total_matches"],
                "top5": [s["stock_id"] for s in resp["stocks"][:5]],
            }
        except Exception:
            strategies_summary[stype] = {"total": 0, "top5": []}

    summary = get_data_summary()

    # ── 新聞摘要 ──────────────────────────────────────────
    news_summary = []
    news_key_points = []
    market_outlook = ""

    try:
        from core.news_scanner import NewsScanner
        cache_path = DATA_DIR / "news_cache.json"
        CACHE_TTL_SECONDS = 600

        cache_valid = False
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    news_cache = json.load(f)
                updated_at_str = news_cache.get("updated_at") if isinstance(news_cache, dict) else None
                if updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    if (datetime.now() - updated_at).total_seconds() < CACHE_TTL_SECONDS:
                        cache_valid = True
            except Exception:
                cache_valid = False

        if not cache_valid:
            try:
                scanner = NewsScanner()
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, scanner.fetch_all_feeds),
                    timeout=25.0,
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"晨報新聞掃描失敗: {e}")

        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                news_cache = json.load(f)
            raw_news = news_cache.get("news", []) if isinstance(news_cache, dict) else []

            # 取最新 5 則新聞作為重點
            for item in raw_news[:5]:
                title = item.get("title", "")
                if title:
                    news_key_points.append(title)

            # 統計情緒分佈作為展望
            pos_count = sum(1 for n in raw_news if n.get("sentiment") == "positive")
            neg_count = sum(1 for n in raw_news if n.get("sentiment") == "negative")
            total_news = len(raw_news)

            if total_news > 0:
                if pos_count > neg_count * 1.5:
                    market_outlook = f"今日新聞偏多（{pos_count}/{total_news} 則正面），市場情緒樂觀。"
                elif neg_count > pos_count * 1.5:
                    market_outlook = f"今日新聞偏空（{neg_count}/{total_news} 則負面），留意下行風險。"
                else:
                    market_outlook = f"今日新聞情緒中性（共 {total_news} 則），觀望為宜。"

    except Exception as e:
        logger.error(f"晨報新聞整合失敗: {e}")

    # ── 組合摘要文字 ──────────────────────────────────────
    taiex_index = _safe_json(summary.get("taiex_index"))
    taiex_change = _safe_json(summary.get("taiex_change"))
    up_count = int((changes > 0).sum())
    down_count = int((changes < 0).sum())

    if taiex_index and taiex_change is not None:
        direction = "上漲" if taiex_change >= 0 else "下跌"
        summary_text = (
            f"台股加權指數 {taiex_index:,.0f} 點，{direction} {abs(taiex_change):.2f}%。"
            f"上漲家數 {up_count}，下跌家數 {down_count}。"
        )
    else:
        summary_text = f"上漲家數 {up_count}，下跌家數 {down_count}。"

    return {
        "date": summary.get("latest_date"),
        # 前端晨報摘要區塊所需欄位
        "summary": summary_text,
        "keyPoints": news_key_points,
        "marketOutlook": market_outlook,
        # 市場數據
        "taiex_index": taiex_index,
        "taiex_change": taiex_change,
        "market": {
            "up": up_count,
            "down": down_count,
            "flat": int((changes == 0).sum()),
        },
        "top_gainers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_gainers.items()
        ],
        "top_losers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_losers.items()
        ],
        "strategies": strategies_summary,
    }


def warm_morning_report() -> None:
    """同步預熱晨報快取（供啟動預熱與排程 re-warm 呼叫）。

    晨報冷啟動需重算 3 個選股策略 + 可能的新聞掃描（~18s），會超過前端 10s
    timeout 而被 abort，使用者誤以為沒資料。由啟動預熱與排程定期 re-warm 來
    保持快取常熱，讓使用者永遠命中熱快取。
    """
    import asyncio as _aio
    try:
        _aio.run(morning_report())  # 觸發 @cached_response 計算並寫入快取
    except RuntimeError:
        # 萬一所在執行緒已有 running loop，改用獨立 loop
        loop = _aio.new_event_loop()
        try:
            loop.run_until_complete(morning_report())
        finally:
            loop.close()


# /scanner/hidden-gems 已抽出到 api/routers/scanner.py


