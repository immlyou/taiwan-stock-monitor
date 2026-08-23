"""Per-user JSON storage paths with legacy owner compatibility."""
from __future__ import annotations

import os
import re
from pathlib import Path


DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "owner")
_SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]{3,128}$")


def normalize_user_id(user_id: str) -> str:
    normalized = str(user_id or "").strip()
    if not _SAFE_USER_ID.fullmatch(normalized):
        raise ValueError("invalid user id")
    return normalized


def user_data_path(user_id: str, filename: str, base_dir: Path | str) -> Path:
    """Resolve one user's data file without allowing path traversal.

    The configured default user keeps the historic ``data/<file>`` location so
    existing single-user deployments retain their data. Other identities are
    isolated under ``data/users/<user_id>/<file>``.
    """
    normalized = normalize_user_id(user_id)
    file_path = Path(filename)
    if file_path.name != filename or filename in {"", ".", ".."}:
        raise ValueError("invalid data filename")

    root = Path(base_dir)
    if normalized == DEFAULT_USER_ID:
        return root / filename
    return root / "users" / normalized / filename


def iter_user_ids(base_dir: Path | str) -> list[str]:
    """List the legacy owner plus every valid namespaced user directory."""
    users = {DEFAULT_USER_ID}
    users_root = Path(base_dir) / "users"
    if users_root.is_dir():
        for path in users_root.iterdir():
            if not path.is_dir():
                continue
            try:
                users.add(normalize_user_id(path.name))
            except ValueError:
                continue
    return [DEFAULT_USER_ID, *sorted(users - {DEFAULT_USER_ID})]
