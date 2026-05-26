"""
API 認證（Bearer Token）行為測試。

驗證 verify_api_key 在三種狀態下的行為：
- API_KEY 為空 → 開放存取
- API_KEY 已設定 → 缺 token / 錯 token → 401
- API_KEY 已設定 → 正確 token → 200

實作策略：用 monkeypatch.setattr 直接改 api.deps.API_KEY，
避免 importlib.reload 造成跨測試污染。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_no_auth(monkeypatch):
    import api.deps
    monkeypatch.setattr(api.deps, "API_KEY", "")
    from api_server import app
    return TestClient(app)


@pytest.fixture
def client_with_auth(monkeypatch):
    import api.deps
    monkeypatch.setattr(api.deps, "API_KEY", "secret-key")
    from api_server import app
    return TestClient(app)


class TestNoAuth:
    """API_KEY 為空 → 所有受保護端點皆放行"""

    def test_settings_accessible_without_token(self, client_no_auth):
        r = client_no_auth.get("/settings")
        assert r.status_code == 200

    def test_health_always_accessible(self, client_no_auth):
        r = client_no_auth.get("/health")
        assert r.status_code == 200


class TestWithAuth:
    """設定 API_KEY → 受保護端點需要正確 Bearer Token"""

    def test_missing_token_returns_401(self, client_with_auth):
        r = client_with_auth.get("/settings")
        assert r.status_code == 401
        assert "API Key" in r.json().get("detail", "")

    def test_wrong_token_returns_401(self, client_with_auth):
        r = client_with_auth.get(
            "/settings",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401

    def test_correct_token_returns_200(self, client_with_auth):
        r = client_with_auth.get(
            "/settings",
            headers={"Authorization": "Bearer secret-key"},
        )
        assert r.status_code == 200

    def test_public_endpoints_remain_open(self, client_with_auth):
        """/, /health, /openapi.json 不應被認證擋住"""
        assert client_with_auth.get("/").status_code == 200
        assert client_with_auth.get("/health").status_code == 200
        assert client_with_auth.get("/openapi.json").status_code == 200
