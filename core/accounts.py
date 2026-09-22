"""Invite-only Google accounts. Single-worker, atomic registry and audit log.

Only the authenticated server gateway may supply a verified Google identity or
bootstrap email. Never accept these values from a browser request body/header.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.json_store import file_lock, save_json_atomic

Role = Literal["admin", "member", "viewer"]


class AccountError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


class Account(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    email: str
    user_id: str | None = None
    name: str = ""
    role: Role = "member"
    enabled: bool = True
    created_at: str
    last_login_at: str | None = None
    revision: int = 1


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    accounts: list[Account] = Field(default_factory=list)
    audit: list[dict] = Field(default_factory=list)


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise AccountError(422, "請輸入有效的 Google Email")
    return value


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AccountStore:
    def __init__(self, root: Path):
        self.path = root / "accounts.json"

    def _load(self) -> Registry:
        if not self.path.exists():
            return Registry()
        try:
            registry = Registry.model_validate_json(self.path.read_text(encoding="utf-8"))
            emails = [a.email for a in registry.accounts]
            ids = [a.id for a in registry.accounts]
            users = [a.user_id for a in registry.accounts if a.user_id]
            if (not registry.accounts or len(set(emails)) != len(emails)
                    or len(set(ids)) != len(ids) or len(set(users)) != len(users)):
                raise ValueError("invalid registry")
            return registry
        except (OSError, ValueError, ValidationError) as exc:
            raise AccountError(503, "帳號資料暫時無法讀取，請聯絡管理員") from exc

    def _save(self, registry: Registry, actor: str, action: str, target: Account):
        registry.audit.append({
            "at": now(), "actor": actor, "action": action,
            "email": target.email, "role": target.role, "enabled": target.enabled,
        })
        registry.audit = registry.audit[-500:]
        try:
            save_json_atomic(self.path, registry.model_dump())
        except OSError as exc:
            raise AccountError(503, "帳號資料儲存失敗，請稍後重試") from exc

    @staticmethod
    def _active(registry: Registry, user_id: str, email: str) -> Account:
        account = next((a for a in registry.accounts if a.user_id == user_id and a.email == email), None)
        if not account or not account.enabled:
            raise AccountError(403, "此帳號尚未受邀或已停用，請聯絡管理員")
        return account

    def resolve(self, user_id: str, email: str, *, bootstrap_email: str = "",
                login: bool = False, name: str = "") -> Account:
        if not re.fullmatch(r"google_[A-Za-z0-9_-]{1,120}", user_id):
            raise AccountError(403, "無效的 Google 帳號識別碼")
        email = normalize_email(email)
        with file_lock(self.path):
            registry = self._load()
            if not registry.accounts and bootstrap_email and email == normalize_email(bootstrap_email):
                account = Account(id=str(uuid4()), email=email, user_id=user_id,
                                  role="admin", created_at=now())
                registry.accounts.append(account)
                self._save(registry, email, "bootstrap", account)
            account = next((a for a in registry.accounts if a.email == email), None)
            if not account or not account.enabled:
                raise AccountError(403, "此帳號尚未受邀或已停用，請聯絡管理員")
            # Invitations can only be bound during verified Google OAuth login,
            # never by replaying an old session cookie for an unbound account.
            if account.user_id is None and login:
                if any(a.user_id == user_id for a in registry.accounts):
                    raise AccountError(403, "Google 帳號已綁定其他 Email")
                account.user_id = user_id
            if account.user_id != user_id:
                raise AccountError(403, "Google 帳號識別碼不符，請聯絡管理員")
            if login:
                account.name = name[:120]
                account.last_login_at = now()
                self._save(registry, email, "login", account)
            return account

    def _admin(self, registry: Registry, user_id: str, email: str) -> Account:
        account = self._active(registry, user_id, normalize_email(email))
        if account.role != "admin":
            raise AccountError(403, "此操作需要管理員權限")
        return account

    def list(self, user_id: str, email: str) -> dict:
        with file_lock(self.path):
            registry = self._load()
            self._admin(registry, user_id, email)
            return {"accounts": [a.model_dump() for a in registry.accounts],
                    "audit": list(reversed(registry.audit[-100:]))}

    def can_run_jobs(self, user_id: str) -> bool:
        with file_lock(self.path):
            # Preserve legacy local tooling before the registry is initialized.
            if not self.path.exists():
                return True
            registry = self._load()
            return any(a.user_id == user_id and a.enabled and a.role != "viewer"
                       for a in registry.accounts)

    def invite(self, user_id: str, actor_email: str, email: str, role: Role) -> Account:
        email = normalize_email(email)
        with file_lock(self.path):
            registry = self._load()
            actor = self._admin(registry, user_id, actor_email)
            if any(a.email == email for a in registry.accounts):
                raise AccountError(409, "此 Email 已在帳號名單中")
            account = Account(id=str(uuid4()), email=email, role=role, created_at=now())
            registry.accounts.append(account)
            self._save(registry, actor.email, "invite", account)
            return account

    def update(self, user_id: str, email: str, account_id: str, *, role: Role,
               enabled: bool, revision: int) -> Account:
        with file_lock(self.path):
            registry = self._load()
            actor = self._admin(registry, user_id, email)
            account = next((a for a in registry.accounts if a.id == account_id), None)
            if not account:
                raise AccountError(404, "帳號不存在")
            if account.id == actor.id:
                raise AccountError(409, "不能調整自己的權限或停用自己")
            if account.revision != revision:
                raise AccountError(409, "帳號已被更新，請重新載入後再修改")
            if account.role == "admin" and account.enabled and (role != "admin" or not enabled):
                if not any(a.id != account.id and a.role == "admin" and a.enabled and a.user_id
                           for a in registry.accounts):
                    raise AccountError(409, "至少需要保留一位已登入的啟用管理員")
            account.role, account.enabled = role, enabled
            account.revision += 1
            self._save(registry, actor.email, "update", account)
            return account


def authorize_request(account: Account, method: str, path: str) -> None:
    path = path.rstrip("/")
    if (path == "/refresh" or path.startswith("/admin/")) and account.role != "admin":
        raise AccountError(403, "此操作需要管理員權限")
    if account.role == "viewer" and (
        (method not in {"GET", "HEAD", "OPTIONS"} and not (method == "POST" and path == "/quote/realtime/batch"))
        or path == "/alerts/check"
    ):
        raise AccountError(403, "唯讀帳號不能新增、修改、刪除或執行此操作")
