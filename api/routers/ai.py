"""AI 分析端點：/ai/*

- /ai/news-sentiment        新聞情緒批次分析
- /ai/anomalies             個股異常偵測
- /ai/journal-review        交易日誌 retrospective
- /ai/stock-chat            個股對話（Claude）
- /ai/post-market-summary   盤後摘要
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import cached_response
from api.models import (
    JournalReviewRequest,
    NewsSentimentRequest,
    PostMarketSummaryRequest,
    StockChatRequest,
)
from api.state import loader
from core.intelligence import generate_stock_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI 分析"], dependencies=[Depends(verify_api_key)])


@router.get("/ai/stock-summary/{stock_id}")
async def ai_stock_summary(stock_id: str):
    """個股 AI 摘要 fallback：不依賴外部 LLM 的資料判讀摘要。"""
    try:
        return generate_stock_summary(loader, stock_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/news-sentiment")
async def ai_news_sentiment(req: NewsSentimentRequest):
    """AI 新聞情緒分析 - 用 Claude 批次分析新聞情緒"""
    from core.ai_models import ClaudeNewsSentimentAnalyzer
    loop = asyncio.get_event_loop()
    analyzer = ClaudeNewsSentimentAnalyzer()
    results = await loop.run_in_executor(None, analyzer.analyze_batch, req.news)
    return {"results": results}


@router.get("/ai/anomalies")
@cached_response(ttl_seconds=900)
async def ai_anomalies(
    scope: str = Query(default="watchlist", description="掃描範圍: watchlist / all"),
    explain: bool = Query(default=True, description="是否啟用 AI 解讀"),
):
    """AI 異常偵測 - 偵測爆量、跳空、法人轉向等異常訊號"""
    from core.ai_models import AnomalyDetector
    loop = asyncio.get_event_loop()

    detector = AnomalyDetector()

    stock_ids = None
    if scope == "watchlist":
        # 收集自選股 + 持倉（走共用 utils，路徑統一指向 repo 根目錄 data/）
        try:
            from app.components.portfolio_utils import load_portfolios
            from app.components.watchlist_utils import get_all_watched_stocks

            ids = set(get_all_watched_stocks())
            for p in load_portfolios().values():
                for h in (p.get("holdings", []) if isinstance(p, dict) else []):
                    ids.add(h.get("stock_id", ""))
            stock_ids = list(ids - {""}) if ids else None
        except Exception:
            logger.exception("收集 watchlist/portfolio 股票清單失敗，改為全市場掃描")
            stock_ids = None

    anomalies = await loop.run_in_executor(None, detector.detect, loader, stock_ids)

    explanation = ""
    if explain and anomalies:
        explanation = await loop.run_in_executor(None, detector.explain, anomalies)

    return {
        "anomalies": anomalies,
        "explanation": explanation,
        "total": len(anomalies),
        "high_count": sum(1 for a in anomalies if a.get("severity") == "high"),
        "medium_count": sum(1 for a in anomalies if a.get("severity") == "medium"),
    }


@router.post("/ai/journal-review")
async def ai_journal_review(req: JournalReviewRequest):
    """AI 交易日誌回顧 - 分析交易行為偏誤"""
    from core.ai_models import TradingJournalAnalyzer
    loop = asyncio.get_event_loop()
    analyzer = TradingJournalAnalyzer()
    result = await loop.run_in_executor(None, analyzer.analyze, req.entries)
    return result


@router.post("/ai/stock-chat")
async def ai_stock_chat(req: StockChatRequest):
    """AI 個股對話 - 自然語言問答"""
    from core.ai_models import StockChatAssistant
    loop = asyncio.get_event_loop()

    assistant = StockChatAssistant()

    # 收集數據上下文
    context_parts = []
    try:
        close = loader.get("close")
        if close is not None and req.stock_id in close.columns:
            prices = close[req.stock_id].dropna()
            if len(prices) > 0:
                latest = float(prices.iloc[-1])
                prev = float(prices.iloc[-2]) if len(prices) > 1 else latest
                chg = (latest / prev - 1) * 100
                context_parts.append(f"收盤價: {latest:.2f} (漲跌: {chg:+.2f}%)")
                high_52w = float(prices.iloc[-252:].max()) if len(prices) >= 252 else float(prices.max())
                low_52w = float(prices.iloc[-252:].min()) if len(prices) >= 252 else float(prices.min())
                context_parts.append(f"52週高低: {high_52w:.2f} / {low_52w:.2f}")
    except Exception:
        pass
    for key, label in [("pe_ratio", "本益比"), ("pb_ratio", "股價淨值比"), ("dividend_yield", "殖利率")]:
        try:
            df = loader.get(key)
            if df is not None and req.stock_id in df.columns:
                val = float(df[req.stock_id].dropna().iloc[-1])
                context_parts.append(f"{label}: {val:.2f}")
        except Exception:
            pass

    # 取得股票名稱
    name = req.stock_id
    try:
        info = loader.get_stock_info()
        if info is not None:
            row = info[info["stock_id"] == req.stock_id]
            if len(row) > 0:
                name = row["name"].values[0]
    except Exception:
        pass

    data_context = "\n".join(context_parts) if context_parts else "暫無數據"

    reply = await loop.run_in_executor(
        None, assistant.chat, req.stock_id, name, data_context, req.question, req.history
    )
    return {"reply": reply, "stock_id": req.stock_id, "name": name}


@router.post("/ai/post-market-summary")
async def ai_post_market_summary(req: PostMarketSummaryRequest):
    """AI 盤後摘要 - 生成覆盤報告"""
    from core.ai_models import PostMarketSummarizer
    loop = asyncio.get_event_loop()

    summarizer = PostMarketSummarizer()

    # 自動收集市場數據
    market_data = req.market_data or {}
    if not market_data:
        try:
            close = loader.get("close")
            if close is not None and len(close) > 1:
                market_data["date"] = close.index[-1].strftime("%Y-%m-%d")
                change_pct = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).fillna(0)

                info = loader.get_stock_info()
                name_map = dict(zip(info["stock_id"], info["name"])) if info is not None else {}

                sorted_change = change_pct.sort_values(ascending=False)
                market_data["top_gainers"] = [
                    {"stock_id": s, "name": name_map.get(s, ""), "change_pct": float(sorted_change[s])}
                    for s in sorted_change.head(5).index
                ]
                market_data["top_losers"] = [
                    {"stock_id": s, "name": name_map.get(s, ""), "change_pct": float(sorted_change[s])}
                    for s in sorted_change.tail(5).index
                ]

            for key, field in [("foreign_investors", "foreign_net"), ("investment_trust", "trust_net"), ("dealer", "dealer_net")]:
                df = loader.get(key)
                if df is not None and len(df) > 0:
                    market_data[field] = float(df.iloc[-1].sum()) / 100_000_000
        except Exception:
            pass

    result = await loop.run_in_executor(None, summarizer.generate, market_data)
    return result


# ════════════════════════════════════════════════════════
# 策略端點（固定路徑優先於動態路徑）
# ════════════════════════════════════════════════════════

# 注意：/strategy/ai-pick、/strategy/composite、/strategy/ai-claude/{stock_id}
# /strategy/ai-lstm/{stock_id}、/strategy/ai-xgboost 均定義在
# /strategy/{strategy_type} 之前，確保 FastAPI 路由匹配正確。
