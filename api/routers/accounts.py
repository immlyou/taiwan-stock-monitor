"""Server-to-server identity registration and administrator account management."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from api import deps
from core.accounts import AccountError, Role

router = APIRouter(tags=["帳號管理"])


class GoogleIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(max_length=128)
    email: str = Field(max_length=254)
    name: str = Field(default="", max_length=120)
    bootstrap_email: str = Field(default="", max_length=254)


class Invite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    role: Role = "member"


class UpdateAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Role
    enabled: bool
    revision: int = Field(ge=1)


def call_store(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except AccountError as exc:
        raise HTTPException(exc.status, exc.message) from exc


@router.post("/internal/accounts/google-login", dependencies=[Depends(deps.verify_service_key)])
def google_login(body: GoogleIdentity, request: Request):
    # Never enable identity assertions in unauthenticated local-dev mode either.
    if not deps.API_KEY or request.headers.get("x-user-id"):
        raise HTTPException(403, "僅允許登入服務呼叫")
    return call_store(deps.account_store().resolve, **body.model_dump(), login=True)


def current_account(request: Request, _: bool = Depends(deps.verify_api_key)):
    account = getattr(request.state, "account", None)
    if not account:
        raise HTTPException(401, "需要已驗證的 Google 帳號")
    return account


@router.get("/accounts/me")
def me(account=Depends(current_account)):
    return account


@router.get("/admin/accounts")
def list_accounts(account=Depends(current_account)):
    return call_store(deps.account_store().list, account.user_id, account.email)


@router.post("/admin/accounts", status_code=201)
def invite_account(body: Invite, account=Depends(current_account)):
    return call_store(deps.account_store().invite, account.user_id, account.email, **body.model_dump())


@router.patch("/admin/accounts/{account_id}")
def update_account(account_id: str, body: UpdateAccount, account=Depends(current_account)):
    return call_store(deps.account_store().update, account.user_id, account.email,
                      account_id, **body.model_dump())
