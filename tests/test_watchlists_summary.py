"""自選股「組合即時追蹤匯總」端點 contract tests。

涵蓋 GET /watchlists/{id}/summary：
- 回傳結構正確（組合層匯總、貢獻排名、異常標記欄位）
- 缺資料股票被安全標記為 unavailable，不崩潰
- 異常波動（當日漲跌幅超門檻）被標記
- 空清單不崩潰
- 不存在的清單回 404

策略沿用 test_api_stateful.py：把持久化檔路徑與 DataLoader 重定向到
tmp_path / mock，所有讀寫實際發生在 tmp dir。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def summary_client(monkeypatch, tmp_path):
    """TestClient with watchlists 持久化 + DataLoader mock（小型可控資料集）。"""
    import api.deps
    from api import state as api_state
    from api.state import loader as real_loader

    # 強制無 auth
    monkeypatch.setattr(api.deps, "API_KEY", "")

    # ── 小型可控 close/volume DataFrame ───────────────────
    dates = pd.date_range("2024-01-01", periods=25, freq="B")
    # 2330：穩定上漲；最後一日 +1%
    p2330 = np.linspace(100.0, 120.0, len(dates))
    p2330[-1] = p2330[-2] * 1.01
    # 2317：最後一日暴跌 -8%（觸發異常 price_move）
    p2317 = np.linspace(50.0, 60.0, len(dates))
    p2317[-1] = p2317[-2] * 0.92
    close = pd.DataFrame({"2330": p2330, "2317": p2317}, index=dates)

    vol = pd.DataFrame(
        {
            "2330": np.full(len(dates), 10_000.0),
            # 2317 最後一日爆量（觸發 volume_spike）
            "2317": np.concatenate([np.full(len(dates) - 1, 5_000.0), [50_000.0]]),
        },
        index=dates,
    )

    cats = pd.DataFrame(
        {
            "stock_id": ["2330", "2317"],
            "name": ["台積電", "鴻海"],
            "category": ["半導體", "電子"],
        }
    )

    sample_data = {
        "close": close,
        "volume": vol,
        "categories": cats,
    }

    monkeypatch.setattr(real_loader, "get", lambda key: sample_data.get(key))
    from core.data_loader import DataLoader
    monkeypatch.setattr(DataLoader, "get", lambda self, key: sample_data.get(key))

    # ── 持久化檔重定向 ────────────────────────────────────
    monkeypatch.setattr(api_state, "DATA_DIR", tmp_path)
    from app.components import watchlist_utils
    monkeypatch.setattr(watchlist_utils, "WATCHLIST_FILE", tmp_path / "watchlists.json")

    from api_server import app
    return TestClient(app)


class TestWatchlistSummary:
    def test_unknown_returns_404(self, summary_client):
        r = summary_client.get("/watchlists/nope/summary")
        assert r.status_code == 404

    def test_empty_watchlist_does_not_crash(self, summary_client):
        summary_client.post("/watchlists", json={"name": "空清單", "stocks": []})
        r = summary_client.get("/watchlists/空清單/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["stocks_count"] == 0
        assert body["available_count"] == 0
        assert body["contribution_ranking"] == []
        assert body["abnormal_stocks"] == []
        # 空清單時組合層指標為 None，但不崩潰
        assert body["portfolio"]["avg_change_pct"] is None
        assert body["portfolio"]["avg_return_nd"] is None

    def test_summary_structure_and_ranking(self, summary_client):
        summary_client.post(
            "/watchlists", json={"name": "wl", "stocks": ["2330", "2317"]}
        )
        r = summary_client.get("/watchlists/wl/summary")
        assert r.status_code == 200
        body = r.json()

        # 頂層結構
        assert body["id"] == "wl"
        assert body["stocks_count"] == 2
        assert body["available_count"] == 2
        assert body["weighting"] == "equal"
        assert "portfolio" in body
        assert "contribution_ranking" in body
        assert "abnormal_stocks" in body

        # 組合層匯總有值
        assert body["portfolio"]["avg_change_pct"] is not None
        assert body["portfolio"]["avg_return_nd"] is not None

        # 個股欄位齊全
        for it in body["stocks"]:
            for field in ("stock_id", "name", "price", "change_pct",
                          "return_nd", "abnormal", "abnormal_reasons", "available"):
                assert field in it
            assert it["available"] is True
            assert it["price"] is not None

        # 貢獻排名：依當日漲跌幅由高至低（2330 上漲應在 2317 暴跌之前）
        ranking_ids = [it["stock_id"] for it in body["contribution_ranking"]]
        assert ranking_ids == ["2330", "2317"]
        # 排名是遞減的
        changes = [it["change_pct"] for it in body["contribution_ranking"]]
        assert changes[0] >= changes[1]

    def test_abnormal_stock_flagged(self, summary_client):
        summary_client.post(
            "/watchlists", json={"name": "wl2", "stocks": ["2330", "2317"]}
        )
        r = summary_client.get("/watchlists/wl2/summary?abnormal_pct=5")
        body = r.json()

        abnormal_ids = [a["stock_id"] for a in body["abnormal_stocks"]]
        assert "2317" in abnormal_ids  # -8% 超過 5% 門檻
        assert "2330" not in abnormal_ids  # +1% 未觸發

        # 2317 的異常原因含 price_move 與 volume_spike
        a2317 = next(a for a in body["abnormal_stocks"] if a["stock_id"] == "2317")
        assert "price_move" in a2317["reasons"]
        assert "volume_spike" in a2317["reasons"]
        assert body["portfolio"]["abnormal_count"] == len(body["abnormal_stocks"])

    def test_missing_data_stock_marked_unavailable(self, summary_client):
        # 9999 不在 mock close 中 → 應安全標記為 unavailable
        summary_client.post(
            "/watchlists", json={"name": "wl3", "stocks": ["2330", "9999"]}
        )
        r = summary_client.get("/watchlists/wl3/summary")
        assert r.status_code == 200
        body = r.json()

        assert body["stocks_count"] == 2
        assert body["available_count"] == 1
        assert "9999" in body["unavailable_stocks"]

        miss = next(it for it in body["stocks"] if it["stock_id"] == "9999")
        assert miss["available"] is False
        assert miss["price"] is None
        assert miss["change_pct"] is None

        # 缺資料股票不進貢獻排名
        ranking_ids = [it["stock_id"] for it in body["contribution_ranking"]]
        assert "9999" not in ranking_ids
