"""
Stateful CRUD endpoints contract tests.

涵蓋：
- /watchlists   (app.components.watchlist_utils 持久化)
- /portfolios   (app.components.portfolio_utils 持久化)
- /alerts       (core.alerts.AlertEngine 類別屬性 ALERTS_FILE)
- /journal      (api.helpers _load_json_file / _save_json_file，走 DATA_DIR)

策略：把各模組的「檔案路徑常數」重定向到 tmp_path，所有讀寫實際發生在
tmp dir 內，測試結束自動清理；不需要 mock 任何讀寫函式本身。
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def stateful_client(monkeypatch, tmp_path, sample_close, sample_volume, sample_stock_info):
    """TestClient with all persistence layers redirected to tmp_path."""
    import api.deps
    from api import helpers as api_helpers
    from api import state as api_state
    from api.state import loader as real_loader

    # 強制無 auth（避免上一個測試殘留）
    monkeypatch.setattr(api.deps, "API_KEY", "")

    # ── 1. DataLoader mock ─────────────────────────────
    cats = pd.DataFrame({
        "stock_id": sample_stock_info["stock_id"].astype(str).values,
        "name": sample_stock_info["name"].astype(str).values,
        "category": sample_stock_info["industry"].astype(str).values,
    })
    sample_data = {
        "close": sample_close,
        "open": sample_close * 0.99,
        "high": sample_close * 1.02,
        "low": sample_close * 0.98,
        "volume": sample_volume,
        "categories": cats,
    }

    def mock_get(self_or_key, *args):
        # 支援被當 instance method 或 module function 呼叫
        key = args[0] if args else self_or_key
        return sample_data.get(key)

    monkeypatch.setattr(real_loader, "get", lambda key: sample_data.get(key))
    from core.data_loader import DataLoader
    monkeypatch.setattr(
        DataLoader, "get", lambda self, key: sample_data.get(key)
    )

    # Stateful CRUD tests must not call external Fugle/TWSE providers.
    class DailyQuoteService:
        def get_quotes(self, stock_ids):
            quotes = []
            for stock_id in stock_ids:
                if stock_id not in sample_close.columns:
                    continue
                series = sample_close[stock_id].dropna()
                price = float(series.iloc[-1])
                prev = float(series.iloc[-2])
                quotes.append({
                    "stock_id": stock_id,
                    "price": price,
                    "prev_close": prev,
                    "change": price - prev,
                    "change_pct": (price - prev) / prev * 100,
                    "source": "finlab",
                    "is_realtime": False,
                    "freshness": "close",
                    "market_state": "closed",
                    "timestamp": None,
                    "date": series.index[-1].strftime("%Y-%m-%d"),
                })
            return quotes

    from api.routers import portfolios as portfolio_router
    from api.routers import watchlists as watchlist_router
    daily_quote_service = DailyQuoteService()
    monkeypatch.setattr(portfolio_router, "quote_service", daily_quote_service, raising=False)
    monkeypatch.setattr(watchlist_router, "quote_service", daily_quote_service, raising=False)

    # ── 2. 持久化檔案重定向 ───────────────────────────
    # journal: api.helpers / api.state 的 DATA_DIR
    monkeypatch.setattr(api_state, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api_helpers, "DATA_DIR", tmp_path)

    # watchlists
    from app.components import watchlist_utils
    monkeypatch.setattr(watchlist_utils, "WATCHLIST_FILE", tmp_path / "watchlists.json")

    # portfolios
    from app.components import portfolio_utils
    monkeypatch.setattr(portfolio_utils, "PORTFOLIO_FILE", tmp_path / "portfolios.json")

    # alerts (class attribute)
    from core.alerts import AlertEngine
    monkeypatch.setattr(AlertEngine, "ALERTS_FILE", tmp_path / "alerts.json")

    from api_server import app
    return TestClient(app)


# ── 自選股 CRUD ──────────────────────────────────────────
class TestWatchlistsCRUD:
    def test_data_is_isolated_per_user(self, stateful_client):
        alice = {"X-User-ID": "google_alice123"}
        bob = {"X-User-ID": "google_bob456"}
        created = stateful_client.post(
            "/watchlists",
            json={"name": "alice-only", "stocks": ["2330"]},
            headers=alice,
        )
        assert created.status_code == 200
        assert stateful_client.get("/watchlists", headers=alice).json()["total"] == 1
        assert stateful_client.get("/watchlists", headers=bob).json()["total"] == 0

    def test_list_empty(self, stateful_client):
        r = stateful_client.get("/watchlists")
        assert r.status_code == 200
        assert r.json() == {"total": 0, "watchlists": []}

    def test_put_default_creates_the_first_watchlist(self, stateful_client):
        """The fixed frontend alias must be writable for a brand-new user."""
        updated = stateful_client.put(
            "/watchlists/default",
            json={"stocks": ["2330"]},
            headers={"X-User-ID": "google_first_watchlist"},
        )

        assert updated.status_code == 200
        detail = stateful_client.get(
            "/watchlists/default",
            headers={"X-User-ID": "google_first_watchlist"},
        )
        assert detail.status_code == 200
        assert [stock["stock_id"] for stock in detail.json()["stocks"]] == ["2330"]

    def test_create_then_list(self, stateful_client):
        r = stateful_client.post(
            "/watchlists",
            json={"name": "我的觀察清單", "stocks": ["2330", "2317"]},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "我的觀察清單"

        r2 = stateful_client.get("/watchlists")
        assert r2.json()["total"] == 1
        assert r2.json()["watchlists"][0]["name"] == "我的觀察清單"

    def test_duplicate_create_returns_409(self, stateful_client):
        stateful_client.post("/watchlists", json={"name": "dup", "stocks": []})
        r = stateful_client.post("/watchlists", json={"name": "dup", "stocks": []})
        assert r.status_code == 409

    def test_get_unknown_returns_404(self, stateful_client):
        r = stateful_client.get("/watchlists/nonexistent")
        assert r.status_code == 404

    def test_get_returns_quotes(self, stateful_client, sample_stocks):
        stateful_client.post(
            "/watchlists",
            json={"name": "wl1", "stocks": sample_stocks[:2]},
        )
        r = stateful_client.get("/watchlists/wl1")
        assert r.status_code == 200
        body = r.json()
        assert body["stocks_count"] == 2
        # mock loader 有提供 close → price 應非 None
        for s in body["stocks"]:
            assert s["stock_id"] in sample_stocks
            assert s["price"] is not None

    def test_get_prefers_live_quote_and_exposes_freshness(self, stateful_client, monkeypatch):
        from api.routers import watchlists as watchlist_router

        class LiveQuotes:
            def get_quotes(self, stock_ids):
                return [{
                    "stock_id": sid, "price": 321.0, "change_pct": 4.2,
                    "source": "fugle", "is_realtime": True,
                    "freshness": "realtime", "market_state": "trading",
                    "timestamp": "2026-08-24T10:00:00+08:00", "date": "2026-08-24",
                } for sid in stock_ids]

        monkeypatch.setattr(watchlist_router, "quote_service", LiveQuotes(), raising=False)
        stateful_client.post("/watchlists", json={"name": "live", "stocks": ["2330"]})

        stock = stateful_client.get("/watchlists/live").json()["stocks"][0]

        assert stock["price"] == 321.0
        assert stock["source"] == "fugle"
        assert stock["is_realtime"] is True
        assert stock["freshness"] == "realtime"
        assert stock["timestamp"] == "2026-08-24T10:00:00+08:00"

    def test_update_replaces_stocks(self, stateful_client):
        stateful_client.post("/watchlists", json={"name": "wl2", "stocks": ["2330"]})
        r = stateful_client.put(
            "/watchlists/wl2",
            json={"stocks": ["2317", "2454"]},
        )
        assert r.status_code == 200

        body = stateful_client.get("/watchlists/wl2").json()
        ids = [s["stock_id"] for s in body["stocks"]]
        assert "2317" in ids and "2454" in ids
        assert "2330" not in ids

    def test_delete(self, stateful_client):
        stateful_client.post("/watchlists", json={"name": "wl3", "stocks": []})
        r = stateful_client.delete("/watchlists/wl3")
        assert r.status_code == 200
        assert stateful_client.get("/watchlists").json()["total"] == 0

    def test_delete_unknown_returns_404(self, stateful_client):
        r = stateful_client.delete("/watchlists/nope")
        assert r.status_code == 404


# ── 投資組合 CRUD ────────────────────────────────────────
class TestPortfoliosCRUD:
    def test_data_is_isolated_per_user(self, stateful_client):
        alice = {"X-User-ID": "google_alice123"}
        bob = {"X-User-ID": "google_bob456"}
        created = stateful_client.post(
            "/portfolios",
            json={"name": "alice-only", "description": "private"},
            headers=alice,
        )
        assert created.status_code == 200
        assert stateful_client.get("/portfolios", headers=alice).json()["total"] == 1
        assert stateful_client.get("/portfolios", headers=bob).json()["total"] == 0

    def test_list_empty(self, stateful_client):
        r = stateful_client.get("/portfolios")
        assert r.status_code == 200
        assert r.json() == {"total": 0, "portfolios": []}

    def test_put_default_creates_the_first_portfolio(self, stateful_client):
        """A new Google user can save the first holding through the default alias."""
        headers = {"X-User-ID": "google_first_portfolio"}
        updated = stateful_client.put(
            "/portfolios/default",
            json={
                "holdings": [
                    {"stock_id": "2330", "shares": 1000, "cost_price": 100}
                ]
            },
            headers=headers,
        )

        assert updated.status_code == 200
        detail = stateful_client.get("/portfolios/default", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["holdings"][0]["stock_id"] == "2330"

    def test_create_then_get(self, stateful_client):
        r = stateful_client.post(
            "/portfolios",
            json={"name": "長線組合", "description": "核心持股"},
        )
        assert r.status_code == 200

        r2 = stateful_client.get("/portfolios/長線組合")
        assert r2.status_code == 200
        body = r2.json()
        assert body["description"] == "核心持股"
        assert body["holdings"] == []
        assert "summary" in body

    def test_duplicate_create_returns_409(self, stateful_client):
        stateful_client.post("/portfolios", json={"name": "dup", "description": ""})
        r = stateful_client.post("/portfolios", json={"name": "dup", "description": ""})
        assert r.status_code == 409

    def test_get_unknown_returns_404(self, stateful_client):
        r = stateful_client.get("/portfolios/nonexistent")
        assert r.status_code == 404

    def test_update_with_holdings_computes_pnl(self, stateful_client, sample_stocks):
        stateful_client.post("/portfolios", json={"name": "p1", "description": ""})
        r = stateful_client.put(
            "/portfolios/p1",
            json={
                "holdings": [
                    {
                        "stock_id": sample_stocks[0],
                        "shares": 1000,
                        "cost_price": 100.0,
                        "buy_date": "2024-01-01",
                    },
                ],
            },
        )
        assert r.status_code == 200

        body = stateful_client.get("/portfolios/p1").json()
        assert len(body["holdings"]) == 1
        h = body["holdings"][0]
        # 至少回傳所需欄位
        for field in ("current_price", "current_value", "pnl", "pnl_pct"):
            assert field in h
        # summary 不應為 None
        assert body["summary"]["total_cost"] > 0

    def test_get_uses_live_prices_for_holding_and_summary(self, stateful_client, monkeypatch):
        from api.routers import portfolios as portfolio_router

        class LiveQuotes:
            def get_quotes(self, stock_ids):
                return [{
                    "stock_id": sid, "price": 250.0, "change_pct": 2.0,
                    "source": "twse", "is_realtime": True,
                    "freshness": "realtime", "market_state": "trading",
                    "timestamp": "2026-08-24T11:00:00+08:00", "date": "2026-08-24",
                } for sid in stock_ids]

        monkeypatch.setattr(portfolio_router, "quote_service", LiveQuotes(), raising=False)
        stateful_client.post("/portfolios", json={"name": "live", "description": ""})
        stateful_client.put(
            "/portfolios/live",
            json={"holdings": [{"stock_id": "2330", "shares": 1000, "cost_price": 200}]},
        )

        body = stateful_client.get("/portfolios/live").json()
        holding = body["holdings"][0]

        assert holding["current_price"] == 250.0
        assert holding["current_value"] == 250000.0
        assert holding["source"] == "twse"
        assert holding["is_realtime"] is True
        assert body["summary"]["total_value"] == 250000.0

    def test_delete(self, stateful_client):
        stateful_client.post("/portfolios", json={"name": "p2", "description": ""})
        r = stateful_client.delete("/portfolios/p2")
        assert r.status_code == 200
        assert stateful_client.get("/portfolios").json()["total"] == 0

    def test_update_holdings_validation_rejects_zero_shares(self, stateful_client):
        stateful_client.post("/portfolios", json={"name": "p3", "description": ""})
        r = stateful_client.put(
            "/portfolios/p3",
            json={"holdings": [{"stock_id": "2330", "shares": 0, "cost_price": 100}]},
        )
        # HoldingItem.shares ge=1 → 422
        assert r.status_code == 422

    def test_what_if_returns_diagnostics_without_persisting(self, stateful_client):
        headers = {"X-User-ID": "google_whatifowner"}
        stateful_client.post(
            "/portfolios",
            headers=headers,
            json={"name": "scenario", "description": "baseline"},
        )
        stateful_client.put(
            "/portfolios/scenario",
            headers=headers,
            json={
                "holdings": [
                    {"stock_id": "2330", "shares": 1000, "cost_price": 100}
                ]
            },
        )

        response = stateful_client.post(
            "/portfolios/scenario/what-if",
            headers=headers,
            json={
                "operations": [
                    {
                        "action": "add",
                        "stock_id": "2317",
                        "shares": 500,
                        "cost_price": 80,
                    }
                ]
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["persisted"] is False
        assert body["baseline"]["holdings_count"] == 1
        assert body["scenario"]["holdings_count"] == 2
        assert body["delta"]["holdings_count"] == 1
        assert {h["stock_id"] for h in body["scenarioHoldings"]} == {"2330", "2317"}

        unchanged = stateful_client.get(
            "/portfolios/scenario", headers=headers
        ).json()
        assert len(unchanged["holdings"]) == 1
        assert unchanged["holdings"][0]["stock_id"] == "2330"

    def test_what_if_rejects_an_update_for_a_missing_holding(self, stateful_client):
        stateful_client.post(
            "/portfolios", json={"name": "scenario", "description": "baseline"}
        )
        response = stateful_client.post(
            "/portfolios/scenario/what-if",
            json={
                "operations": [
                    {
                        "action": "update",
                        "stock_id": "9999",
                        "shares": 10,
                        "cost_price": 10,
                    }
                ]
            },
        )
        assert response.status_code == 422


# ── 警報 CRUD ────────────────────────────────────────────
class TestAlertsCRUD:
    def test_data_is_isolated_per_user(self, stateful_client):
        alice = {"X-User-ID": "google_alice123"}
        bob = {"X-User-ID": "google_bob456"}
        created = stateful_client.post(
            "/alerts",
            json={"stock_id": "2330", "type": "price_above", "value": 700},
            headers=alice,
        )
        assert created.status_code == 200
        assert stateful_client.get("/alerts", headers=alice).json()["total"] == 1
        assert stateful_client.get("/alerts", headers=bob).json()["total"] == 0

    def test_alert_types(self, stateful_client):
        r = stateful_client.get("/alerts/types")
        assert r.status_code == 200
        types = r.json()["types"]
        assert any(t["type"] == "price_above" for t in types)

    def test_list_empty(self, stateful_client):
        r = stateful_client.get("/alerts")
        assert r.status_code == 200
        assert r.json() == {"total": 0, "alerts": []}

    def test_create_then_list(self, stateful_client):
        r = stateful_client.post(
            "/alerts",
            json={"stock_id": "2330", "type": "price_above", "value": 700, "note": "突破"},
        )
        assert r.status_code == 200
        alert_id = r.json()["alert"]["id"]
        assert alert_id

        body = stateful_client.get("/alerts").json()
        assert body["total"] == 1
        assert body["alerts"][0]["stock_id"] == "2330"

    def test_patch_disables_alert(self, stateful_client):
        r = stateful_client.post(
            "/alerts",
            json={"stock_id": "2330", "type": "price_below", "value": 500},
        )
        alert_id = r.json()["alert"]["id"]
        r2 = stateful_client.patch(f"/alerts/{alert_id}", json={"enabled": False})
        assert r2.status_code == 200
        assert r2.json()["alert"]["enabled"] is False

    def test_patch_unknown_returns_404(self, stateful_client):
        r = stateful_client.patch("/alerts/nonexistent", json={"enabled": True})
        assert r.status_code == 404

    def test_delete(self, stateful_client):
        r = stateful_client.post(
            "/alerts",
            json={"stock_id": "2330", "type": "rsi_above", "value": 80},
        )
        alert_id = r.json()["alert"]["id"]
        r2 = stateful_client.delete(f"/alerts/{alert_id}")
        assert r2.status_code == 200
        assert stateful_client.get("/alerts").json()["total"] == 0

    def test_delete_unknown_returns_404(self, stateful_client):
        r = stateful_client.delete("/alerts/nope")
        assert r.status_code == 404


class TestAlertsV2Rules:
    def test_rule_update_is_not_lost_during_concurrent_evaluation(
        self, stateful_client, monkeypatch
    ):
        """A scheduler snapshot must never overwrite a newer user edit."""
        headers = {"X-User-ID": "google_concurrent_rule"}
        created = stateful_client.post(
            "/alerts/rules",
            headers=headers,
            json={
                "name": "舊名稱",
                "target": {"stockIds": ["2330"]},
                "conditions": [
                    {"field": "price", "operator": "gt", "value": 0}
                ],
            },
        )
        rule_id = created.json()["rule"]["id"]
        evaluation_started = threading.Event()
        allow_evaluation_to_finish = threading.Event()

        def slow_no_hit(*_args, **_kwargs):
            evaluation_started.set()
            assert allow_evaluation_to_finish.wait(timeout=2)
            return False, {}, []

        monkeypatch.setattr(
            "core.alert_rules.evaluate_rule_for_stock", slow_no_hit
        )

        from api.models import AlertEvaluateRequest
        from api.routers.alerts import alert_rules_evaluate

        with ThreadPoolExecutor(max_workers=1) as executor:
            evaluating = executor.submit(
                asyncio.run,
                alert_rules_evaluate(
                    AlertEvaluateRequest(ruleIds=[rule_id]),
                    user_id="google_concurrent_rule",
                ),
            )
            assert evaluation_started.wait(timeout=2)
            updated = stateful_client.patch(
                f"/alerts/rules/{rule_id}",
                headers=headers,
                json={"name": "使用者的新名稱"},
            )
            assert updated.status_code == 200
            allow_evaluation_to_finish.set()
            assert evaluating.result(timeout=2)["evaluatedRules"] == 1

        rules = stateful_client.get("/alerts/rules", headers=headers).json()["rules"]
        assert rules[0]["name"] == "使用者的新名稱"

    def test_multi_condition_rule_evaluates_and_records_history(
        self, stateful_client
    ):
        headers = {"X-User-ID": "google_ruleowner"}
        created = stateful_client.post(
            "/alerts/rules",
            headers=headers,
            json={
                "name": "價格與漲跌幅同時符合",
                "match": "all",
                "target": {"stockIds": ["2330"]},
                "conditions": [
                    {"field": "price", "operator": "gt", "value": 0},
                    {"field": "change_pct", "operator": "gt", "value": -100},
                ],
                "frequency": "repeating",
                "cooldownMinutes": 60,
                "channels": ["telegram"],
            },
        )
        assert created.status_code == 200
        rule_id = created.json()["rule"]["id"]

        evaluated = stateful_client.post(
            "/alerts/evaluate", headers=headers, json={"ruleIds": [rule_id]}
        )
        assert evaluated.status_code == 200
        assert evaluated.json()["triggeredCount"] == 1
        assert evaluated.json()["hits"][0]["stockId"] == "2330"

        # Same stock/rule is inside its cooldown window, so no duplicate hit.
        repeated = stateful_client.post(
            "/alerts/evaluate", headers=headers, json={"ruleIds": [rule_id]}
        )
        assert repeated.json()["triggeredCount"] == 0
        assert repeated.json()["suppressedCount"] == 1

        history = stateful_client.get("/alerts/hits", headers=headers)
        assert history.status_code == 200
        assert history.json()["total"] == 1
        assert history.json()["hits"][0]["ruleId"] == rule_id

    def test_any_rule_can_expand_a_watchlist_target(self, stateful_client):
        headers = {"X-User-ID": "google_watchlistrule"}
        stateful_client.post(
            "/watchlists",
            headers=headers,
            json={"name": "focus", "stocks": ["2330", "2317"]},
        )
        created = stateful_client.post(
            "/alerts/rules",
            headers=headers,
            json={
                "name": "觀察清單任一條件",
                "match": "any",
                "target": {"watchlistId": "focus"},
                "conditions": [
                    {"field": "price", "operator": "gt", "value": 0},
                    {"field": "rsi", "operator": "lt", "value": 0},
                ],
            },
        )
        assert created.status_code == 200

        result = stateful_client.post(
            "/alerts/evaluate", headers=headers, json={}
        ).json()
        assert result["triggeredCount"] == 2
        assert {hit["stockId"] for hit in result["hits"]} == {"2330", "2317"}

    def test_rules_and_hits_are_isolated_per_user(self, stateful_client):
        alice = {"X-User-ID": "google_rulesalice"}
        bob = {"X-User-ID": "google_rulesbob"}
        stateful_client.post(
            "/alerts/rules",
            headers=alice,
            json={
                "name": "alice only",
                "target": {"stockIds": ["2330"]},
                "conditions": [
                    {"field": "price", "operator": "gt", "value": 0}
                ],
            },
        )

        assert stateful_client.get("/alerts/rules", headers=alice).json()["total"] == 1
        assert stateful_client.get("/alerts/rules", headers=bob).json()["total"] == 0


# ── 交易日誌 CRUD ────────────────────────────────────────
class TestJournalCRUD:
    def test_data_is_isolated_per_user(self, stateful_client):
        alice = {"X-User-ID": "google_alice123"}
        bob = {"X-User-ID": "google_bob456"}
        created = stateful_client.post(
            "/journal",
            json={"stock_id": "2330", "action": "note", "note": "private"},
            headers=alice,
        )
        assert created.status_code == 200
        assert stateful_client.get("/journal", headers=alice).json()["total"] == 1
        assert stateful_client.get("/journal", headers=bob).json()["total"] == 0

    def test_list_empty(self, stateful_client):
        r = stateful_client.get("/journal")
        assert r.status_code == 200
        assert r.json() == {"total": 0, "entries": []}

    def test_create_then_list(self, stateful_client):
        r = stateful_client.post(
            "/journal",
            json={
                "stock_id": "2330",
                "action": "buy",
                "shares": 1000,
                "price": 650,
                "note": "突破買進",
                "date": "2025-05-26",
            },
        )
        assert r.status_code == 200
        entry_id = r.json()["entry"]["id"]
        assert entry_id

        r2 = stateful_client.get("/journal")
        assert r2.json()["total"] == 1
        assert r2.json()["entries"][0]["action"] == "buy"

    def test_filter_by_stock_id(self, stateful_client):
        stateful_client.post(
            "/journal",
            json={"stock_id": "2330", "action": "buy", "shares": 100, "price": 600},
        )
        stateful_client.post(
            "/journal",
            json={"stock_id": "2317", "action": "buy", "shares": 100, "price": 200},
        )
        r = stateful_client.get("/journal?stock_id=2330")
        assert r.json()["total"] == 1
        assert r.json()["entries"][0]["stock_id"] == "2330"

    def test_limit_validation(self, stateful_client):
        r = stateful_client.get("/journal?limit=500")
        assert r.status_code == 422

    def test_update_entry(self, stateful_client):
        r = stateful_client.post(
            "/journal",
            json={"stock_id": "2330", "action": "buy", "shares": 100, "price": 600},
        )
        entry_id = r.json()["entry"]["id"]
        r2 = stateful_client.put(
            f"/journal/{entry_id}",
            json={"stock_id": "2330", "action": "sell", "shares": 100, "price": 700},
        )
        assert r2.status_code == 200
        assert r2.json()["entry"]["action"] == "sell"

    def test_update_unknown_returns_404(self, stateful_client):
        r = stateful_client.put(
            "/journal/nonexistent",
            json={"stock_id": "2330", "action": "buy"},
        )
        assert r.status_code == 404

    def test_delete(self, stateful_client):
        r = stateful_client.post(
            "/journal",
            json={"stock_id": "2330", "action": "note", "note": "備忘"},
        )
        entry_id = r.json()["entry"]["id"]
        r2 = stateful_client.delete(f"/journal/{entry_id}")
        assert r2.status_code == 200
        assert stateful_client.get("/journal").json()["total"] == 0
