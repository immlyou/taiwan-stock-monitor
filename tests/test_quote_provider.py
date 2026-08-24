"""即時報價供應鏈的公開 Adapter / Service 契約。"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import pandas as pd

from core.quote_provider import (
    FinLabCloseQuoteAdapter,
    FugleQuoteAdapter,
    QuoteService,
    TwseQuoteAdapter,
)


class FakeQuoteAdapter:
    def __init__(self, quotes: Optional[Dict[str, dict]] = None, error: Optional[Exception] = None):
        self.quotes = quotes or {}
        self.error = error
        self.calls: List[List[str]] = []

    def get_quotes(self, stock_ids: List[str]) -> List[dict]:
        self.calls.append(stock_ids)
        if self.error:
            raise self.error
        return [self.quotes[sid] for sid in stock_ids if sid in self.quotes]


def quote(stock_id: str, price: float, source: str) -> dict:
    return {
        "stock_id": stock_id,
        "price": price,
        "prev_close": price - 1,
        "change": 1,
        "change_pct": round(100 / (price - 1), 2),
        "source": source,
        "is_realtime": source != "finlab",
        "market_state": "trading" if source != "finlab" else "closed",
        "freshness": "realtime" if source != "finlab" else "close",
    }


def test_service_uses_fugle_first_and_only_asks_twse_for_missing_symbols():
    fugle = FakeQuoteAdapter({"2330": quote("2330", 101, "fugle")})
    twse = FakeQuoteAdapter({"2317": quote("2317", 202, "twse")})
    finlab = FakeQuoteAdapter()
    service = QuoteService([fugle, twse], finlab, cache_ttl=0)

    result = service.get_quotes(["2330", "2317"])

    assert [(item["stock_id"], item["source"]) for item in result] == [
        ("2330", "fugle"),
        ("2317", "twse"),
    ]
    assert fugle.calls == [["2330", "2317"]]
    assert twse.calls == [["2317"]]
    assert finlab.calls == []


def test_service_survives_live_provider_errors_and_falls_back_to_finlab_close():
    fugle = FakeQuoteAdapter(error=TimeoutError("fugle timeout"))
    twse = FakeQuoteAdapter(error=ConnectionError("twse unavailable"))
    finlab = FakeQuoteAdapter({"2330": quote("2330", 99, "finlab")})
    service = QuoteService([fugle, twse], finlab, cache_ttl=0)

    result = service.get_quotes(["2330"])

    assert result == [quote("2330", 99, "finlab")]
    assert finlab.calls == [["2330"]]


def test_finlab_adapter_normalizes_daily_ohlcv_as_a_close_quote():
    dates = pd.to_datetime(["2026-08-20", "2026-08-21"])
    datasets = {
        "close": pd.DataFrame({"2330": [100.0, 103.0]}, index=dates),
        "open": pd.DataFrame({"2330": [99.0, 101.0]}, index=dates),
        "high": pd.DataFrame({"2330": [102.0, 105.0]}, index=dates),
        "low": pd.DataFrame({"2330": [98.0, 100.0]}, index=dates),
        "volume": pd.DataFrame({"2330": [1000, 2000]}, index=dates),
    }

    class Loader:
        def get(self, key: str):
            return datasets[key]

    result = FinLabCloseQuoteAdapter(Loader()).get_quotes(["2330", "9999"])

    assert len(result) == 1
    assert result[0] == {
        "stock_id": "2330",
        "name": "",
        "price": 103.0,
        "prev_close": 100.0,
        "change": 3.0,
        "change_pct": 3.0,
        "open": 101.0,
        "high": 105.0,
        "low": 100.0,
        "volume": 2000,
        "amount": 206000,
        "date": "2026-08-21",
        "timestamp": None,
        "source": "finlab",
        "is_realtime": False,
        "market_state": "closed",
        "freshness": "close",
        "note": "FinLab 最新交易日收盤價",
    }


def test_fugle_adapter_normalizes_intraday_payload(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "date": "2026-08-24",
                "symbol": "2330",
                "name": "台積電",
                "previousClose": 118,
                "openPrice": 119,
                "highPrice": 123,
                "lowPrice": 117.5,
                "lastPrice": 121,
                "lastUpdated": 1787536800000000,
                "total": {"tradeVolume": 5000, "tradeValue": 605000},
            }

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("core.quote_provider.requests.get", fake_get)
    monkeypatch.setattr("core.quote_provider.taiwan_market_state", lambda: "trading")

    result = FugleQuoteAdapter(api_key="secret", max_workers=1).get_quotes(["2330"])[0]

    assert calls[0][0].endswith("/intraday/quote/2330")
    assert calls[0][1]["headers"]["X-API-KEY"] == "secret"
    assert result["price"] == 121
    assert result["change_pct"] == 2.54
    assert result["volume"] == 5000
    assert result["amount"] == 605000
    assert result["source"] == "fugle"
    assert result["is_realtime"] is True


def test_twse_adapter_uses_previous_close_when_preopen_has_no_last_price(monkeypatch):
    class Provider:
        def get_realtime_batch(self, stock_ids):
            return [{
                "stock_id": "2330", "name": "台積電", "price": None,
                "yesterday_close": 120, "volume": 0,
            }]

    monkeypatch.setattr("core.quote_provider.taiwan_market_state", lambda: "preopen")

    result = TwseQuoteAdapter(Provider()).get_quotes(["2330"])[0]

    assert result["price"] == 120
    assert result["freshness"] == "previous_close"
    assert result["is_realtime"] is False
    assert result["source"] == "twse"


def test_fugle_adapter_stops_at_its_non_blocking_per_minute_budget(monkeypatch):
    calls = []

    class Response:
        def __init__(self, stock_id):
            self.stock_id = stock_id

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "date": "2026-08-24", "symbol": self.stock_id,
                "lastPrice": 100, "previousClose": 99, "total": {},
            }

    def fake_get(url, **kwargs):
        stock_id = url.rsplit("/", 1)[-1]
        calls.append(stock_id)
        return Response(stock_id)

    monkeypatch.setattr("core.quote_provider.requests.get", fake_get)
    adapter = FugleQuoteAdapter(
        api_key="secret", max_workers=1, max_calls_per_minute=1,
    )

    result = adapter.get_quotes(["2330", "2317"])

    assert calls == ["2330"]
    assert [item["stock_id"] for item in result] == ["2330"]


def test_service_coalesces_simultaneous_requests_for_the_same_symbol():
    entered = threading.Event()
    second_entered = threading.Event()
    release = threading.Event()

    class SlowAdapter:
        def __init__(self):
            self.calls = 0

        def get_quotes(self, stock_ids):
            self.calls += 1
            if self.calls > 1:
                second_entered.set()
            entered.set()
            assert release.wait(timeout=2)
            return [quote("2330", 101, "fugle")]

    adapter = SlowAdapter()
    service = QuoteService([adapter], FakeQuoteAdapter(), cache_ttl=60)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.get_quote, "2330")
        assert entered.wait(timeout=2)
        second = executor.submit(service.get_quote, "2330")
        assert not second_entered.wait(timeout=0.1)
        release.set()
        assert first.result(timeout=2)["price"] == 101
        assert second.result(timeout=2)["price"] == 101

    assert adapter.calls == 1
