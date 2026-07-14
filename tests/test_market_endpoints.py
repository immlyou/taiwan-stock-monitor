"""market 端點 characterization 測試（2026-07-15 P2b）。

market.py 的 7 個端點改為把阻塞的 loader.get / 計算丟進 run_in_executor（避免卡單
worker 事件迴圈）。這些端點原本幾乎沒有端點層測試，本檔補上：以 mocked loader 驗證
卸載後仍回 200 且結構/數值正確（尤其 market_after_hours 是拆段重構，非逐字節搬移）。
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient


class _NoCache:
    def get(self, key):
        return None

    def set(self, key, value, ttl_seconds):
        pass

    def clear(self):
        pass


@pytest.fixture
def market_client(monkeypatch):
    import api.deps
    import api.routers.market as market_mod

    monkeypatch.setattr(api.deps, "API_KEY", "")
    monkeypatch.setattr("core.data_loader._finlab_quota_exceeded", False)
    monkeypatch.setattr("api.helpers.get_cache", lambda: _NoCache())

    dates = pd.to_datetime(["2026-07-14", "2026-07-15"])
    close = pd.DataFrame(
        {"1111": [100.0, 110.0], "2222": [50.0, 45.0], "3333": [30.0, 30.0]},
        index=dates,
    )
    active = ["1111", "2222", "3333"]
    name_map = {"1111": "甲", "2222": "乙", "3333": "丙"}
    industry_map = {"1111": "半導體", "2222": "金融", "3333": "半導體"}
    price_index = pd.Series([18000.0, 18100.0], index=dates)
    inst = pd.DataFrame({"1111": [1000, 2000], "2222": [-500, -300]}, index=dates)

    def _loader_get(key):
        if key == "close":
            return close
        if key in ("foreign_investors", "investment_trust", "dealer"):
            return inst
        return None

    monkeypatch.setattr(market_mod, "get_active_stocks", lambda *a, **k: active)
    monkeypatch.setattr(
        market_mod, "get_data_summary",
        lambda: {"latest_date": "2026-07-15", "total_stocks": len(active)},
    )
    monkeypatch.setattr(market_mod.loader, "get", _loader_get)
    monkeypatch.setattr(market_mod.loader, "get_price_index", lambda: price_index)
    monkeypatch.setattr(market_mod.loader, "get_benchmark", lambda: price_index)
    monkeypatch.setattr(market_mod, "_get_stock_name_map", lambda: name_map)
    monkeypatch.setattr(market_mod, "_get_industry_map", lambda: industry_map)
    monkeypatch.setattr(
        market_mod, "calculate_industry_rotation",
        lambda loader, top_n=30: {"industries": [{"industry": "半導體", "score": 1.0}], "top_n": top_n},
    )

    async def _fake_run_strategy(stype, preset="standard", top_n=5):
        return {"total_matches": 2, "stocks": [{"stock_id": "1111"}, {"stock_id": "2222"}]}

    monkeypatch.setattr(market_mod, "run_strategy", _fake_run_strategy)

    from api_server import app
    return TestClient(app)


def test_summary_offloaded_ok(market_client):
    r = market_client.get("/market/summary")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["up_count"] + b["down_count"] + b["flat_count"] == 3
    assert b.get("note") != "FinLab 額度超限，僅提供大盤指數"


def test_heatmap_offloaded_ok(market_client):
    r = market_client.get("/market/heatmap")
    assert r.status_code == 200, r.text
    b = r.json()
    assert "industries" in b and isinstance(b["industries"], list)


def test_money_flow_offloaded_ok(market_client):
    r = market_client.get("/market/money-flow")
    assert r.status_code == 200, r.text
    b = r.json()
    assert set(b) >= {"foreign", "investment_trust", "dealer"}


def test_benchmark_offloaded_passes_days(market_client):
    r = market_client.get("/market/benchmark?days=20")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["days"] == 20
    assert len(b["data"]) == 2  # 只有兩天資料


def test_industries_offloaded_ok(market_client):
    r = market_client.get("/market/industries")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["total_industries"] == len(b["industries"])


def test_industry_rotation_offloaded_passes_top_n(market_client):
    r = market_client.get("/market/industry-rotation?top_n=7")
    assert r.status_code == 200, r.text
    assert r.json()["top_n"] == 7  # top_n 有正確透傳進 executor


def test_after_hours_restructured_output(market_client):
    r = market_client.get("/market/after-hours")
    assert r.status_code == 200, r.text
    b = r.json()
    # 輸出結構與重構前一致，且內部用的 name_map 不外洩
    assert set(b) == {"date", "taiex", "institutional", "market", "top_gainers", "top_losers", "ai_picks"}
    assert b["market"]["up"] + b["market"]["down"] + b["market"]["flat"] == 3
    assert b["ai_picks"]["value"]["total"] == 2
    assert b["ai_picks"]["value"]["top5"][0] == {"stock_id": "1111", "name": "甲"}
    assert b["top_gainers"][0]["stock_id"] == "1111"  # +10% 最高
