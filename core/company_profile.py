"""Company profile enrichment for listed and OTC Taiwan stocks."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCAL_PROFILE_FILE = DATA_DIR / "company_profiles.json"
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TS: Dict[str, float] = {}
_CACHE_TTL = 60 * 60 * 12

OPENAPI_SOURCES = [
    {
        "market": "上市",
        "name": "TWSE OpenAPI 公司基本資料",
        "url": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
    },
    {
        "market": "上櫃",
        "name": "TPEx OpenAPI 公司基本資料",
        "url": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
    },
]


def _empty_profile(stock_id: str) -> Dict[str, Any]:
    return {
        "stock_id": stock_id,
        "name": "",
        "company_full_name": "",
        "market": "",
        "industry": "",
        "business_scope": "",
        "business_summary": "",
        "product_lines": [],
        "revenue_sources": [],
        "website": "",
        "capital": "",
        "chairman": "",
        "general_manager": "",
        "profile_sources": [],
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
    }


def _load_local_profiles() -> Dict[str, Dict[str, Any]]:
    if not LOCAL_PROFILE_FILE.exists():
        return {}
    try:
        with open(LOCAL_PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("讀取公司補充資料失敗: %s", e)
        return {}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _merge_profile(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    result = {**base}
    for key, value in extra.items():
        if value in (None, "", [], {}):
            continue
        if key == "profile_sources":
            existing = result.get("profile_sources") or []
            result[key] = existing + [s for s in value if s not in existing]
        else:
            result[key] = value
    return result


def _profile_from_categories(loader: Any, stock_id: str) -> Dict[str, Any]:
    profile: Dict[str, Any] = {}
    try:
        categories = loader.get("categories")
        rows = categories[categories["stock_id"].astype(str) == stock_id] if "stock_id" in categories.columns else categories.loc[[stock_id]]
        if rows.empty:
            return profile
        row = rows.iloc[0]
        profile["name"] = _clean_text(row.get("name", ""))
        for column in ("category", "industry", "產業", "類別"):
            if column in row and _clean_text(row.get(column)):
                profile["industry"] = _clean_text(row.get(column))
                break
    except Exception:
        pass
    return profile


def _profile_from_goodinfo(stock_id: str) -> Dict[str, Any]:
    try:
        from core.goodinfo import fetch_stock_detail
        detail = fetch_stock_detail(stock_id)
    except Exception:
        detail = None
    if not detail:
        return {}
    return {
        "name": detail.get("name"),
        "market": detail.get("market"),
        "industry": detail.get("industry"),
        "capital": detail.get("capital"),
        "profile_sources": [{"name": "Goodinfo 公司基本資料", "url": f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={stock_id}"}],
    }


def _fetch_openapi_rows(url: str) -> list[dict[str, Any]]:
    response = requests.get(url, timeout=10, headers={"User-Agent": "taiwan-stock-monitor/1.0"})
    response.raise_for_status()
    if not response.text.strip():
        return []
    data = response.json()
    return data if isinstance(data, list) else []


def _profile_from_openapi(stock_id: str) -> Dict[str, Any]:
    for source in OPENAPI_SOURCES:
        try:
            rows = _fetch_openapi_rows(source["url"])
        except Exception as e:
            logger.debug("OpenAPI 公司基本資料讀取失敗 %s: %s", source["name"], e)
            continue
        for row in rows:
            if _clean_text(row.get("公司代號")) != stock_id:
                continue
            business = _clean_text(row.get("主要經營業務"))
            return {
                "name": _clean_text(row.get("公司簡稱") or row.get("公司名稱")),
                "company_full_name": _clean_text(row.get("公司名稱")),
                "market": source["market"],
                "industry": _clean_text(row.get("產業別")),
                "business_scope": business,
                "business_summary": business,
                "website": _clean_text(row.get("網址")),
                "capital": _clean_text(row.get("實收資本額")),
                "chairman": _clean_text(row.get("董事長")),
                "general_manager": _clean_text(row.get("總經理")),
                "profile_sources": [{"name": source["name"], "url": source["url"]}],
            }
    return {}


def get_company_profile(loader: Any, stock_id: str, *, refresh: bool = False) -> Dict[str, Any]:
    """Return enriched company profile data for a stock.

    Merge order:
    1. FinLab categories fallback
    2. Goodinfo basic detail
    3. TWSE/TPEx OpenAPI basic company data
    4. local curated `data/company_profiles.json` override
    """
    normalized_id = str(stock_id).strip()
    if not normalized_id:
        raise KeyError("stock_id is required")

    cached = _CACHE.get(normalized_id)
    if cached and not refresh and time.time() - _CACHE_TS.get(normalized_id, 0) < _CACHE_TTL:
        return cached

    profile = _empty_profile(normalized_id)
    profile = _merge_profile(profile, _profile_from_categories(loader, normalized_id))
    profile = _merge_profile(profile, _profile_from_goodinfo(normalized_id))
    profile = _merge_profile(profile, _profile_from_openapi(normalized_id))
    profile = _merge_profile(profile, _load_local_profiles().get(normalized_id, {}))

    if not profile.get("name") and not profile.get("company_full_name") and not profile.get("industry"):
        raise KeyError(f"找不到公司基本資料: {stock_id}")

    if not profile.get("business_summary") and profile.get("business_scope"):
        profile["business_summary"] = profile["business_scope"]

    _CACHE[normalized_id] = profile
    _CACHE_TS[normalized_id] = time.time()
    return profile
