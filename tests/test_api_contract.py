"""
HTTP-level API contract tests using FastAPI TestClient.

驗證重點：
- 狀態碼（200 / 4xx）
- 回應 schema 必要欄位
- 路徑參數與 query 驗證錯誤

不驗證資料正確性（這是 core 模組單元測試的責任）。
所有外部資料（FinLab pickle、TWSE）皆透過 monkeypatch loader 避開。
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.routers.system import APP_VERSION


@pytest.fixture
def api_client(monkeypatch, tmp_path, sample_close, sample_volume, sample_stock_info):
    """TestClient with mocked DataLoader and isolated data dir."""
    import api.deps
    from api import helpers as api_helpers
    from api import state as api_state
    from api.state import loader as real_loader

    # 強制清空 API_KEY，避免上一個測試（如 test_api_auth）殘留 module-level 值
    monkeypatch.setattr(api.deps, "API_KEY", "")

    # 構造 categories DataFrame（_get_stock_name_map / _get_industry_map 會用到）
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

    def mock_get(self, key):
        return sample_data.get(key)

    # 替換 instance 上的 get 方法（覆蓋共享 singleton）
    monkeypatch.setattr(real_loader, "get", lambda key: sample_data.get(key))

    # 同步替換 DataLoader.get class-level 方法，覆蓋 `get_active_stocks` 等
    # 在函式內 new 出來的 DataLoader() 實例
    from core.data_loader import DataLoader
    monkeypatch.setattr(DataLoader, "get", mock_get)

    # 將 settings.json 等狀態檔導向 tmp_path，避免污染真實 data/ 目錄
    monkeypatch.setattr(api_state, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api_helpers, "DATA_DIR", tmp_path)

    # 清空所有層的快取，避免跨測試/跨 fixture 殘留
    try:
        from core.cache import get_cache
        cache = get_cache()
        if hasattr(cache, "clear"):
            cache.clear()
    except Exception:
        pass
    try:
        from core.data_loader import DataCache
        DataCache().clear() if hasattr(DataCache(), "clear") else None
    except Exception:
        pass

    from api_server import app
    return TestClient(app)


# ── 系統端點 ─────────────────────────────────────────────
class TestSystemEndpoints:
    def test_root_returns_metadata(self, api_client):
        r = api_client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "台股戰情中心 API"
        assert body["version"] == APP_VERSION
        assert body["docs"] == "/docs"

    def test_health_returns_status(self, api_client):
        r = api_client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("ok", "degraded")
        assert body["version"] == APP_VERSION
        assert "finlab" in body
        assert "timestamp" in body

    def test_openapi_schema_available(self, api_client):
        r = api_client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert schema["info"]["version"] == APP_VERSION
        assert "/stocks/list" in schema["paths"]


# ── 股票清單端點 ─────────────────────────────────────────
class TestStocksEndpoints:
    def test_stocks_list_shape(self, api_client):
        r = api_client.get("/stocks/list")
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert isinstance(body["stocks"], list)
        if body["stocks"]:
            stock = body["stocks"][0]
            assert "stock_id" in stock
            assert "name" in stock
            assert "industry" in stock

    def test_stocks_search_missing_query_returns_422(self, api_client):
        r = api_client.get("/stocks/search")
        assert r.status_code == 422

    def test_stocks_search_returns_results(self, api_client):
        r = api_client.get("/stocks/search?q=2330")
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "2330"
        assert "total" in body
        assert isinstance(body["stocks"], list)

    def test_stocks_search_limit_validation(self, api_client):
        # limit > 100 應觸發 422
        r = api_client.get("/stocks/search?q=2330&limit=500")
        assert r.status_code == 422

    def test_stocks_active_shape(self, api_client):
        r = api_client.get("/stocks/active")
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "date" in body
        assert isinstance(body["stocks"], list)

    def test_stocks_compare_empty_ids_returns_400(self, api_client):
        r = api_client.get("/stocks/compare?ids=")
        # 422 (FastAPI validation) 或 400 (handler 內邏輯) 都可
        assert r.status_code in (400, 422)

    def test_stocks_compare_too_many_returns_400(self, api_client):
        ids = ",".join([str(i) for i in range(1000, 1020)])
        r = api_client.get(f"/stocks/compare?ids={ids}")
        assert r.status_code == 400

    def test_stocks_compare_days_validation(self, api_client):
        r = api_client.get("/stocks/compare?ids=2330&days=5")  # < 10
        assert r.status_code == 422
        r = api_client.get("/stocks/compare?ids=2330&days=600")  # > 500
        assert r.status_code == 422

    def test_stocks_compare_returns_normalized_series(self, api_client, sample_stocks):
        ids = ",".join(sample_stocks[:2])
        r = api_client.get(f"/stocks/compare?ids={ids}&days=30")
        assert r.status_code == 200
        body = r.json()
        assert body["days"] == 30
        assert isinstance(body["stocks"], list)
        if body["stocks"]:
            s = body["stocks"][0]
            assert "stock_id" in s
            assert "base_price" in s
            assert "data" in s
            # 標準化首日應為 100
            if s["data"]:
                assert abs(s["data"][0]["normalized"] - 100) < 0.01


# ── 系統設定端點 ─────────────────────────────────────────
class TestSettingsEndpoints:
    def test_settings_get_defaults(self, api_client):
        r = api_client.get("/settings")
        assert r.status_code == 200
        body = r.json()
        assert "theme" in body
        assert "language" in body
        assert body["language"] == "zh-TW"
        assert body["telegram"] == {
            "enabled": False,
            "chatId": "",
            "botTokenConfigured": False,
        }
        assert body["email"]["passwordConfigured"] is False
        assert body["system"]["timezone"] == "Asia/Taipei"

    def test_notification_secrets_are_write_only_and_preserved(
        self, api_client
    ):
        headers = {"X-User-ID": "google_secretowner"}
        saved = api_client.put(
            "/settings",
            headers=headers,
            json={
                "telegram": {
                    "enabled": True,
                    "botToken": "telegram-super-secret",
                    "chatId": "123456",
                },
                "email": {
                    "enabled": True,
                    "smtpHost": "smtp.example.com",
                    "smtpPort": 587,
                    "username": "sender@example.com",
                    "password": "email-super-secret",
                    "recipient": "alerts@example.com",
                },
            },
        )
        assert saved.status_code == 200
        saved_text = saved.text
        assert "telegram-super-secret" not in saved_text
        assert "email-super-secret" not in saved_text
        assert saved.json()["settings"]["telegram"]["botTokenConfigured"] is True
        assert saved.json()["settings"]["email"]["passwordConfigured"] is True

        fetched = api_client.get("/settings", headers=headers)
        assert "telegram-super-secret" not in fetched.text
        assert "email-super-secret" not in fetched.text
        assert "botToken" not in fetched.json()["telegram"]
        assert "password" not in fetched.json()["email"]

        preserved = api_client.put(
            "/settings",
            headers=headers,
            json={
                "telegram": {"botToken": ""},
                "email": {"password": ""},
                "extra": {"apiKey": "must-never-leak"},
            },
        )
        assert "must-never-leak" not in preserved.text
        assert preserved.json()["settings"]["telegram"]["botTokenConfigured"] is True
        assert preserved.json()["settings"]["email"]["passwordConfigured"] is True

    def test_telegram_test_uses_saved_user_credentials(
        self, api_client, monkeypatch
    ):
        headers = {"X-User-ID": "google_telegramtest"}
        api_client.put(
            "/settings",
            headers=headers,
            json={
                "telegram": {
                    "enabled": True,
                    "botToken": "saved-token",
                    "chatId": "saved-chat",
                }
            },
        )
        sent = {}

        def fake_send(channel, title, message):
            sent.update(token=channel.token, chat_id=channel.chat_id, title=title)
            return True

        from core.notification import TelegramChannel

        monkeypatch.setattr(TelegramChannel, "send", fake_send)
        response = api_client.post("/settings/test-telegram", headers=headers)

        assert response.status_code == 200
        assert sent == {
            "token": "saved-token",
            "chat_id": "saved-chat",
            "title": "台股戰情中心測試通知",
        }

    def test_settings_put_updates_theme(self, api_client):
        r = api_client.put("/settings", json={"theme": "dark"})
        assert r.status_code == 200
        body = r.json()
        assert body["settings"]["theme"] == "dark"

        # 二次 GET 應拿到更新值（驗證持久化到 tmp DATA_DIR）
        r2 = api_client.get("/settings")
        assert r2.json()["theme"] == "dark"

    def test_settings_are_isolated_by_verified_user_id(self, api_client):
        alice_headers = {"X-User-ID": "google_alice123"}
        bob_headers = {"X-User-ID": "google_bob456"}

        updated = api_client.put(
            "/settings", json={"theme": "dark"}, headers=alice_headers
        )
        assert updated.status_code == 200

        alice = api_client.get("/settings", headers=alice_headers)
        bob = api_client.get("/settings", headers=bob_headers)

        assert alice.json()["theme"] == "dark"
        assert bob.json()["theme"] == "light"

    def test_settings_put_partial_update(self, api_client):
        api_client.put("/settings", json={"theme": "dark", "default_days": 90})
        r = api_client.put("/settings", json={"theme": "light"})
        assert r.status_code == 200
        body = r.json()
        assert body["settings"]["theme"] == "light"
        # default_days 不變
        assert body["settings"]["default_days"] == 90


# ── 404 / 方法不允許 ─────────────────────────────────────
class TestErrorContract:
    def test_unknown_path_returns_404(self, api_client):
        r = api_client.get("/this/does/not/exist")
        assert r.status_code == 404

    def test_wrong_method_returns_405(self, api_client):
        r = api_client.post("/health")
        assert r.status_code == 405
