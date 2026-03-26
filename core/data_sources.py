# -*- coding: utf-8 -*-
"""
多源資料 Fallback 模組
======================
當 FinLab API 額度用完時，自動切換到免費替代來源。

資料來源優先順序:
  OHLCV 價格:  FinLab -> yfinance
  三大法人:    FinLab -> TWSE OpenAPI
  基本面:      FinLab -> FinMind
  即時報價:    TWSE OpenAPI (直接使用)
  融資融券:    FinLab -> TWSE OpenAPI
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

import pandas as pd
import requests

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 內部快取 (source-level)
# ---------------------------------------------------------------------------
_source_cache: Dict[str, Any] = {}
_source_cache_ts: Dict[str, float] = {}
_SOURCE_CACHE_TTL = 300  # 5 分鐘

# TWSE rate limit: 記錄上次呼叫時間，確保間隔 >= 1 秒
_twse_last_call: float = 0.0

_TWSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


def _source_cached(key: str, ttl: int = _SOURCE_CACHE_TTL):
    """簡易快取裝飾器 (用 key prefix + 呼叫參數)"""
    if key in _source_cache:
        if time.time() - _source_cache_ts.get(key, 0) < ttl:
            return _source_cache[key]
    return None


def _set_source_cache(key: str, value: Any):
    _source_cache[key] = value
    _source_cache_ts[key] = time.time()


def _twse_throttle():
    """確保 TWSE API 呼叫間隔至少 1 秒"""
    global _twse_last_call
    elapsed = time.time() - _twse_last_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _twse_last_call = time.time()


# ===================================================================
# 1. yfinance -- OHLCV 價格
# ===================================================================

def _yfinance_ohlcv(stock_id: str, days: int) -> Optional[pd.DataFrame]:
    """
    透過 yfinance 取得台股 OHLCV。
    回傳 DataFrame: index=日期, columns=[open, high, low, close, volume]
    格式對齊 FinLab loader 回傳的結構 (單一股票的長條 DataFrame)。
    """
    try:
        import yfinance as yf
    except ImportError:
        _log.warning("yfinance 未安裝，無法使用 yfinance fallback")
        return None

    ticker_id = f"{stock_id}.TW"
    _log.info("[fallback] yfinance 下載 OHLCV: %s (days=%d)", ticker_id, days)

    try:
        # yfinance period 以日曆天計，交易日大約 *1.5
        calendar_days = int(days * 1.6) + 10
        df = yf.download(
            ticker_id,
            period=f"{calendar_days}d",
            auto_adjust=True,
            progress=False,
            timeout=15,
        )
        if df is None or df.empty:
            # 上櫃股票使用 .TWO
            ticker_id = f"{stock_id}.TWO"
            _log.info("[fallback] 嘗試 OTC 代號: %s", ticker_id)
            df = yf.download(
                ticker_id,
                period=f"{calendar_days}d",
                auto_adjust=True,
                progress=False,
                timeout=15,
            )

        if df is None or df.empty:
            _log.warning("[fallback] yfinance 無資料: %s", stock_id)
            return None

        # yfinance 可能回傳 MultiIndex columns (ticker as level)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        # 只保留需要的欄位，並取最後 days 筆
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[cols].tail(days)
        _log.info("[fallback] yfinance 成功: %s, %d 筆", stock_id, len(df))
        return df

    except Exception as e:
        _log.error("[fallback] yfinance 失敗 (%s): %s", stock_id, e)
        return None


# ===================================================================
# 2. TWSE OpenAPI -- 即時報價
# ===================================================================

def _twse_realtime(stock_id: str) -> Optional[Dict]:
    """
    TWSE 即時報價 (mis.twse.com.tw)
    回傳格式與 api_server.py /quote/realtime 端點一致。
    """
    cache_key = f"twse_realtime_{stock_id}"
    cached = _source_cached(cache_key, ttl=30)  # 即時報價快取 30 秒
    if cached is not None:
        return cached

    _twse_throttle()

    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_id}.tw"
    _log.info("[fallback] TWSE 即時報價: %s", stock_id)

    try:
        res = requests.get(url, headers=_TWSE_HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()

        if not data.get("msgArray"):
            # 嘗試 OTC
            url_otc = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=otc_{stock_id}.tw"
            res = requests.get(url_otc, headers=_TWSE_HEADERS, timeout=10)
            res.raise_for_status()
            data = res.json()

        if data.get("msgArray"):
            item = data["msgArray"][0]
            result = {
                "stock_id": stock_id,
                "name": item.get("n", ""),
                "price": _safe_float(item.get("z")),
                "open": _safe_float(item.get("o")),
                "high": _safe_float(item.get("h")),
                "low": _safe_float(item.get("l")),
                "volume": int(_safe_float(item.get("v")) or 0) * 1000,
                "yesterday_close": _safe_float(item.get("y")),
            }
            _set_source_cache(cache_key, result)
            _log.info("[fallback] TWSE 即時報價成功: %s price=%.2f",
                      stock_id, result["price"] or 0)
            return result

    except Exception as e:
        _log.error("[fallback] TWSE 即時報價失敗 (%s): %s", stock_id, e)

    return None


def _twse_realtime_batch(stock_ids: List[str]) -> List[Dict]:
    """批次取得 TWSE 即時報價 (一次最多 ~20 支效能較佳)"""
    cache_key = f"twse_realtime_batch_{'_'.join(sorted(stock_ids[:20]))}"
    cached = _source_cached(cache_key, ttl=30)
    if cached is not None:
        return cached

    _twse_throttle()

    # 組合查詢字串: tse_2330.tw|tse_2317.tw|...
    ex_ch_parts = [f"tse_{sid}.tw" for sid in stock_ids]
    ex_ch = "|".join(ex_ch_parts)
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"

    _log.info("[fallback] TWSE 批次即時報價: %d 支", len(stock_ids))

    try:
        res = requests.get(url, headers=_TWSE_HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()

        results = []
        found_ids = set()
        if data.get("msgArray"):
            for item in data["msgArray"]:
                sid = item.get("c", "")
                found_ids.add(sid)
                results.append({
                    "stock_id": sid,
                    "name": item.get("n", ""),
                    "price": _safe_float(item.get("z")),
                    "open": _safe_float(item.get("o")),
                    "high": _safe_float(item.get("h")),
                    "low": _safe_float(item.get("l")),
                    "volume": int(_safe_float(item.get("v")) or 0) * 1000,
                    "yesterday_close": _safe_float(item.get("y")),
                })

        # 未找到的可能是 OTC，逐一補查
        missing = [sid for sid in stock_ids if sid not in found_ids]
        for sid in missing[:10]:  # 最多補查 10 支
            single = _twse_realtime(sid)
            if single:
                results.append(single)

        _set_source_cache(cache_key, results)
        _log.info("[fallback] TWSE 批次報價成功: %d/%d", len(results), len(stock_ids))
        return results

    except Exception as e:
        _log.error("[fallback] TWSE 批次報價失敗: %s", e)

    return []


# ===================================================================
# 3. TWSE OpenAPI -- 三大法人
# ===================================================================

def _twse_institutional(stock_id: str, days: int = 5) -> Optional[Dict]:
    """
    TWSE 三大法人買賣超 (T86 API)
    回傳格式與 api_server.py /stock/{id}/chip 端點一致。
    """
    cache_key = f"twse_inst_{stock_id}_{days}"
    cached = _source_cached(cache_key)
    if cached is not None:
        return cached

    result = {"stock_id": stock_id}
    today = datetime.now()

    # 嘗試最近幾個交易日
    collected_days = 0
    foreign_daily = []
    trust_daily = []
    dealer_daily = []

    for i in range(days + 10):  # 多嘗試幾天以跳過非交易日
        if collected_days >= days:
            break

        date_obj = today - timedelta(days=i)
        date_str = date_obj.strftime("%Y%m%d")

        _twse_throttle()

        url = "https://www.twse.com.tw/fund/T86"
        _log.debug("[fallback] TWSE 三大法人: date=%s", date_str)

        try:
            res = requests.get(
                url,
                params={"response": "json", "date": date_str, "selectType": "ALLBUT0999"},
                headers=_TWSE_HEADERS,
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()

            if data.get("stat") != "OK" or "data" not in data:
                continue

            # 搜尋目標股票
            for row in data["data"]:
                sid = str(row[0]).strip().replace('"', '')
                if sid == stock_id:
                    collected_days += 1
                    d_str = date_obj.strftime("%Y-%m-%d")
                    # T86 欄位: 證券代號,證券名稱,外陸資買賣超股數(不含外資自營商),
                    #           投信買賣超股數, 自營商買賣超股數, ...
                    foreign_shares = _parse_twse_number(row[4]) if len(row) > 4 else 0
                    trust_shares = _parse_twse_number(row[5]) if len(row) > 5 else 0
                    dealer_shares = _parse_twse_number(row[6]) if len(row) > 6 else 0

                    foreign_daily.append({"date": d_str, "shares": int(foreign_shares)})
                    trust_daily.append({"date": d_str, "shares": int(trust_shares)})
                    dealer_daily.append({"date": d_str, "shares": int(dealer_shares)})
                    break

        except Exception as e:
            _log.debug("[fallback] TWSE T86 失敗 (date=%s): %s", date_str, e)
            continue

    if foreign_daily:
        result["外資"] = {
            "total_shares": sum(d["shares"] for d in foreign_daily),
            "daily": list(reversed(foreign_daily)),
        }
    if trust_daily:
        result["投信"] = {
            "total_shares": sum(d["shares"] for d in trust_daily),
            "daily": list(reversed(trust_daily)),
        }
    if dealer_daily:
        result["自營商"] = {
            "total_shares": sum(d["shares"] for d in dealer_daily),
            "daily": list(reversed(dealer_daily)),
        }

    if foreign_daily or trust_daily or dealer_daily:
        _set_source_cache(cache_key, result)
        _log.info("[fallback] TWSE 三大法人成功: %s, %d 天", stock_id, collected_days)
        return result

    return None


# ===================================================================
# 4. TWSE OpenAPI -- 融資融券
# ===================================================================

def _twse_margin_fallback(stock_id: str, days: int = 5) -> Optional[Dict]:
    """
    TWSE 融資融券 fallback。
    複用 core.twse_api 中已有的 fetch_stock_margin。
    回傳格式與 api_server.py /stock/{id}/chip 端點的 margin 部分一致。
    """
    cache_key = f"twse_margin_{stock_id}_{days}"
    cached = _source_cached(cache_key)
    if cached is not None:
        return cached

    try:
        from core.twse_api import fetch_stock_margin

        data = fetch_stock_margin(stock_id, retry_days=days + 5)
        if data:
            result = {
                "margin_buy": data.get("margin_buy", 0),
                "margin_sell": data.get("margin_sell", 0),
                "margin_ratio": data.get("margin_ratio", 0),
                "date": data.get("date", ""),
            }
            _set_source_cache(cache_key, result)
            _log.info("[fallback] TWSE 融資融券成功: %s", stock_id)
            return result
    except Exception as e:
        _log.error("[fallback] TWSE 融資融券失敗 (%s): %s", stock_id, e)

    return None


# ===================================================================
# 5. FinMind -- 基本面 PE/PB/殖利率
# ===================================================================

def _finmind_fundamentals(stock_id: str) -> Optional[Dict]:
    """
    FinMind 免費 API (10000 次/日) 取得 PE/PB/殖利率。
    回傳: {"pe_ratio": float, "pb_ratio": float, "dividend_yield": float}
    """
    cache_key = f"finmind_fund_{stock_id}"
    cached = _source_cached(cache_key, ttl=3600)  # 基本面快取 1 小時
    if cached is not None:
        return cached

    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    params = {
        "dataset": "TaiwanStockPER",
        "data_id": stock_id,
        "start_date": start_date,
    }

    _log.info("[fallback] FinMind 基本面: %s", stock_id)

    try:
        res = requests.get(url, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()

        if data.get("data"):
            latest = data["data"][-1]
            result = {
                "pe_ratio": _safe_float(latest.get("PER")),
                "pb_ratio": _safe_float(latest.get("PBR")),
                "dividend_yield": _safe_float(latest.get("dividend_yield")),
            }
            _set_source_cache(cache_key, result)
            _log.info("[fallback] FinMind 成功: %s PE=%.1f PB=%.2f",
                      stock_id,
                      result["pe_ratio"] or 0,
                      result["pb_ratio"] or 0)
            return result

    except Exception as e:
        _log.error("[fallback] FinMind 失敗 (%s): %s", stock_id, e)

    return None


# ===================================================================
# Utility
# ===================================================================

def _safe_float(val) -> Optional[float]:
    """安全轉換為 float，處理空值/非數字"""
    if val is None:
        return None
    try:
        f = float(val)
        if f == 0 and str(val).strip() in ("", "-", "--"):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _parse_twse_number(val) -> float:
    """解析 TWSE 數字字串 (含逗號/引號)"""
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", "").replace('"', '').strip())
    except (ValueError, TypeError):
        return 0.0


# ===================================================================
# MultiSourceDataProvider -- 主要對外介面
# ===================================================================

class MultiSourceDataProvider:
    """
    多源資料提供者 -- FinLab 優先，額度滿時自動 fallback。

    使用方式:
        from core.data_sources import MultiSourceDataProvider
        provider = MultiSourceDataProvider(loader)

        # 當 FinLab 額度超限時使用:
        ohlcv = provider.get_ohlcv("2330", days=120)
        fundamentals = provider.get_fundamentals("2330")
        chip = provider.get_institutional("2330", days=5)
        quote = provider.get_realtime_quote("2330")
        margin = provider.get_margin("2330")
    """

    def __init__(self, loader=None):
        """
        Parameters
        ----------
        loader : DataLoader, optional
            FinLab DataLoader 實例。若提供，會在 fallback 前先嘗試 FinLab。
        """
        self._loader = loader

    # ---------------------------------------------------------------
    # OHLCV
    # ---------------------------------------------------------------

    def get_ohlcv(self, stock_id: str, days: int = 120) -> Optional[Dict]:
        """
        取得 OHLCV 價格資料，回傳與 /stock/{id}/ohlcv 端點相同的格式。

        Fallback: FinLab -> yfinance
        """
        # 嘗試 yfinance (quota exceeded 時直接走這裡)
        df = _yfinance_ohlcv(stock_id, days)
        if df is not None and not df.empty:
            records = []
            for d, row in df.iterrows():
                records.append({
                    "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10],
                    "open": _safe_json_val(row.get("open")),
                    "high": _safe_json_val(row.get("high")),
                    "low": _safe_json_val(row.get("low")),
                    "close": _safe_json_val(row.get("close")),
                    "volume": _safe_json_val(row.get("volume")),
                })
            return {
                "stock_id": stock_id,
                "days": len(records),
                "data": records,
                "source": "yfinance",
            }

        _log.warning("[fallback] OHLCV 所有來源均失敗: %s", stock_id)
        return None

    # ---------------------------------------------------------------
    # 三大法人
    # ---------------------------------------------------------------

    def get_institutional(self, stock_id: str, days: int = 5) -> Optional[Dict]:
        """
        取得三大法人買賣超，回傳與 /stock/{id}/chip 端點相同的格式。

        Fallback: FinLab -> TWSE T86
        """
        result = _twse_institutional(stock_id, days)
        if result:
            result["source"] = "twse"
            return result

        _log.warning("[fallback] 三大法人所有來源均失敗: %s", stock_id)
        return None

    # ---------------------------------------------------------------
    # 基本面
    # ---------------------------------------------------------------

    def get_fundamentals(self, stock_id: str) -> Optional[Dict]:
        """
        取得基本面 PE/PB/殖利率。

        Fallback: FinLab -> FinMind
        """
        result = _finmind_fundamentals(stock_id)
        if result:
            result["source"] = "finmind"
            return result

        _log.warning("[fallback] 基本面所有來源均失敗: %s", stock_id)
        return None

    # ---------------------------------------------------------------
    # 即時報價
    # ---------------------------------------------------------------

    def get_realtime_quote(self, stock_id: str) -> Optional[Dict]:
        """
        取得即時報價 (直接使用 TWSE)。
        """
        result = _twse_realtime(stock_id)
        if result:
            result["source"] = "twse"
            return result
        return None

    def get_realtime_batch(self, stock_ids: List[str]) -> List[Dict]:
        """
        批次取得即時報價 (直接使用 TWSE)。
        """
        results = _twse_realtime_batch(stock_ids)
        for r in results:
            r["source"] = "twse"
        return results

    # ---------------------------------------------------------------
    # 融資融券
    # ---------------------------------------------------------------

    def get_margin(self, stock_id: str, days: int = 5) -> Optional[Dict]:
        """
        取得融資融券資料。

        Fallback: FinLab -> TWSE MI_MARGN
        """
        result = _twse_margin_fallback(stock_id, days)
        if result:
            result["source"] = "twse"
            return result

        _log.warning("[fallback] 融資融券所有來源均失敗: %s", stock_id)
        return None


# ===================================================================
# Helper -- JSON 安全值轉換
# ===================================================================

def _safe_json_val(val) -> Any:
    """將值轉為 JSON 安全的 Python 原生型別"""
    import math
    import numpy as np

    if val is None:
        return None
    if isinstance(val, (int,)):
        return int(val)
    if isinstance(val, (float,)):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, 2)
    if isinstance(val, (np.floating,)):
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return None
        return round(v, 2)
    if isinstance(val, (np.integer,)):
        return int(val)
    return val
