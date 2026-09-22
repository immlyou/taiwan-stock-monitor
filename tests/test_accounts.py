"""Account permissions are enforced at the API/data boundary, not UI/JWT claims."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import deps, state
from api.routers import accounts, dashboard
from core.accounts import AccountError, AccountStore

OWNER = "owner@example.test"
OWNER_ID = "google_owner"


@pytest.fixture
def store(tmp_path):
    value = AccountStore(tmp_path)
    value.resolve(OWNER_ID, OWNER, bootstrap_email=OWNER)
    return value


def invite(store, email="member@example.test", role="member", user_id="google_member"):
    account = store.invite(OWNER_ID, OWNER, email, role)
    store.resolve(user_id, email, login=True)
    return account


def test_bootstrap_only_exact_owner_and_no_fabricated_login(tmp_path):
    store = AccountStore(tmp_path)
    with pytest.raises(AccountError, match="未受邀"):
        store.resolve("google_stranger", "stranger@example.test", bootstrap_email=OWNER)
    owner = store.resolve(OWNER_ID, OWNER.upper(), bootstrap_email=OWNER)
    assert owner.role == "admin"
    assert owner.last_login_at is None
    login = store.resolve(OWNER_ID, OWNER, login=True, name="Owner")
    assert login.last_login_at and login.name == "Owner"
    with pytest.raises(AccountError):
        store.resolve("google_second", "second@example.test", bootstrap_email="second@example.test")


def test_invitation_requires_oauth_and_binds_immutable_id(store):
    account = store.invite(OWNER_ID, OWNER, "member@example.test", "member")
    assert account.user_id is None
    with pytest.raises(AccountError):
        store.resolve("google_member", account.email)
    first = store.resolve("google_member", account.email, login=True)
    assert first.last_login_at
    with pytest.raises(AccountError):
        store.resolve("google_impostor", account.email, login=True)
    store.invite(OWNER_ID, OWNER, "alias@example.test", "member")
    with pytest.raises(AccountError):
        store.resolve("google_member", "alias@example.test", login=True)


def test_self_change_duplicate_and_stale_update_rejected(store):
    owner = store.resolve(OWNER_ID, OWNER)
    with pytest.raises(AccountError, match="自己"):
        store.update(OWNER_ID, OWNER, owner.id, role="viewer", enabled=False, revision=1)
    member = invite(store)
    with pytest.raises(AccountError, match="已在"):
        store.invite(OWNER_ID, OWNER, member.email.upper(), "viewer")
    store.update(OWNER_ID, OWNER, member.id, role="viewer", enabled=True, revision=1)
    with pytest.raises(AccountError, match="重新載入"):
        store.update(OWNER_ID, OWNER, member.id, role="admin", enabled=True, revision=1)


def test_disabled_account_cannot_login_or_use_existing_identity(store):
    member = invite(store)
    store.update(OWNER_ID, OWNER, member.id, role="member", enabled=False, revision=1)
    for login in (False, True):
        with pytest.raises(AccountError, match="停用"):
            store.resolve("google_member", member.email, login=login)
    assert not store.can_run_jobs("google_member")


def test_changing_bootstrap_email_cannot_revive_or_promote_existing_account(store):
    member = invite(store)
    assert store.resolve("google_member", member.email, bootstrap_email=member.email).role == "member"
    store.update(OWNER_ID, OWNER, member.id, role="member", enabled=False, revision=1)
    with pytest.raises(AccountError):
        store.resolve("google_member", member.email, bootstrap_email=member.email, login=True)


def test_scheduler_skips_disabled_readonly_and_unregistered_users(store, monkeypatch):
    import core.accounts
    import core.alerts
    import core.scheduler
    import core.user_storage
    from api.routers import alerts

    disabled = invite(store)
    invite(store, "viewer@example.test", "viewer", "google_viewer")
    store.update(OWNER_ID, OWNER, disabled.id, role="member", enabled=False, revision=1)
    monkeypatch.setattr(state, "DATA_DIR", store.path.parent)
    monkeypatch.setattr(state.loader, "get", lambda _: None)
    monkeypatch.setattr(core.user_storage, "iter_user_ids", lambda _: [OWNER_ID, "google_member", "google_viewer", "orphan"])
    visited = []

    def legacy_check(data, send_notification, user_id):
        visited.append(("legacy", user_id))
        return []

    async def rules_check(request, user_id):
        visited.append(("rules", user_id))
        return {"triggeredCount": 0}

    monkeypatch.setattr(core.alerts, "check_alerts_and_notify", legacy_check)
    monkeypatch.setattr(alerts, "alert_rules_evaluate", rules_check)
    core.scheduler._alert_check_job()
    assert visited == [("legacy", OWNER_ID), ("rules", OWNER_ID)]


def test_write_failure_does_not_replace_existing_accounts(store, monkeypatch):
    import core.accounts
    original = store.path.read_text()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(core.accounts, "save_json_atomic", fail)
    with pytest.raises(AccountError) as exc:
        store.invite(OWNER_ID, OWNER, "new@example.test", "member")
    assert exc.value.status == 503
    assert store.path.read_text() == original


def test_registry_corruption_fails_closed_without_overwrite(store):
    for invalid in ('{broken', '{"version":1,"accounts":[]}', '{"version":2}'):
        store.path.write_text(invalid)
        with pytest.raises(AccountError) as exc:
            store.resolve(OWNER_ID, OWNER, bootstrap_email=OWNER)
        assert exc.value.status == 503
        assert store.path.read_text() == invalid


def test_concurrent_admin_changes_leave_one_active_admin(store):
    admin = invite(store, "admin@example.test", "admin", "google_admin")
    owner = store.resolve(OWNER_ID, OWNER)

    def disable(actor_id, email, target_id):
        try:
            store.update(actor_id, email, target_id, role="member", enabled=False, revision=1)
            return True
        except AccountError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(disable, OWNER_ID, OWNER, admin.id),
                   pool.submit(disable, "google_admin", admin.email, owner.id)]
        assert sum(f.result() for f in futures) == 1
    assert sum(a.role == "admin" and a.enabled for a in store._load().accounts) == 1


def test_concurrent_duplicate_invites_only_create_one(store):
    def add():
        try:
            store.invite(OWNER_ID, OWNER, "new@example.test", "member")
            return True
        except AccountError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: add(), range(20))) == 1


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setattr(deps, "API_KEY", "test-key")
    monkeypatch.setattr(state, "DATA_DIR", store.path.parent)
    from api import helpers
    monkeypatch.setattr(helpers, "DATA_DIR", store.path.parent)
    app = FastAPI()
    app.include_router(accounts.router)
    app.include_router(dashboard.router)

    @app.post("/refresh", dependencies=[Depends(deps.verify_api_key)])
    @app.get("/alerts/check", dependencies=[Depends(deps.verify_api_key)])
    @app.post("/quote/realtime/batch", dependencies=[Depends(deps.verify_api_key)])
    def operation():
        return {"ok": True}

    return TestClient(app)


def headers(user_id=OWNER_ID, email=OWNER):
    return {"authorization": "Bearer test-key", "x-user-id": user_id, "x-user-email": email}


def test_api_service_key_and_internal_boundary(client):
    body = {"user_id": OWNER_ID, "email": OWNER}
    assert client.post("/internal/accounts/google-login", json=body).status_code == 401
    assert client.post("/internal/accounts/google-login", json=body, headers=headers()).status_code == 403
    assert client.post("/internal/accounts/google-login", json=body,
                       headers={"authorization": "Bearer test-key"}).status_code == 200
    assert client.get("/admin/accounts", headers={"authorization": "Bearer test-key"}).status_code == 401


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_non_admin_cannot_manage_accounts_or_refresh(client, store, role):
    invite(store, role=role)
    actor = headers("google_member", "member@example.test")
    actor["x-role"] = "admin"
    assert client.get("/admin/accounts", headers=actor).status_code == 403
    assert client.post("/admin/accounts", headers=actor, json={"email": "new@example.test"}).status_code == 403
    assert client.post("/refresh", headers=actor).status_code == 403
    assert client.get("/dashboard/config", headers=actor).status_code == 200


def test_live_revocation_viewer_batch_reads_and_no_identity_mismatch(client, store):
    member = invite(store)
    actor = headers("google_member", member.email)
    assert client.get("/accounts/me", headers=actor).status_code == 200
    assert client.get("/accounts/me", headers=headers("google_member", OWNER)).status_code == 403
    assert client.get("/accounts/me", headers=headers("google_member", "")).status_code in (403, 422)
    patch = {"role": "viewer", "enabled": True, "revision": 1}
    assert client.patch(f"/admin/accounts/{member.id}", headers=headers(), json=patch).status_code == 200
    assert client.put("/dashboard/config", headers=actor, json={}).status_code == 403
    assert client.get("/alerts/check", headers=actor).status_code == 403
    assert client.post("/quote/realtime/batch", headers=actor, json={}).status_code == 200
    assert not store.can_run_jobs("google_member")
    patch.update(enabled=False, revision=2)
    assert client.patch(f"/admin/accounts/{member.id}", headers=headers(), json=patch).status_code == 200
    assert client.get("/dashboard/config", headers=actor).status_code == 403


def test_admin_api_validation_and_audit(client):
    assert client.post("/admin/accounts", headers=headers(), json={"email": "bad"}).status_code == 422
    assert client.post("/admin/accounts", headers=headers(), json={"email": "a@example.test", "role": "root"}).status_code == 422
    response = client.post("/admin/accounts", headers=headers(), json={"email": "new@example.test", "role": "viewer"})
    assert response.status_code == 201
    data = client.get("/admin/accounts", headers=headers()).json()
    assert len(data["accounts"]) == 2
    assert data["audit"][0]["action"] == "invite"
    assert data["audit"][0]["actor"] == OWNER
