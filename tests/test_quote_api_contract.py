"""Public HTTP contract for normalized realtime quote responses."""
from __future__ import annotations

from fastapi.testclient import TestClient


def live_quote(stock_id: str) -> dict:
    return {
        "stock_id": stock_id,
        "name": "台積電" if stock_id == "2330" else "鴻海",
        "price": 123.5,
        "prev_close": 120.0,
        "change": 3.5,
        "change_pct": 2.92,
        "open": 121.0,
        "high": 124.0,
        "low": 119.5,
        "volume": 2000,
        "amount": 247000,
        "date": "2026-08-24",
        "timestamp": "2026-08-24T10:00:01+08:00",
        "source": "fugle",
        "is_realtime": True,
        "market_state": "trading",
        "freshness": "realtime",
        "note": "Fugle 盤中即時報價",
    }


class FakeQuoteService:
    def get_quote(self, stock_id: str):
        return live_quote(stock_id) if stock_id == "2330" else None

    def get_quotes(self, stock_ids):
        return [live_quote(stock_id) for stock_id in stock_ids]


def test_single_quote_exposes_source_freshness_and_provider_timestamp(monkeypatch):
    import api.deps
    import api.routers.quote as quote_router
    from api_server import app

    monkeypatch.setattr(api.deps, "API_KEY", "")
    monkeypatch.setattr(quote_router, "quote_service", FakeQuoteService(), raising=False)
    client = TestClient(app)

    response = client.get("/quote/realtime/2330")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fugle"
    assert body["freshness"] == "realtime"
    assert body["market_state"] == "trading"
    assert body["is_realtime"] is True
    assert body["timestamp"] == "2026-08-24T10:00:01+08:00"


def test_batch_quote_keeps_normalized_quote_contract_and_summary_metadata(monkeypatch):
    import api.deps
    import api.routers.quote as quote_router
    from api_server import app

    monkeypatch.setattr(api.deps, "API_KEY", "")
    monkeypatch.setattr(quote_router, "quote_service", FakeQuoteService(), raising=False)
    client = TestClient(app)

    response = client.post(
        "/quote/realtime/batch",
        json={"stock_ids": ["2330", "2317"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["sources"] == ["fugle"]
    assert body["has_realtime"] is True
    assert body["market_state"] == "trading"
    assert all(item["source"] == "fugle" for item in body["quotes"])


def test_single_quote_returns_404_when_every_provider_has_no_symbol(monkeypatch):
    import api.deps
    import api.routers.quote as quote_router
    from api_server import app

    monkeypatch.setattr(api.deps, "API_KEY", "")
    monkeypatch.setattr(quote_router, "quote_service", FakeQuoteService(), raising=False)
    client = TestClient(app)

    response = client.get("/quote/realtime/9999")

    assert response.status_code == 404
