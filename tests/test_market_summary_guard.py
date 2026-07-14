"""/market/summary 回歸測試：prev=0 造成的 inf 漲跌幅不得炸 500。

背景（2026-07-15 健檢 P0）：
- `market_summary` 的 ``changes = (latest - prev) / prev * 100`` 原本缺少同檔
  `market_heatmap`/`market_industries` 都有的 inf/NaN 清洗。當某股 prev=0
  （新上市／資料異常）時 changes 為 ±inf，被排進 top_gainers/top_losers 後以
  原生 float 送入 `SafeJSONResponse`。
- `SafeJSONResponse` 原本對原生 NaN/Inf 的清洗是死碼（`json.dumps(allow_nan=False)`
  會在呼叫 default hook 前就拋 ValueError）→ 整個請求裸 500。

兩個修復：
1. `api/routers/market.py`：`changes` 補 `.replace([inf,-inf],0).fillna(0)`（inf→0）。
2. `api/response.py`：改成先遞迴 sanitize 再 dumps。

本測試同時鎖住兩者：
- `status_code == 200`：若 response.py 死碼還在，這裡會是 500。
- 榜單無 None：若 market.py 未清 inf，會靠 response.py 把 inf 清成 **None**；有 market
  修復則 inf→**0.0**。故「無 None」專門鎖 market.py 的 inf 防護。
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def market_client(monkeypatch):
    import api.deps
    import api.routers.market as market_mod

    monkeypatch.setattr(api.deps, "API_KEY", "")

    # AAAA 的 prev=0 → (10-0)/0 = +inf；BBBB +10%；CCCC -10%
    close = pd.DataFrame(
        {
            "AAAA": [0.0, 10.0],
            "BBBB": [100.0, 110.0],
            "CCCC": [50.0, 45.0],
        },
        index=pd.to_datetime(["2026-07-14", "2026-07-15"]),
    )
    active = ["AAAA", "BBBB", "CCCC"]

    monkeypatch.setattr(market_mod, "get_active_stocks", lambda: active)
    monkeypatch.setattr(
        market_mod,
        "get_data_summary",
        lambda: {"latest_date": "2026-07-15", "total_stocks": len(active)},
    )
    monkeypatch.setattr(
        market_mod.loader, "get", lambda key: close if key == "close" else None
    )
    monkeypatch.setattr(market_mod, "_taiex_quote", lambda: (18000.0, 100.0, 0.56))

    # market_summary 開頭有 FinLab 額度超限的早退守衛（讀 core.data_loader 的模組級
    # 旗標 _finlab_quota_exceeded）。其他測試（如 test_finlab_resilience）可能把它設
    # True 且未還原，會讓本端點走 TWSE 降級分支、跳過我們要驗的 inf 清洗路徑。強制設
    # False 確保走實算路徑（monkeypatch 會自動還原，不污染他人）。
    monkeypatch.setattr("core.data_loader._finlab_quota_exceeded", False)

    # 回應快取是程序級單例（且線上/全套件下可能是 Redis）。為讓本測試不受其他測試
    # 快取狀態影響、也不污染他人，直接把 cached_response 用的 get_cache 換成「永遠
    # miss、set 為 no-op」的假 backend → 保證走 market_summary 的實算路徑。
    class _NoCache:
        def get(self, key):
            return None

        def set(self, key, value, ttl_seconds):
            pass

        def clear(self):
            pass

    monkeypatch.setattr("api.helpers.get_cache", lambda: _NoCache())

    from api_server import app
    return TestClient(app)


def test_market_summary_prev_zero_does_not_500(market_client):
    resp = market_client.get("/market/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    pcts = [g["change_pct"] for g in body["top_gainers"]]
    pcts += [ll["change_pct"] for ll in body["top_losers"]]

    # 沒有任何 inf 洩漏成 None：market.py 的 inf→0 防護生效
    assert None not in pcts, f"inf 漲跌幅未被清成 0（洩漏 None）: {pcts}"
    # 且都是有限數（無 NaN）
    assert all(isinstance(p, (int, float)) and p == p for p in pcts), pcts

    # 確認走的是實算路徑（非 FinLab 額度超限的降級分支）
    assert body.get("note") != "FinLab 額度超限，僅提供大盤指數", body
    # 計數自洽：inf 股被清成 0 → 計入 flat（3 檔：AAAA/BBBB/CCCC）
    assert body["up_count"] + body["down_count"] + body["flat_count"] == 3
