import pandas as pd

from core.intelligence import (
    calculate_industry_rotation,
    diagnose_portfolio,
    evaluate_smart_alerts,
    generate_stock_summary,
)


class FakeLoader:
    def __init__(self):
        dates = pd.date_range("2024-01-01", periods=80, freq="D")
        self.data = {
            "close": pd.DataFrame({
                "2330": [100 + i for i in range(80)],
                "2317": [90 + i * 0.4 for i in range(80)],
                "2454": [80 - i * 0.1 for i in range(80)],
            }, index=dates),
            "volume": pd.DataFrame({
                "2330": [1000] * 79 + [3000],
                "2317": [900] * 80,
                "2454": [800] * 80,
            }, index=dates),
            "pe_ratio": pd.DataFrame({"2330": [15] * 80, "2317": [18] * 80, "2454": [30] * 80}, index=dates),
            "pb_ratio": pd.DataFrame({"2330": [2] * 80, "2317": [3] * 80, "2454": [5] * 80}, index=dates),
            "dividend_yield": pd.DataFrame({"2330": [4] * 80, "2317": [3] * 80, "2454": [1] * 80}, index=dates),
            "revenue_yoy": pd.DataFrame({"2330": [20] * 80, "2317": [10] * 80, "2454": [-5] * 80}, index=dates),
            "revenue_mom": pd.DataFrame({"2330": [5] * 80, "2317": [2] * 80, "2454": [-2] * 80}, index=dates),
            "market_value": pd.DataFrame({"2330": [1000] * 80, "2317": [800] * 80, "2454": [500] * 80}, index=dates),
            "foreign_investors": pd.DataFrame({"2330": [100] * 80, "2317": [50] * 80, "2454": [-10] * 80}, index=dates),
            "investment_trust": pd.DataFrame({"2330": [50] * 80, "2317": [10] * 80, "2454": [-5] * 80}, index=dates),
            "dealer": pd.DataFrame({"2330": [10] * 80, "2317": [5] * 80, "2454": [-2] * 80}, index=dates),
            "foreign_holding": pd.DataFrame({"2330": [60] * 80, "2317": [40] * 80, "2454": [20] * 80}, index=dates),
            "categories": pd.DataFrame({
                "stock_id": ["2330", "2317", "2454"],
                "name": ["台積電", "鴻海", "聯發科"],
                "category": ["半導體", "電子代工", "半導體"],
            }),
        }

    def get(self, key):
        return self.data[key]


def test_generate_stock_summary_contains_stance_and_points():
    summary = generate_stock_summary(FakeLoader(), "2330")

    assert summary["stock_id"] == "2330"
    assert summary["stance"]
    assert summary["key_points"]


def test_evaluate_smart_alerts_returns_signal():
    result = evaluate_smart_alerts(FakeLoader(), stock_ids=["2330"], top_n=5)

    assert result["total"] >= 1
    assert result["alerts"][0]["stock_id"] == "2330"
    assert result["alerts"][0]["reasons"]


def test_diagnose_portfolio_returns_allocation_and_risk():
    portfolio = {
        "holdings": [
            {"stock_id": "2330", "shares": 10, "cost_price": 100},
            {"stock_id": "2317", "shares": 5, "cost_price": 90},
        ]
    }

    result = diagnose_portfolio(FakeLoader(), "default", portfolio)

    assert result["holdings_count"] == 2
    assert result["allocation"]
    assert "annualized_volatility_pct" in result["risk"]


def test_calculate_industry_rotation_ranks_industries(monkeypatch):
    monkeypatch.setattr("core.intelligence.get_active_stocks", lambda: ["2330", "2317", "2454"])

    result = calculate_industry_rotation(FakeLoader(), top_n=10)

    assert result["industries"]
    assert {"industry", "rotation_score", "quadrant"}.issubset(result["industries"][0])
