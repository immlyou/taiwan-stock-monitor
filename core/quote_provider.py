"""Normalized stock quote providers with live-first fallback.

The rest of the application talks only to :class:`QuoteService`.  Provider
specific payloads and failures stay behind the ``get_quotes`` adapter seam.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as datetime_time
from typing import Any, Dict, List, Optional, Protocol, Sequence

import requests

from core.timeutils import TAIPEI_TZ, now_taipei


logger = logging.getLogger(__name__)


class QuoteAdapter(Protocol):
    """Public seam implemented by each quote source."""

    def get_quotes(self, stock_ids: List[str]) -> List[dict]:
        ...


def taiwan_market_state(now: Optional[datetime] = None) -> str:
    """Return ``preopen``, ``trading`` or ``closed`` in Taiwan time."""
    current = now or now_taipei()
    if current.tzinfo is None:
        current = current.replace(tzinfo=TAIPEI_TZ)
    else:
        current = current.astimezone(TAIPEI_TZ)
    if current.weekday() >= 5:
        return "closed"
    local_time = current.time().replace(tzinfo=None)
    if local_time < datetime_time(9, 0):
        return "preopen"
    if local_time <= datetime_time(13, 30):
        return "trading"
    return "closed"


def _number(value: Any) -> Optional[float]:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _rounded(value: Optional[float]) -> Optional[float]:
    return round(value, 2) if value is not None else None


def _timestamp_iso(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
        if numeric > 10**14:
            numeric /= 1_000_000
        elif numeric > 10**11:
            numeric /= 1_000
        return datetime.fromtimestamp(numeric, TAIPEI_TZ).isoformat()
    except (TypeError, ValueError, OSError):
        text = str(value)
        return text or None


def _live_freshness(state: str) -> str:
    if state == "trading":
        return "realtime"
    if state == "preopen":
        return "previous_close"
    return "close"


def _live_note(source_label: str, state: str) -> str:
    if state == "trading":
        return f"{source_label} 盤中即時報價"
    if state == "preopen":
        return f"{source_label} 盤前最新報價"
    return f"{source_label} 最近一筆報價（目前休市）"


class FugleQuoteAdapter:
    """Fugle MarketData intraday quote HTTP adapter."""

    DEFAULT_BASE_URL = "https://api.fugle.tw/marketdata/v1.0/stock"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 5.0,
        max_workers: int = 5,
        max_calls_per_minute: Optional[int] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("FUGLE_MARKETDATA_API_KEY", "")
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_workers = max_workers
        if max_calls_per_minute is None:
            try:
                max_calls_per_minute = int(os.getenv("FUGLE_MAX_CALLS_PER_MINUTE", "55"))
            except ValueError:
                max_calls_per_minute = 55
        self.max_calls_per_minute = max(1, max_calls_per_minute)
        self._request_times = deque()  # type: deque[float]
        self._rate_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip())

    def get_quotes(self, stock_ids: List[str]) -> List[dict]:
        if not self.enabled or not stock_ids:
            return []
        workers = max(1, min(self.max_workers, len(stock_ids)))
        results: Dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fugle-quote") as executor:
            futures = {executor.submit(self._fetch_quote, sid): sid for sid in stock_ids}
            for future in as_completed(futures):
                sid = futures[future]
                try:
                    item = future.result()
                    if item:
                        results[sid] = item
                except Exception as exc:
                    logger.warning("Fugle quote failed for %s: %s", sid, exc)
        return [results[sid] for sid in stock_ids if sid in results]

    def _fetch_quote(self, stock_id: str) -> Optional[dict]:
        if not self._reserve_request():
            logger.info("Fugle minute budget reached; delegating %s to TWSE", stock_id)
            return None
        response = requests.get(
            f"{self.base_url}/intraday/quote/{stock_id}",
            headers={"X-API-KEY": self.api_key, "Accept": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        price = _number(payload.get("lastPrice"))
        if price is None:
            price = _number(payload.get("closePrice"))
        prev_close = _number(payload.get("previousClose"))
        if prev_close is None:
            prev_close = _number(payload.get("referencePrice"))
        if price is None:
            price = prev_close
        if price is None:
            return None

        state = taiwan_market_state()
        change = price - prev_close if prev_close is not None else _number(payload.get("change"))
        change_pct = (
            change / prev_close * 100
            if change is not None and prev_close not in (None, 0)
            else _number(payload.get("changePercent")) or 0.0
        )
        total = payload.get("total") or {}
        volume = _number(total.get("tradeVolume"))
        amount = _number(total.get("tradeValue"))
        timestamp = _timestamp_iso(payload.get("lastUpdated"))
        if timestamp is None:
            timestamp = (payload.get("lastTrade") or {}).get("time")

        return {
            "stock_id": str(payload.get("symbol") or stock_id),
            "name": payload.get("name") or "",
            "price": _rounded(price),
            "prev_close": _rounded(prev_close if prev_close is not None else price),
            "change": _rounded(change if change is not None else 0.0),
            "change_pct": round(change_pct, 2),
            "open": _rounded(_number(payload.get("openPrice"))),
            "high": _rounded(_number(payload.get("highPrice"))),
            "low": _rounded(_number(payload.get("lowPrice"))),
            "volume": int(volume) if volume is not None else None,
            "amount": int(amount) if amount is not None else None,
            "date": str(payload.get("date") or now_taipei().date()),
            "timestamp": timestamp,
            "source": "fugle",
            "is_realtime": state == "trading",
            "market_state": state,
            "freshness": _live_freshness(state),
            "note": _live_note("Fugle", state),
        }

    def _reserve_request(self) -> bool:
        """Reserve a Fugle call without sleeping; overflow falls through to TWSE."""
        now = time.monotonic()
        with self._rate_lock:
            while self._request_times and now - self._request_times[0] >= 60:
                self._request_times.popleft()
            if len(self._request_times) >= self.max_calls_per_minute:
                return False
            self._request_times.append(now)
            return True


class TwseQuoteAdapter:
    """Normalize the existing TWSE MIS batch provider."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    def get_quotes(self, stock_ids: List[str]) -> List[dict]:
        if not stock_ids:
            return []
        raw_quotes = self.provider.get_realtime_batch(stock_ids) or []
        state = taiwan_market_state()
        results = []
        for raw in raw_quotes:
            stock_id = str(raw.get("stock_id") or "")
            price = _number(raw.get("price"))
            prev_close = _number(raw.get("yesterday_close"))
            if price is None:
                price = prev_close
            if not stock_id or price is None:
                continue
            change = price - prev_close if prev_close is not None else 0.0
            change_pct = change / prev_close * 100 if prev_close not in (None, 0) else 0.0
            volume = _number(raw.get("volume"))
            amount = price * volume if volume is not None else None
            results.append({
                "stock_id": stock_id,
                "name": raw.get("name") or "",
                "price": _rounded(price),
                "prev_close": _rounded(prev_close if prev_close is not None else price),
                "change": _rounded(change),
                "change_pct": round(change_pct, 2),
                "open": _rounded(_number(raw.get("open"))),
                "high": _rounded(_number(raw.get("high"))),
                "low": _rounded(_number(raw.get("low"))),
                "volume": int(volume) if volume is not None else None,
                "amount": int(amount) if amount is not None else None,
                "date": str(now_taipei().date()),
                "timestamp": raw.get("timestamp") or now_taipei().isoformat(),
                "source": "twse",
                "is_realtime": state == "trading",
                "market_state": state,
                "freshness": _live_freshness(state),
                "note": _live_note("TWSE", state),
            })
        return results


class FinLabCloseQuoteAdapter:
    """Normalize FinLab daily OHLCV as the last-resort close quote."""

    def __init__(self, loader: Any) -> None:
        self.loader = loader

    def get_quotes(self, stock_ids: List[str]) -> List[dict]:
        if not stock_ids:
            return []
        close = self.loader.get("close")
        if close is None or close.empty:
            return []
        optional_frames: Dict[str, Any] = {}
        for key in ("open", "high", "low", "volume"):
            try:
                optional_frames[key] = self.loader.get(key)
            except Exception:
                optional_frames[key] = None

        results = []
        for stock_id in stock_ids:
            if stock_id not in close.columns:
                continue
            series = close[stock_id].dropna()
            if series.empty:
                continue
            price = float(series.iloc[-1])
            prev_close = float(series.iloc[-2]) if len(series) >= 2 else price
            date = series.index[-1].strftime("%Y-%m-%d")

            def latest_value(key: str) -> Optional[float]:
                frame = optional_frames.get(key)
                if frame is None or stock_id not in frame.columns:
                    return None
                values = frame[stock_id].dropna()
                return float(values.iloc[-1]) if not values.empty else None

            volume = latest_value("volume")
            change = price - prev_close
            results.append({
                "stock_id": stock_id,
                "name": "",
                "price": round(price, 2),
                "prev_close": round(prev_close, 2),
                "change": round(change, 2),
                "change_pct": round(change / prev_close * 100, 2) if prev_close else 0.0,
                "open": _rounded(latest_value("open")),
                "high": _rounded(latest_value("high")),
                "low": _rounded(latest_value("low")),
                "volume": int(volume) if volume is not None else None,
                "amount": int(volume * price) if volume is not None else None,
                "date": date,
                "timestamp": None,
                "source": "finlab",
                "is_realtime": False,
                "market_state": "closed",
                "freshness": "close",
                "note": "FinLab 最新交易日收盤價",
            })
        return results


class QuoteService:
    """Resolve each requested symbol from live providers, then daily close."""

    def __init__(
        self,
        live_adapters: Sequence[QuoteAdapter],
        fallback_adapter: QuoteAdapter,
        cache_ttl: float = 15.0,
    ) -> None:
        self.live_adapters = list(live_adapters)
        self.fallback_adapter = fallback_adapter
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.RLock()
        self._resolve_lock = threading.Lock()

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def get_quote(self, stock_id: str) -> Optional[dict]:
        quotes = self.get_quotes([stock_id])
        return quotes[0] if quotes else None

    def get_quotes(self, stock_ids: List[str]) -> List[dict]:
        requested = list(dict.fromkeys(str(sid).strip().upper() for sid in stock_ids if str(sid).strip()))
        if not requested:
            return []

        resolved = self._read_cache(requested)
        if len(resolved) == len(requested):
            return [resolved[sid] for sid in requested]

        # Recheck after acquiring the single-flight lock: another page may have
        # resolved the same symbols while this request was waiting.
        with self._resolve_lock:
            resolved.update(self._read_cache(requested))
            remaining = [sid for sid in requested if sid not in resolved]

            for adapter in self.live_adapters:
                if not remaining:
                    break
                self._fill_from_adapter(adapter, remaining, resolved)
                remaining = [sid for sid in remaining if sid not in resolved]

            if remaining:
                self._fill_from_adapter(self.fallback_adapter, remaining, resolved)

            if self.cache_ttl > 0:
                now = time.monotonic()
                with self._lock:
                    for stock_id, item in resolved.items():
                        self._cache[stock_id] = (now, dict(item))
        return [resolved[sid] for sid in requested if sid in resolved]

    def _read_cache(self, stock_ids: List[str]) -> Dict[str, dict]:
        if self.cache_ttl <= 0:
            return {}
        now = time.monotonic()
        resolved: Dict[str, dict] = {}
        with self._lock:
            for stock_id in stock_ids:
                cached = self._cache.get(stock_id)
                if cached and now - cached[0] < self.cache_ttl:
                    resolved[stock_id] = dict(cached[1])
        return resolved

    @staticmethod
    def _fill_from_adapter(adapter: QuoteAdapter, stock_ids: List[str], resolved: Dict[str, dict]) -> None:
        try:
            quotes = adapter.get_quotes(list(stock_ids))
        except Exception as exc:
            logger.warning("Quote provider %s failed: %s", adapter.__class__.__name__, exc)
            return
        allowed = set(stock_ids)
        for quote in quotes:
            stock_id = str(quote.get("stock_id") or "")
            if stock_id in allowed and quote.get("price") is not None:
                resolved[stock_id] = quote
