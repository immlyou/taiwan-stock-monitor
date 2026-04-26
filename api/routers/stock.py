"""個股端點：/stock/{id}/*

包含：
- /stock/{id}                基本資訊 + 近期行情
- /stock/{id}/technical      技術指標快照（RSI/MACD/均線）
- /stock/{id}/chip           籌碼（三大法人持股）
- /stock/{id}/ohlcv          OHLCV 歷史
- /stock/{id}/technical-chart 技術指標時序資料（供前端繪圖）
- /stock/{id}/financials     財報摘要
- /stock/{id}/chip/detail    大戶持股分佈

部分端點附帶 Goodinfo / yfinance / FinMind fallback。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _get_industry_map, _get_stock_name_map, _safe_json, cached_response
from api.state import loader, multi_source
from core.company_profile import get_company_profile
from core.data_loader import FinLabQuotaExceededError
from core.indicators import (
    calculate_atr,
    calculate_bias,
    calculate_bollinger_bands,
    calculate_cci,
    calculate_ema,
    calculate_kdj,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_williams_r,
)
from core.intelligence import calculate_score_history
from core.stock_score import calculate_stock_score

logger = logging.getLogger(__name__)

router = APIRouter(tags=["個股"], dependencies=[Depends(verify_api_key)])


@router.get("/stock/{stock_id}")
async def stock_info(
    stock_id: str,
    days: int = Query(default=5, description="取得最近 N 天的資料", ge=1, le=250),
):
    """
    個股基本資訊與近期行情。
    範例: /stock/2330?days=10
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用替代來源 ──
    if _finlab_quota_exceeded:
        logger.info("[stock_info] FinLab 額度超限，走 fallback: %s", stock_id)
        return await _stock_info_fallback(stock_id, days)

    try:
        close = loader.get("close")
    except FinLabQuotaExceededError:
        logger.warning("[stock_info] FinLab quota hit, switching to fallback: %s", stock_id)
        return await _stock_info_fallback(stock_id, days)
    if stock_id not in close.columns:
        # Fallback: 嘗試從 Goodinfo 取得資料（支援興櫃等 FinLab 不涵蓋的股票）
        return await _goodinfo_stock_fallback(stock_id)

    price_data = close[stock_id].dropna().tail(days)
    latest_price = float(price_data.iloc[-1])
    prev_price = float(price_data.iloc[-2]) if len(price_data) >= 2 else latest_price
    change_pct = round((latest_price - prev_price) / prev_price * 100, 2)

    pe = pb = dy = None
    try:
        pe_df = loader.get("pe_ratio")
        if stock_id in pe_df.columns:
            pe = _safe_json(pe_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass
    try:
        pb_df = loader.get("pb_ratio")
        if stock_id in pb_df.columns:
            pb = _safe_json(pb_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass
    try:
        dy_df = loader.get("dividend_yield")
        if stock_id in dy_df.columns:
            dy = _safe_json(dy_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    rev_yoy = None
    try:
        yoy_df = loader.get("revenue_yoy")
        if stock_id in yoy_df.columns:
            rev_yoy = _safe_json(yoy_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    name_map = _get_stock_name_map()
    industry_map = _get_industry_map()
    company_profile = None
    try:
        company_profile = get_company_profile(loader, stock_id)
    except Exception:
        company_profile = None

    return {
        "stock_id": stock_id,
        "name": name_map.get(stock_id, ""),
        "industry": company_profile.get("industry") if company_profile else industry_map.get(stock_id, ""),
        "latest_price": round(latest_price, 2),
        "change_pct": change_pct,
        "date": price_data.index[-1].strftime("%Y-%m-%d"),
        "pe_ratio": pe,
        "pb_ratio": pb,
        "dividend_yield": dy,
        "revenue_yoy": rev_yoy,
        "company_profile": company_profile,
        "price_history": [
            {
                "date": d.strftime("%Y-%m-%d"),
                "price": round(float(p), 2),
            }
            for d, p in price_data.items()
        ],
    }


@router.get("/stock/{stock_id}/profile")
async def stock_company_profile(
    stock_id: str,
    refresh: bool = Query(default=False, description="略過本程序快取並重新嘗試資料來源"),
):
    """公司營運概況：主要產品線、營收來源、業務範圍與產業別。"""
    try:
        return get_company_profile(loader, stock_id, refresh=refresh)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到公司基本資料: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{stock_id}/scorecard")
async def stock_scorecard(stock_id: str):
    """個股量化評分卡：價值、成長、動能、籌碼、品質、風險六構面。"""
    try:
        score = calculate_stock_score(loader, stock_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    name_map = _get_stock_name_map()
    industry_map = _get_industry_map()
    return {
        **score,
        "name": name_map.get(stock_id, ""),
        "industry": industry_map.get(stock_id, ""),
    }


@router.get("/stock/{stock_id}/score-history")
async def stock_score_history(
    stock_id: str,
    days: int = Query(default=20, ge=2, le=30, description="評分歷史交易日數"),
):
    """個股量化評分歷史，用於觀察升降級與分數趨勢。"""
    try:
        return calculate_score_history(loader, stock_id, days=days)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _goodinfo_ohlcv_fallback(stock_id: str, days: int = 120):
    """Goodinfo OHLCV fallback：從 Goodinfo 取得歷史價格"""
    from core.goodinfo import fetch_ohlcv
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, fetch_ohlcv, stock_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    # 只取最近 days 筆
    records = records[-days:]
    return {
        "stock_id": stock_id,
        "days": len(records),
        "data": records,
        "source": "goodinfo",
    }


async def _goodinfo_stock_fallback(stock_id: str):
    """Goodinfo fallback：用於 FinLab 不涵蓋的股票（如興櫃）"""
    from core.goodinfo import fetch_stock_detail
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, fetch_stock_detail, stock_id)
    if not data or "price" not in data:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "stock_id": stock_id,
        "name": data.get("name", ""),
        "industry": data.get("industry", ""),
        "latest_price": data.get("price"),
        "change_pct": data.get("change_pct"),
        "date": today,
        "pe_ratio": data.get("per"),
        "pb_ratio": data.get("pbr"),
        "dividend_yield": data.get("dividend_yield"),
        "revenue_yoy": None,
        "price_history": [{"date": today, "price": data.get("price")}] if data.get("price") else [],
        "source": "goodinfo",
        "market": data.get("market", ""),
    }


async def _stock_info_fallback(stock_id: str, days: int):
    """stock_info 的 fallback 實作: yfinance + FinMind"""
    # 價格來自 yfinance
    ohlcv = multi_source.get_ohlcv(stock_id, days)
    if not ohlcv or not ohlcv.get("data"):
        raise HTTPException(status_code=503, detail="FinLab 額度超限且 fallback 來源無資料")

    price_history = ohlcv["data"]
    latest = price_history[-1]
    prev = price_history[-2] if len(price_history) >= 2 else latest
    latest_price = latest.get("close") or 0
    prev_price = prev.get("close") or latest_price
    change_pct = round((latest_price - prev_price) / prev_price * 100, 2) if prev_price else 0

    # 基本面來自 FinMind
    fund = multi_source.get_fundamentals(stock_id)
    pe = fund.get("pe_ratio") if fund else None
    pb = fund.get("pb_ratio") if fund else None
    dy = fund.get("dividend_yield") if fund else None

    # 即時報價取得股票名稱
    quote = multi_source.get_realtime_quote(stock_id)
    name = quote.get("name", "") if quote else ""

    return {
        "stock_id": stock_id,
        "name": name,
        "industry": "",
        "latest_price": round(latest_price, 2),
        "change_pct": change_pct,
        "date": latest.get("date", ""),
        "pe_ratio": pe,
        "pb_ratio": pb,
        "dividend_yield": dy,
        "revenue_yoy": None,
        "price_history": [
            {"date": r["date"], "price": round(r.get("close") or 0, 2)}
            for r in price_history
        ],
        "source": "fallback",
    }


@router.get("/stock/{stock_id}/technical")
async def stock_technical(stock_id: str):
    """
    個股技術指標：RSI、MACD、均線（最新一筆快照）。
    範例: /stock/2330/technical
    """
    close = loader.get("close")
    if stock_id not in close.columns:
        # Fallback: 用 Goodinfo OHLCV 計算技術指標
        return await _goodinfo_technical_fallback(stock_id)

    series = close[stock_id].dropna()

    rsi_14 = calculate_rsi(series, period=14)
    latest_rsi = _safe_json(rsi_14.iloc[-1]) if len(rsi_14) > 0 else None

    macd_line, signal_line, histogram = calculate_macd(series)
    latest_macd = _safe_json(macd_line.iloc[-1]) if len(macd_line) > 0 else None
    latest_signal = _safe_json(signal_line.iloc[-1]) if len(signal_line) > 0 else None

    sma_5 = calculate_sma(series, period=5)
    sma_20 = calculate_sma(series, period=20)
    sma_60 = calculate_sma(series, period=60)

    latest_price = float(series.iloc[-1])

    trend = "盤整"
    if sma_5.iloc[-1] > sma_20.iloc[-1] > sma_60.iloc[-1]:
        trend = "多頭排列"
    elif sma_5.iloc[-1] < sma_20.iloc[-1] < sma_60.iloc[-1]:
        trend = "空頭排列"

    rsi_signal = "中性"
    if latest_rsi and latest_rsi > 70:
        rsi_signal = "超買"
    elif latest_rsi and latest_rsi < 30:
        rsi_signal = "超賣"

    return {
        "stock_id": stock_id,
        "price": round(latest_price, 2),
        "rsi_14": latest_rsi,
        "rsi_signal": rsi_signal,
        "macd": latest_macd,
        "macd_signal": latest_signal,
        "macd_histogram": _safe_json(histogram.iloc[-1]) if len(histogram) > 0 else None,
        "sma_5": _safe_json(sma_5.iloc[-1]),
        "sma_20": _safe_json(sma_20.iloc[-1]),
        "sma_60": _safe_json(sma_60.iloc[-1]),
        "trend": trend,
    }


async def _goodinfo_technical_fallback(stock_id: str):
    """用 Goodinfo OHLCV 計算技術指標"""
    import pandas as pd
    from core.goodinfo import fetch_ohlcv
    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(None, fetch_ohlcv, stock_id)
    if not records or len(records) < 5:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    closes = pd.Series(
        [r["close"] for r in records],
        index=pd.to_datetime([r["date"] for r in records]),
    )

    latest_price = float(closes.iloc[-1])
    result = {"stock_id": stock_id, "price": round(latest_price, 2), "source": "goodinfo"}

    try:
        rsi = calculate_rsi(closes, period=14)
        result["rsi_14"] = _safe_json(rsi.iloc[-1]) if len(rsi) > 0 else None
        if result["rsi_14"] and result["rsi_14"] > 70:
            result["rsi_signal"] = "超買"
        elif result["rsi_14"] and result["rsi_14"] < 30:
            result["rsi_signal"] = "超賣"
        else:
            result["rsi_signal"] = "中性"
    except Exception:
        result["rsi_14"] = None
        result["rsi_signal"] = "中性"

    try:
        macd_line, signal_line, histogram = calculate_macd(closes)
        result["macd"] = _safe_json(macd_line.iloc[-1]) if len(macd_line) > 0 else None
        result["macd_signal"] = _safe_json(signal_line.iloc[-1]) if len(signal_line) > 0 else None
        result["macd_histogram"] = _safe_json(histogram.iloc[-1]) if len(histogram) > 0 else None
    except Exception:
        result["macd"] = result["macd_signal"] = result["macd_histogram"] = None

    try:
        sma_5 = calculate_sma(closes, period=5)
        sma_20 = calculate_sma(closes, period=20)
        result["sma_5"] = _safe_json(sma_5.iloc[-1]) if len(sma_5) > 0 else None
        result["sma_20"] = _safe_json(sma_20.iloc[-1]) if len(sma_20) > 0 else None
        result["sma_60"] = None  # 資料不足 60 天

        if result["sma_5"] and result["sma_20"]:
            result["trend"] = "多頭排列" if result["sma_5"] > result["sma_20"] else "空頭排列"
        else:
            result["trend"] = "盤整"
    except Exception:
        result["sma_5"] = result["sma_20"] = result["sma_60"] = None
        result["trend"] = "盤整"

    return result


@router.get("/stock/{stock_id}/chip")
async def stock_chip(
    stock_id: str,
    days: int = Query(default=5, description="最近 N 天", ge=1, le=60),
):
    """
    個股籌碼分析：三大法人買賣超、外資持股比率、融資融券。
    範例: /stock/2330/chip?days=10
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用 TWSE ──
    if _finlab_quota_exceeded:
        logger.info("[chip] FinLab 額度超限，走 TWSE fallback: %s", stock_id)
        result = multi_source.get_institutional(stock_id, days) or {"stock_id": stock_id}
        margin = multi_source.get_margin(stock_id, days)
        if margin:
            result["margin_buy"] = margin.get("margin_buy")
            result["margin_sell"] = margin.get("margin_sell")
        result["source"] = "fallback"
        return result

    result = {"stock_id": stock_id}

    for key, label in [
        ("foreign_investors", "外資"),
        ("investment_trust", "投信"),
        ("dealer", "自營商"),
    ]:
        try:
            df = loader.get(key)
            if stock_id in df.columns:
                data = df[stock_id].dropna().tail(days)
                total = float(data.sum())
                result[label] = {
                    "total_shares": int(total),
                    "daily": [
                        {"date": d.strftime("%Y-%m-%d"), "shares": int(v)}
                        for d, v in data.items()
                    ],
                }
        except Exception:
            pass

    try:
        fh = loader.get("foreign_holding")
        if stock_id in fh.columns:
            latest = fh[stock_id].dropna().iloc[-1]
            result["foreign_holding_pct"] = _safe_json(latest)
    except Exception:
        pass

    try:
        mb = loader.get("margin_buy")
        ms = loader.get("margin_sell")
        if stock_id in mb.columns:
            result["margin_buy"] = _safe_json(mb[stock_id].dropna().iloc[-1])
        if stock_id in ms.columns:
            result["margin_sell"] = _safe_json(ms[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    return result


# ════════════════════════════════════════════════════════
# 第二批：個股擴充
# ════════════════════════════════════════════════════════

@router.get("/stock/{stock_id}/ohlcv")
@cached_response(ttl_seconds=300)
async def stock_ohlcv(
    stock_id: str,
    days: int = Query(default=120, ge=5, le=1260, description="最近 N 個交易日"),
):
    """
    個股 OHLCV 時序資料。

    回傳開高低收量的每日時序，供前端繪製 K 線圖。
    範例: /stock/2330/ohlcv?days=120
    """
    from core.data_loader import _finlab_quota_exceeded

    # ── Fallback: FinLab 額度超限時改用 yfinance ──
    if _finlab_quota_exceeded:
        logger.info("[ohlcv] FinLab 額度超限，走 yfinance fallback: %s", stock_id)
        fallback = multi_source.get_ohlcv(stock_id, days)
        if fallback:
            return fallback
        raise HTTPException(status_code=503, detail="FinLab 額度超限且 fallback 來源無資料")

    try:
        close = loader.get("close")
        if stock_id not in close.columns:
            # Fallback: Goodinfo OHLCV（支援興櫃等 FinLab 不涵蓋的股票）
            return await _goodinfo_ohlcv_fallback(stock_id, days)

        close_s = close[stock_id].dropna().tail(days)
        dates = close_s.index

        # 一次載入所需的 DataFrame，避免重複讀取 pickle
        open_s = high_s = low_s = vol_s = None
        for key, name in [("open", "open_s"), ("high", "high_s"), ("low", "low_s"), ("volume", "vol_s")]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].reindex(dates)
                    if name == "open_s": open_s = series
                    elif name == "high_s": high_s = series
                    elif name == "low_s": low_s = series
                    elif name == "vol_s": vol_s = series
            except Exception:
                pass

        records = []
        for d in dates:
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "close": _safe_json(close_s.loc[d]),
                "open": _safe_json(open_s.loc[d]) if open_s is not None else None,
                "high": _safe_json(high_s.loc[d]) if high_s is not None else None,
                "low": _safe_json(low_s.loc[d]) if low_s is not None else None,
                "volume": _safe_json(vol_s.loc[d]) if vol_s is not None else None,
            }
            records.append(row)

        return {
            "stock_id": stock_id,
            "days": len(records),
            "data": records,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{stock_id}/technical-chart")
@cached_response(ttl_seconds=300)
async def stock_technical_chart(
    stock_id: str,
    days: int = Query(default=120, ge=30, le=1260, description="最近 N 個交易日"),
):
    """
    個股完整技術指標時序。

    回傳含 SMA5/20/60、RSI14、MACD、BB 的每日時序，供前端繪製技術分析圖。
    範例: /stock/2330/technical-chart?days=120
    """
    try:
        close = loader.get("close")
        if stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

        series = close[stock_id].dropna()
        # 取末 days 筆，但計算指標需要更多歷史（額外取 60 筆緩衝）
        full_series = series.tail(days + 80)
        tail_dates = series.tail(days).index

        sma5 = calculate_sma(full_series, 5)
        sma20 = calculate_sma(full_series, 20)
        sma60 = calculate_sma(full_series, 60)
        rsi14 = calculate_rsi(full_series, 14)
        macd_line, signal_line, histogram = calculate_macd(full_series)
        bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(full_series, 20)

        high_s = low_s = None
        try:
            high_df = loader.get("high")
            low_df = loader.get("low")
            if stock_id in high_df.columns:
                high_s = high_df[stock_id].dropna()
            if stock_id in low_df.columns:
                low_s = low_df[stock_id].dropna()
        except Exception:
            pass

        kdj_k = kdj_d = kdj_j = None
        if high_s is not None and low_s is not None:
            try:
                h_full = high_s.reindex(full_series.index)
                l_full = low_s.reindex(full_series.index)
                kdj_k, kdj_d, kdj_j = calculate_kdj(h_full, l_full, full_series)
            except Exception:
                pass

        records = []
        for d in tail_dates:
            if d not in full_series.index:
                continue
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "close": _safe_json(full_series.loc[d]),
                "sma5": _safe_json(sma5.loc[d]) if d in sma5.index else None,
                "sma20": _safe_json(sma20.loc[d]) if d in sma20.index else None,
                "sma60": _safe_json(sma60.loc[d]) if d in sma60.index else None,
                "rsi14": _safe_json(rsi14.loc[d]) if d in rsi14.index else None,
                "macd": _safe_json(macd_line.loc[d]) if d in macd_line.index else None,
                "macd_signal": _safe_json(signal_line.loc[d]) if d in signal_line.index else None,
                "macd_hist": _safe_json(histogram.loc[d]) if d in histogram.index else None,
                "bb_upper": _safe_json(bb_upper.loc[d]) if d in bb_upper.index else None,
                "bb_mid": _safe_json(bb_mid.loc[d]) if d in bb_mid.index else None,
                "bb_lower": _safe_json(bb_lower.loc[d]) if d in bb_lower.index else None,
                "kdj_k": _safe_json(kdj_k.loc[d]) if kdj_k is not None and d in kdj_k.index else None,
                "kdj_d": _safe_json(kdj_d.loc[d]) if kdj_d is not None and d in kdj_d.index else None,
                "kdj_j": _safe_json(kdj_j.loc[d]) if kdj_j is not None and d in kdj_j.index else None,
            }
            records.append(row)

        return {
            "stock_id": stock_id,
            "days": len(records),
            "data": records,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{stock_id}/financials")
async def stock_financials(
    stock_id: str,
    months: int = Query(default=12, ge=3, le=60, description="最近 N 個月"),
):
    """
    個股財報資料 - 月營收、本益比、股價淨值比、殖利率。

    範例: /stock/2330/financials
    """
    try:
        result: Dict[str, Any] = {"stock_id": stock_id, "months": months}

        for key, label in [
            ("monthly_revenue", "monthly_revenue"),
            ("revenue_yoy", "revenue_yoy"),
            ("revenue_mom", "revenue_mom"),
            ("pe_ratio", "pe_ratio"),
            ("pb_ratio", "pb_ratio"),
            ("dividend_yield", "dividend_yield"),
        ]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna().tail(months)
                    result[label] = [
                        {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                        for d, v in series.items()
                    ]
                else:
                    result[label] = []
            except Exception:
                result[label] = []

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{stock_id}/chip/detail")
@cached_response(ttl_seconds=300)
async def stock_chip_detail(
    stock_id: str,
    days: int = Query(default=30, ge=5, le=120, description="最近 N 天"),
):
    """
    個股詳細籌碼分析 - 含大戶持股分布時序。

    範例: /stock/2330/chip/detail?days=30
    """
    try:
        result: Dict[str, Any] = {"stock_id": stock_id, "days": days}

        # 三大法人時序
        for key, label in [
            ("foreign_investors", "foreign"),
            ("investment_trust", "investment_trust"),
            ("dealer", "dealer"),
        ]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna().tail(days)
                    result[label] = {
                        "latest": _safe_json(series.iloc[-1]) if len(series) > 0 else None,
                        "total": _safe_json(series.sum()),
                        "data": [
                            {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                            for d, v in series.items()
                        ],
                    }
            except Exception:
                result[label] = None

        # 外資持股比率
        try:
            fh = loader.get("foreign_holding")
            if stock_id in fh.columns:
                series = fh[stock_id].dropna().tail(days)
                result["foreign_holding"] = {
                    "latest": _safe_json(series.iloc[-1]) if len(series) > 0 else None,
                    "data": [
                        {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                        for d, v in series.items()
                    ],
                }
        except Exception:
            result["foreign_holding"] = None

        # 融資融券時序
        for key, label in [("margin_buy", "margin_buy"), ("margin_sell", "margin_sell")]:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna().tail(days)
                    result[label] = {
                        "latest": _safe_json(series.iloc[-1]) if len(series) > 0 else None,
                        "data": [
                            {"date": d.strftime("%Y-%m-%d"), "value": _safe_json(v)}
                            for d, v in series.items()
                        ],
                    }
            except Exception:
                result[label] = None

        # 大戶持股分布（取最新一筆）
        inventory_keys = [
            "inventory_total_holders",
            "inventory_over_1000_ratio",
            "inventory_over_400_ratio",
            "inventory_under_10_ratio",
        ]
        inventory_data = {}
        for key in inventory_keys:
            try:
                df = loader.get(key)
                if stock_id in df.columns:
                    series = df[stock_id].dropna()
                    if len(series) > 0:
                        inventory_data[key] = _safe_json(series.iloc[-1])
            except Exception:
                pass
        result["inventory"] = inventory_data

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
