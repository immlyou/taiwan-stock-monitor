"""Release identity loaded from the repository's canonical manifest."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

_MANIFEST_PATH: Final = Path(__file__).resolve().parents[1] / "release-manifest.json"
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _load_release_manifest() -> dict[str, object]:
    try:
        manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"無法讀取版本 manifest: {_MANIFEST_PATH}") from exc

    for key in ("productVersion", "frontendVersion", "apiVersion", "releaseDate"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise RuntimeError(f"版本 manifest 缺少有效欄位: {key}")
    for key in ("productVersion", "frontendVersion", "apiVersion"):
        if not _SEMVER.fullmatch(str(manifest[key])):
            raise RuntimeError(f"版本 manifest 的 {key} 不是 semver")
    return manifest


RELEASE_MANIFEST: Final = _load_release_manifest()
RELEASE_VERSION: Final = str(RELEASE_MANIFEST["productVersion"])
FRONTEND_VERSION: Final = str(RELEASE_MANIFEST["frontendVersion"])
API_VERSION: Final = str(RELEASE_MANIFEST["apiVersion"])
RELEASE_DATE: Final = str(RELEASE_MANIFEST["releaseDate"])
