import pandas as pd

from core.company_profile import get_company_profile


class ProfileLoader:
    def get(self, key):
        if key == "categories":
            return pd.DataFrame({
                "stock_id": ["4933", "2330"],
                "name": ["友輝", "台積電"],
                "category": ["光電業", "半導體"],
            })
        raise KeyError(key)


def test_get_company_profile_uses_local_curated_profile():
    profile = get_company_profile(ProfileLoader(), "4933", refresh=True)

    assert profile["stock_id"] == "4933"
    assert profile["industry"] == "光電業"
    assert "增光膜" in "".join(profile["product_lines"])
    assert profile["revenue_sources"][0]["ratio_pct"] > 0


def test_get_company_profile_falls_back_to_categories(monkeypatch):
    monkeypatch.setattr("core.company_profile._load_local_profiles", lambda: {})
    monkeypatch.setattr("core.company_profile._profile_from_goodinfo", lambda stock_id: {})
    monkeypatch.setattr("core.company_profile._profile_from_openapi", lambda stock_id: {})

    profile = get_company_profile(ProfileLoader(), "2330", refresh=True)

    assert profile["name"] == "台積電"
    assert profile["industry"] == "半導體"
