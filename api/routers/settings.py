"""系統設定 (Settings) 端點"""
from __future__ import annotations

import logging
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_user_id, verify_api_key
from api.helpers import _load_json_file, _save_json_file
from api.models import SettingsUpdateRequest

logger = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"

_DEFAULTS = {
    "theme": "light",
    "language": "zh-TW",
    "notifications_enabled": True,
    "default_days": 60,
    "telegram": {
        "enabled": False,
        "botToken": "",
        "chatId": "",
    },
    "email": {
        "enabled": False,
        "smtpHost": "smtp.gmail.com",
        "smtpPort": 587,
        "username": "",
        "password": "",
        "recipient": "",
    },
    "system": {
        "dataUpdateInterval": 30,
        "timezone": "Asia/Taipei",
        "autoBacktest": False,
        "marketOpenTime": "09:00",
        "marketCloseTime": "13:30",
    },
}

router = APIRouter(tags=["設定"], dependencies=[Depends(verify_api_key)])

_SECRET_KEY_NAMES = {
    "token",
    "bottoken",
    "password",
    "apikey",
    "secret",
    "clientsecret",
}


def _settings_with_defaults(stored: dict | None) -> dict:
    settings = deepcopy(_DEFAULTS)
    for key, value in (stored or {}).items():
        if key in {"telegram", "email", "system"} and isinstance(value, dict):
            settings[key].update(value)
        else:
            settings[key] = value

    # Migrate the pre-contract notification keys without dropping credentials.
    telegram = settings["telegram"]
    telegram["botToken"] = telegram.get("botToken") or telegram.get("token", "")
    telegram["chatId"] = telegram.get("chatId") or telegram.get("chat_id", "")
    telegram.pop("token", None)
    telegram.pop("chat_id", None)

    email = settings["email"]
    email["smtpHost"] = email.get("smtpHost") or email.get("smtp_server", "smtp.gmail.com")
    email["smtpPort"] = email.get("smtpPort") or email.get("smtp_port", 587)
    email["username"] = email.get("username") or email.get("sender", "")
    if not email.get("recipient"):
        recipients = email.get("recipients", [])
        email["recipient"] = recipients[0] if recipients else ""
    for old_key in ("smtp_server", "smtp_port", "sender", "recipients"):
        email.pop(old_key, None)
    # Report effective capabilities, not old saved values that never affected
    # a scheduler. Leave raw storage intact until the user next saves settings.
    settings["system"].update(timezone="Asia/Taipei", autoBacktest=False,
                              marketOpenTime="09:00", marketCloseTime="13:30")
    return settings


def _public_settings(settings: dict) -> dict:
    public = deepcopy(settings)
    telegram = public["telegram"]
    telegram["botTokenConfigured"] = bool(telegram.pop("botToken", ""))
    email = public["email"]
    email["passwordConfigured"] = bool(email.pop("password", ""))
    return _strip_unknown_secrets(public)


def _strip_unknown_secrets(value):
    if isinstance(value, dict):
        return {
            key: _strip_unknown_secrets(item)
            for key, item in value.items()
            if key.replace("_", "").lower() not in _SECRET_KEY_NAMES
        }
    if isinstance(value, list):
        return [_strip_unknown_secrets(item) for item in value]
    return value


@router.get("/settings")
async def settings_get(user_id: str = Depends(get_user_id)):
    """取得系統設定。"""
    try:
        stored = _load_json_file(SETTINGS_FILE, default={}, user_id=user_id)
        return _public_settings(_settings_with_defaults(stored))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def settings_update(
    req: SettingsUpdateRequest, user_id: str = Depends(get_user_id)
):
    """更新系統設定。"""
    try:
        stored = _load_json_file(SETTINGS_FILE, default={}, user_id=user_id)
        data = _settings_with_defaults(stored)
        if req.theme is not None:
            data["theme"] = req.theme
        if req.language is not None:
            data["language"] = req.language
        if req.notifications_enabled is not None:
            data["notifications_enabled"] = req.notifications_enabled
        if req.default_days is not None:
            data["default_days"] = req.default_days
        if req.extra:
            for key, value in req.extra.items():
                normalized_key = key.replace("_", "").lower()
                if (
                    key not in {"telegram", "email", "system"}
                    and normalized_key not in _SECRET_KEY_NAMES
                ):
                    data[key] = value

        updates = req.model_dump(exclude_none=True)
        updates.pop("extra", None)
        for section in ("telegram", "email", "system"):
            section_update = updates.get(section)
            if not section_update:
                continue
            for key, value in section_update.items():
                # Empty secret fields mean "leave the existing credential alone".
                if key in {"botToken", "password"} and not str(value).strip():
                    continue
                data[section][key] = value
        _save_json_file(SETTINGS_FILE, data, user_id=user_id)
        return {"message": "更新成功", "settings": _public_settings(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/test-telegram")
async def settings_test_telegram(user_id: str = Depends(get_user_id)):
    """Send one test message using this user's stored write-only credentials."""
    stored = _load_json_file(SETTINGS_FILE, default={}, user_id=user_id)
    settings = _settings_with_defaults(stored)
    telegram = settings["telegram"]
    if not telegram.get("botToken") or not telegram.get("chatId"):
        raise HTTPException(status_code=422, detail="Telegram Bot Token 或 Chat ID 未設定")

    try:
        from core.notification import TelegramChannel

        channel = TelegramChannel(
            token=telegram["botToken"], chat_id=telegram["chatId"]
        )
        channel.send(
            "台股戰情中心測試通知",
            "Google 帳號的 Telegram 通知設定已連線成功。",
        )
        return {"message": "Telegram 測試通知已送出"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Telegram test notification failed")
        raise HTTPException(status_code=502, detail="Telegram 測試通知傳送失敗") from exc
