#!/usr/bin/env python3
"""
台股戰情中心 API Server
========================
提供 REST API 讓 OpenClaw 或其他外部系統串接查詢台股數據。

啟動方式:
    python api_server.py
    python api_server.py --host 0.0.0.0 --port 8000

API 文件:
    啟動後訪問 http://localhost:8000/docs
"""
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List


from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import pandas as pd
import numpy as np

from config import STRATEGY_PARAMS, TRADING_COSTS
from core.data_loader import DataLoader, get_data_summary, get_active_stocks
from core.indicators import calculate_rsi, calculate_macd, calculate_sma
from core.alerts import AlertEngine
from core.strategies.value import ValueStrategy
from core.strategies.growth import GrowthStrategy
from core.strategies.momentum import MomentumStrategy

# ─── 初始化 ─────────────────────────────────────────────
app = FastAPI(
    title="台股戰情中心 API",
    description="提供台股數據查詢、選股策略、警報等功能，供 OpenClaw 等外部系統串接",
    version="1.0.0",
)

import logging

logger = logging.getLogger(__name__)

# CORS 設定：從環境變數讀取允許的來源（逗號分隔），預設為 "*"
# 生產環境請設定 CORS_ORIGINS 為具體域名，例如：
#   CORS_ORIGINS=https://app.example.com,https://admin.example.com
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
# allow_origins=["*"] 搭配 allow_credentials=True 違反 CORS 規範，
# 使用萬用字元時必須停用 credentials。
_cors_allow_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key 驗證
# 生產環境必須設定 STOCK_API_KEY 環境變數，否則所有端點將無需認證即可存取。
API_KEY = os.getenv("STOCK_API_KEY", "")
security = HTTPBearer(auto_error=False)


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """驗證 API Key（若有設定）。

    未設定 STOCK_API_KEY 時允許所有請求通過，適合本地開發。
    生產環境務必設定 STOCK_API_KEY。
    """
    if not API_KEY:
        # 記錄每次未認證存取，便於在日誌中識別生產環境的設定疏漏
        logger.debug("API_KEY 未設定，跳過認證（本地開發模式）")
        return True
    if not credentials or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="無效的 API Key")
    return True


# 全域 DataLoader
loader = DataLoader()


@app.on_event("startup")
async def _startup_security_check():
    """啟動時檢查安全設定並記錄警告。"""
    if not API_KEY:
        logger.warning(
            "STOCK_API_KEY 環境變數未設定——所有 API 端點無需認證即可存取。"
            " 生產環境請務必設定此變數。"
        )
    if not _cors_allow_credentials:
        logger.warning(
            "CORS_ORIGINS 未設定或為 '*'，已停用 allow_credentials。"
            " 生產環境請設定 CORS_ORIGINS 為具體域名。"
        )


# ─── 工具函數 ───────────────────────────────────────────
def _safe_json(obj):
    """安全轉換 numpy/pandas 物件為 JSON 可序列化格式"""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return round(float(obj), 4) if not np.isnan(obj) else None
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    return obj


def _get_stock_latest(stock_id: str, days: int = 1):
    """取得個股最新數據"""
    close = loader.get("close")
    if stock_id not in close.columns:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    data = close[stock_id].dropna().tail(days)
    return data


# ─── API 端點 ───────────────────────────────────────────

@app.get("/", tags=["系統"])
async def root():
    """API 根目錄"""
    return {
        "name": "台股戰情中心 API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/market/summary",
            "/stock/{stock_id}",
            "/stock/{stock_id}/technical",
            "/stock/{stock_id}/chip",
            "/strategy/{strategy_type}",
            "/alerts/check",
            "/morning-report",
            "/screener",
        ],
    }


# ─── 市場概覽 ───────────────────────────────────────────

@app.get("/market/summary", tags=["市場"], dependencies=[Depends(verify_api_key)])
async def market_summary():
    """
    市場總覽 - 取得大盤指數、上漲/下跌家數等摘要資訊。
    OpenClaw 可用此端點取得每日市場概況。
    """
    summary = get_data_summary()
    if "error" in summary:
        raise HTTPException(status_code=500, detail=summary["error"])

    # 計算漲跌家數
    close = loader.get("close")
    active = get_active_stocks()

    latest = close[active].iloc[-1]
    prev = close[active].iloc[-2]
    changes = (latest - prev) / prev * 100

    up_count = int((changes > 0).sum())
    down_count = int((changes < 0).sum())
    flat_count = int((changes == 0).sum())

    # 漲幅/跌幅排行
    top_gainers = changes.nlargest(10)
    top_losers = changes.nsmallest(10)

    return {
        "date": summary.get("latest_date"),
        "taiex_index": _safe_json(summary.get("taiex_index")),
        "taiex_change": _safe_json(summary.get("taiex_change")),
        "total_stocks": summary.get("total_stocks"),
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "top_gainers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_gainers.items()
        ],
        "top_losers": [
            {"stock_id": sid, "change_pct": round(float(pct), 2)}
            for sid, pct in top_losers.items()
        ],
    }


# ─── 個股查詢 ───────────────────────────────────────────

@app.get("/stock/{stock_id}", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_info(
    stock_id: str,
    days: int = Query(default=5, description="取得最近 N 天的資料", ge=1, le=250),
):
    """
    個股基本資訊與近期行情。
    範例: /stock/2330?days=10
    """
    close = loader.get("close")
    if stock_id not in close.columns:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    # 價格
    price_data = close[stock_id].dropna().tail(days)
    latest_price = float(price_data.iloc[-1])
    prev_price = float(price_data.iloc[-2]) if len(price_data) >= 2 else latest_price
    change_pct = round((latest_price - prev_price) / prev_price * 100, 2)

    # 本益比、殖利率
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

    # 月營收
    rev_yoy = None
    try:
        yoy_df = loader.get("revenue_yoy")
        if stock_id in yoy_df.columns:
            rev_yoy = _safe_json(yoy_df[stock_id].dropna().iloc[-1])
    except Exception:
        pass

    return {
        "stock_id": stock_id,
        "latest_price": round(latest_price, 2),
        "change_pct": change_pct,
        "date": price_data.index[-1].strftime("%Y-%m-%d"),
        "pe_ratio": pe,
        "pb_ratio": pb,
        "dividend_yield": dy,
        "revenue_yoy": rev_yoy,
        "price_history": [
            {
                "date": d.strftime("%Y-%m-%d"),
                "price": round(float(p), 2),
            }
            for d, p in price_data.items()
        ],
    }


@app.get("/stock/{stock_id}/technical", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_technical(stock_id: str):
    """
    個股技術指標：RSI、MACD、均線。
    範例: /stock/2330/technical
    """
    close = loader.get("close")
    if stock_id not in close.columns:
        raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

    series = close[stock_id].dropna()

    # RSI
    rsi_14 = calculate_rsi(series, period=14)
    latest_rsi = _safe_json(rsi_14.iloc[-1]) if len(rsi_14) > 0 else None

    # MACD
    macd_line, signal_line, histogram = calculate_macd(series)
    latest_macd = _safe_json(macd_line.iloc[-1]) if len(macd_line) > 0 else None
    latest_signal = _safe_json(signal_line.iloc[-1]) if len(signal_line) > 0 else None

    # 均線
    sma_5 = calculate_sma(series, period=5)
    sma_20 = calculate_sma(series, period=20)
    sma_60 = calculate_sma(series, period=60)

    latest_price = float(series.iloc[-1])

    # 趨勢判斷
    trend = "盤整"
    if sma_5.iloc[-1] > sma_20.iloc[-1] > sma_60.iloc[-1]:
        trend = "多頭排列"
    elif sma_5.iloc[-1] < sma_20.iloc[-1] < sma_60.iloc[-1]:
        trend = "空頭排列"

    # RSI 訊號
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


@app.get("/stock/{stock_id}/chip", tags=["個股"], dependencies=[Depends(verify_api_key)])
async def stock_chip(
    stock_id: str,
    days: int = Query(default=5, description="最近 N 天", ge=1, le=60),
):
    """
    個股籌碼分析：三大法人買賣超、外資持股比率、融資融券。
    範例: /stock/2330/chip?days=10
    """
    result = {"stock_id": stock_id}

    # 三大法人
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

    # 外資持股比率
    try:
        fh = loader.get("foreign_holding")
        if stock_id in fh.columns:
            latest = fh[stock_id].dropna().iloc[-1]
            result["foreign_holding_pct"] = _safe_json(latest)
    except Exception:
        pass

    # 融資融券
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


# ─── 選股策略 ───────────────────────────────────────────

@app.get("/strategy/{strategy_type}", tags=["策略"], dependencies=[Depends(verify_api_key)])
async def run_strategy(
    strategy_type: str,
    preset: str = Query(default="standard", description="預設組合: conservative/standard/aggressive"),
    top_n: int = Query(default=20, description="回傳前 N 檔", ge=1, le=50),
):
    """
    執行選股策略，回傳符合條件的股票清單。

    策略類型:
    - value: 價值投資（低本益比、高殖利率）
    - growth: 成長投資（營收年增率高）
    - momentum: 動能投資（突破、量能）

    範例: /strategy/value?preset=conservative&top_n=10
    """
    if strategy_type not in ("value", "growth", "momentum"):
        raise HTTPException(status_code=400, detail="策略類型需為 value/growth/momentum")

    from config import STRATEGY_PRESETS

    active = get_active_stocks()
    close = loader.get("close")
    latest_prices = close[active].iloc[-1]

    # 根據 preset 取得對應策略參數，並實例化 Strategy 類別
    preset_params = STRATEGY_PRESETS[strategy_type].get(
        preset, STRATEGY_PRESETS[strategy_type]["standard"]
    )["params"]

    results = []

    if strategy_type == "value":
        pe_df = loader.get("pe_ratio")
        pb_df = loader.get("pb_ratio")
        dy_df = loader.get("dividend_yield")

        strategy = ValueStrategy(params=preset_params)
        data = {"pe_ratio": pe_df, "pb_ratio": pb_df, "dividend_yield": dy_df}
        matched = set(strategy.filter(data))

        # 提取 API 回應所需的具體指標數值
        for sid in matched:
            try:
                pe = pe_df[sid].dropna().iloc[-1] if sid in pe_df.columns else None
                pb = pb_df[sid].dropna().iloc[-1] if sid in pb_df.columns else None
                dy = dy_df[sid].dropna().iloc[-1] if sid in dy_df.columns else None
                if pe is None or pb is None or dy is None:
                    continue
                results.append({
                    "stock_id": sid,
                    "price": round(float(latest_prices.get(sid, 0)), 2),
                    "pe_ratio": round(float(pe), 2),
                    "pb_ratio": round(float(pb), 2),
                    "dividend_yield": round(float(dy), 2),
                })
            except (IndexError, KeyError):
                continue

        results.sort(key=lambda x: x["dividend_yield"], reverse=True)

    elif strategy_type == "growth":
        yoy_df = loader.get("revenue_yoy")
        mom_df = loader.get("revenue_mom")

        strategy = GrowthStrategy(params=preset_params)
        data = {"revenue_yoy": yoy_df, "revenue_mom": mom_df}
        matched = set(strategy.filter(data))

        for sid in matched:
            try:
                yoy = yoy_df[sid].dropna().iloc[-1] if sid in yoy_df.columns else None
                mom = mom_df[sid].dropna().iloc[-1] if sid in mom_df.columns else None
                if yoy is None or mom is None:
                    continue
                results.append({
                    "stock_id": sid,
                    "price": round(float(latest_prices.get(sid, 0)), 2),
                    "revenue_yoy": round(float(yoy), 2),
                    "revenue_mom": round(float(mom), 2),
                })
            except (IndexError, KeyError):
                continue

        results.sort(key=lambda x: x["revenue_yoy"], reverse=True)

    elif strategy_type == "momentum":
        volume_df = loader.get("volume")

        # MomentumStrategy 使用 volume_ratio_min 而非 volume_ratio，需做鍵名對應
        momentum_params = dict(preset_params)
        if "volume_ratio" in momentum_params and "volume_ratio_min" not in momentum_params:
            momentum_params["volume_ratio_min"] = momentum_params.pop("volume_ratio")

        strategy = MomentumStrategy(params=momentum_params)
        data = {"close": close, "volume": volume_df}
        matched = set(strategy.filter(data))

        breakout_days = momentum_params.get("breakout_days", 20)

        for sid in matched:
            try:
                price_series = close[sid].dropna()
                vol_series = volume_df[sid].dropna()
                if len(price_series) < breakout_days + 1 or len(vol_series) < 21:
                    continue

                latest_price = float(price_series.iloc[-1])
                high_n = float(price_series.tail(breakout_days + 1).iloc[:-1].max())
                avg_vol = float(vol_series.tail(21).iloc[:-1].mean())
                latest_vol = float(vol_series.iloc[-1])
                vol_ratio = latest_vol / avg_vol if avg_vol > 0 else 0

                rsi_series = calculate_rsi(price_series, period=14)
                latest_rsi = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 else 50

                results.append({
                    "stock_id": sid,
                    "price": round(latest_price, 2),
                    "volume_ratio": round(vol_ratio, 2),
                    "rsi": round(latest_rsi, 2),
                    "breakout_high": round(high_n, 2),
                })
            except (IndexError, KeyError):
                continue

        results.sort(key=lambda x: x["volume_ratio"], reverse=True)

    return {
        "strategy": strategy_type,
        "preset": preset,
        "date": close.index[-1].strftime("%Y-%m-%d"),
        "total_matches": len(results),
        "stocks": results[:top_n],
    }


# ─── 自訂篩選 ───────────────────────────────────────────

@app.get("/screener", tags=["策略"], dependencies=[Depends(verify_api_key)])
async def screener(
    pe_max: Optional[float] = Query(default=None, description="本益比上限"),
    pe_min: Optional[float] = Query(default=None, description="本益比下限"),
    pb_max: Optional[float] = Query(default=None, description="股價淨值比上限"),
    dy_min: Optional[float] = Query(default=None, description="殖利率下限 (%)"),
    yoy_min: Optional[float] = Query(default=None, description="營收年增率下限 (%)"),
    rsi_max: Optional[float] = Query(default=None, description="RSI 上限"),
    rsi_min: Optional[float] = Query(default=None, description="RSI 下限"),
    top_n: int = Query(default=20, ge=1, le=100),
):
    """
    自訂條件篩選股票。可組合多個條件。
    範例: /screener?pe_max=15&dy_min=5&top_n=10
    """
    active = get_active_stocks()
    close = loader.get("close")
    candidates = set(active)

    if pe_max is not None or pe_min is not None:
        pe_df = loader.get("pe_ratio")
        for sid in list(candidates):
            if sid not in pe_df.columns:
                candidates.discard(sid)
                continue
            val = pe_df[sid].dropna().iloc[-1] if not pe_df[sid].dropna().empty else None
            if val is None or np.isnan(val):
                candidates.discard(sid)
                continue
            if pe_max is not None and val > pe_max:
                candidates.discard(sid)
            if pe_min is not None and val < pe_min:
                candidates.discard(sid)

    if pb_max is not None:
        pb_df = loader.get("pb_ratio")
        for sid in list(candidates):
            if sid not in pb_df.columns:
                candidates.discard(sid)
                continue
            val = pb_df[sid].dropna().iloc[-1] if not pb_df[sid].dropna().empty else None
            if val is None or np.isnan(val) or val > pb_max:
                candidates.discard(sid)

    if dy_min is not None:
        dy_df = loader.get("dividend_yield")
        for sid in list(candidates):
            if sid not in dy_df.columns:
                candidates.discard(sid)
                continue
            val = dy_df[sid].dropna().iloc[-1] if not dy_df[sid].dropna().empty else None
            if val is None or np.isnan(val) or val < dy_min:
                candidates.discard(sid)

    if yoy_min is not None:
        yoy_df = loader.get("revenue_yoy")
        for sid in list(candidates):
            if sid not in yoy_df.columns:
                candidates.discard(sid)
                continue
            val = yoy_df[sid].dropna().iloc[-1] if not yoy_df[sid].dropna().empty else None
            if val is None or np.isnan(val) or val < yoy_min:
                candidates.discard(sid)

    if rsi_max is not None or rsi_min is not None:
        # 向量化：一次對所有候選股票計算 RSI，避免逐股迴圈
        valid_candidates = [sid for sid in candidates if sid in close.columns]
        if valid_candidates:
            rsi_all = calculate_rsi(close[valid_candidates], period=14)
            latest_rsi = rsi_all.iloc[-1]
            for sid in list(candidates):
                if sid not in latest_rsi.index or pd.isna(latest_rsi[sid]):
                    candidates.discard(sid)
                    continue
                val = float(latest_rsi[sid])
                if rsi_max is not None and val > rsi_max:
                    candidates.discard(sid)
                if rsi_min is not None and val < rsi_min:
                    candidates.discard(sid)
        else:
            candidates.clear()

    # 組裝結果
    results = []
    for sid in list(candidates)[:top_n]:
        price = close[sid].dropna().iloc[-1] if sid in close.columns else 0
        results.append({"stock_id": sid, "price": round(float(price), 2)})

    return {
        "date": close.index[-1].strftime("%Y-%m-%d"),
        "filters_applied": {
            k: v for k, v in {
                "pe_max": pe_max, "pe_min": pe_min, "pb_max": pb_max,
                "dy_min": dy_min, "yoy_min": yoy_min,
                "rsi_max": rsi_max, "rsi_min": rsi_min,
            }.items() if v is not None
        },
        "total_matches": len(candidates),
        "stocks": results,
    }


# ─── 警報 ───────────────────────────────────────────────

@app.get("/alerts/check", tags=["警報"], dependencies=[Depends(verify_api_key)])
async def check_alerts():
    """
    檢查所有已設定的警報，回傳觸發的項目。
    """
    try:
        engine = AlertEngine()
        close = loader.get("close")
        volume = loader.get("volume")

        high = loader.get("high")
        low = loader.get("low")
        data = {"close": close, "volume": volume, "high": high, "low": low}
        triggered = engine.check_all_alerts(data)
        return {
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "triggered_count": len(triggered),
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "stock_id": a.stock_id,
                    "type": a.alert_type,
                    "current_value": _safe_json(a.current_value),
                    "target_value": _safe_json(a.target_value),
                    "message": a.message,
                }
                for a in triggered
            ],
        }
    except Exception as e:
        return {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "triggered_count": 0, "alerts": [], "note": str(e)}


# ─── 晨報 ───────────────────────────────────────────────

@app.get("/morning-report", tags=["報告"], dependencies=[Depends(verify_api_key)])
async def morning_report():
    """
    產生每日晨報摘要，包含市場概況、漲跌排行、策略選股結果。
    OpenClaw 可每日早上自動呼叫此端點取得晨報。
    """
    close = loader.get("close")
    active = get_active_stocks()

    # 漲跌排行
    latest = close[active].iloc[-1]
    prev = close[active].iloc[-2]
    changes = ((latest - prev) / prev * 100).dropna()

    top_gainers = changes.nlargest(5)
    top_losers = changes.nsmallest(5)

    # 快速跑三個策略
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

    return {
        "date": summary.get("latest_date"),
        "taiex_index": _safe_json(summary.get("taiex_index")),
        "taiex_change": _safe_json(summary.get("taiex_change")),
        "market": {
            "up": int((changes > 0).sum()),
            "down": int((changes < 0).sum()),
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


# ─── 啟動 ───────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台股戰情中心 API Server")
    parser.add_argument("--host", default="0.0.0.0", help="綁定 Host (預設 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="綁定 Port (預設 8000)")
    parser.add_argument("--reload", action="store_true", help="開發模式 (自動重載)")

    args = parser.parse_args()

    print(f"🚀 台股戰情中心 API 啟動中...")
    print(f"📡 http://{args.host}:{args.port}")
    print(f"📖 API 文件: http://{args.host}:{args.port}/docs")
    print(f"🔑 API Key: {'已設定' if API_KEY else '未設定 (開放存取)'}")

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
