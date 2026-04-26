import numpy as np
import pandas as pd
import pytest

from core.stock_score import calculate_score_table, calculate_stock_score, calculate_top_scores


class FakeLoader:
    def __init__(self, data):
        self.data = data

    def get(self, key):
        if key not in self.data:
            raise FileNotFoundError(key)
        return self.data[key]


@pytest.fixture
def score_loader():
    dates = pd.date_range("2026-01-01", periods=140, freq="B")
    close = pd.DataFrame({
        "2330": np.linspace(100, 180, len(dates)),
        "2317": np.linspace(100, 95, len(dates)),
        "2454": np.linspace(80, 120, len(dates)),
    }, index=dates)
    volume = pd.DataFrame({
        "2330": np.linspace(1000, 2500, len(dates)),
        "2317": np.linspace(1500, 1000, len(dates)),
        "2454": np.linspace(800, 1200, len(dates)),
    }, index=dates)

    latest = pd.DatetimeIndex([dates[-1]])
    point = lambda values: pd.DataFrame([values], index=latest)

    return FakeLoader({
        "close": close,
        "volume": volume,
        "market_value": point({"2330": 1000, "2317": 500, "2454": 700}),
        "is_flagged": point({"2330": 0, "2317": 0, "2454": 1}),
        "pe_ratio": point({"2330": 18, "2317": 12, "2454": 30}),
        "pb_ratio": point({"2330": 2.0, "2317": 1.2, "2454": 4.0}),
        "dividend_yield": point({"2330": 3.0, "2317": 5.0, "2454": 1.5}),
        "revenue_yoy": point({"2330": 25, "2317": -5, "2454": 10}),
        "revenue_mom": point({"2330": 8, "2317": -2, "2454": 4}),
        "foreign_investors": point({"2330": 10000, "2317": -2000, "2454": 3000}),
        "investment_trust": point({"2330": 5000, "2317": 1000, "2454": -500}),
        "dealer": point({"2330": 1000, "2317": -300, "2454": 200}),
        "foreign_holding": point({"2330": 70, "2317": 40, "2454": 55}),
        "inventory_over_1000_ratio": point({"2330": 65, "2317": 45, "2454": 50}),
        "inventory_under_10_ratio": point({"2330": 10, "2317": 25, "2454": 20}),
    })


def test_calculate_score_table_has_expected_shape(score_loader):
    table = calculate_score_table(score_loader)

    expected = {"stock_id", "total_score", "rating", "value", "growth", "momentum", "chip", "quality", "risk"}
    assert expected.issubset(table.columns)
    assert len(table) == 3
    assert table["total_score"].dropna().between(0, 100).all()


def test_calculate_stock_score_returns_scorecard_record(score_loader):
    record = calculate_stock_score(score_loader, "2330")

    assert record["stock_id"] == "2330"
    assert record["rating"] in {"A", "B", "C", "D", "F"}
    assert record["total_score"] is not None
    assert set(record["component_scores"]) == {"value", "growth", "momentum", "chip", "quality", "risk"}
    assert record["available_components"] >= 1


def test_calculate_top_scores_limits_result_count(score_loader):
    result = calculate_top_scores(score_loader, top_n=2)

    assert result["total"] == 3
    assert len(result["stocks"]) == 2


def test_calculate_stock_score_unknown_raises(score_loader):
    with pytest.raises(KeyError):
        calculate_stock_score(score_loader, "9999")


def test_calculate_stock_score_tolerates_missing_optional_inputs(score_loader):
    loader = FakeLoader({
        "close": score_loader.data["close"],
        "pe_ratio": score_loader.data["pe_ratio"],
    })

    record = calculate_stock_score(loader, "2330")

    assert record["stock_id"] == "2330"
    assert record["total_score"] is not None
    assert record["available_components"] >= 1
