"""AI trading radar endpoints."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_user_id, verify_api_key
from api.helpers import cached_response
from api.state import loader
from core.radar_pro import RadarPro
from core.trading_radar import TradingRadar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["操盤雷達"], dependencies=[Depends(verify_api_key)])


@router.get("/radar/stocks")
@cached_response(ttl_seconds=1800)
async def radar_stocks(
    top_n: int = Query(default=50, ge=1, le=200, description="回傳前 N 筆操盤雷達訊號"),
):
    """AI 操盤雷達清單：主力吸籌、營收爆發、出貨風險、進場等待區與每日觀察。"""
    loop = asyncio.get_event_loop()

    def _scan():
        return TradingRadar(loader).scan(top_n=top_n)

    try:
        return await loop.run_in_executor(None, _scan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/stock/{stock_id}")
async def radar_stock(stock_id: str):
    """單一個股 AI 操盤雷達。"""
    try:
        return TradingRadar(loader).analyze_stock(stock_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/backtest")
@cached_response(ttl_seconds=3600)
async def radar_backtest(
    days: int = Query(default=180, ge=80, le=720),
    top_n: int = Query(default=20, ge=5, le=80),
):
    """雷達訊號歷史代理回測：估算 5/10/20 日勝率與平均報酬。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: RadarPro(loader).backtest(days=days, top_n=top_n))


@router.get("/radar/tracking")
@cached_response(ttl_seconds=1800)
async def radar_tracking():
    """訊號追蹤與命中率儀表板。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: RadarPro(loader).tracking())


@router.get("/radar/portfolio-health/{portfolio_id}")
async def radar_portfolio_health(
    portfolio_id: str, user_id: str = Depends(get_user_id)
):
    """持倉自動健檢。"""
    try:
        return RadarPro(loader).portfolio_health(portfolio_id, user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/peers/{stock_id}")
async def radar_peers(
    stock_id: str,
    top_n: int = Query(default=12, ge=3, le=50),
):
    """同業比較雷達。"""
    try:
        return RadarPro(loader).peer_comparison(stock_id, top_n=top_n)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到同業資料: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/daily-report")
@cached_response(ttl_seconds=1800)
async def radar_daily_report():
    """每日操盤報告。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: RadarPro(loader).daily_report())


@router.get("/radar/notifications/preview")
@cached_response(ttl_seconds=1800)
async def radar_notification_preview(
    portfolio_id: str = Query(default="default"),
    user_id: str = Depends(get_user_id),
):
    """Telegram / Email 智慧推播預覽。"""
    return RadarPro(loader).notification_preview(
        portfolio_id=portfolio_id, user_id=user_id
    )


@router.get("/radar/events/{stock_id}")
async def radar_events(
    stock_id: str,
    days: int = Query(default=90, ge=30, le=365),
):
    """個股事件時間軸。"""
    try:
        return RadarPro(loader).event_timeline(stock_id, days=days)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/price-plan/{stock_id}")
async def radar_price_plan(stock_id: str):
    """價格區間、停損停利與 R/R 建議。"""
    try:
        return RadarPro(loader).price_plan(stock_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/news-revenue/{stock_id}")
async def radar_news_revenue(stock_id: str):
    """新聞與營收解讀。"""
    try:
        return RadarPro(loader).news_revenue(stock_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/radar/broker-chip/{stock_id}")
async def radar_broker_chip(stock_id: str):
    """券商籌碼代理訊號；若無分點資料，以三大法人代理。"""
    return RadarPro(loader).broker_chip_proxy(stock_id)


def warm_radar() -> None:
    """同步預熱操盤雷達的重端點快取，讓使用者不碰冷啟動。

    backtest 冷啟動 ~15s、notifications 原本未快取 ~3.7s。以前端實際使用的
    參數（backtest days=180/top_n=20）驅動 @cached_response 寫入快取。
    """
    import asyncio as _aio

    async def _run() -> None:
        try:
            await radar_backtest(days=180, top_n=20)
        except Exception as e:  # noqa: BLE001
            logger.warning("雷達 backtest 預熱失敗: %s", e)
        try:
            await radar_notification_preview(portfolio_id="default")
        except Exception as e:  # noqa: BLE001
            logger.warning("雷達 notifications 預熱失敗: %s", e)

    try:
        _aio.run(_run())
    except RuntimeError:
        loop = _aio.new_event_loop()
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()
