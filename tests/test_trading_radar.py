import pandas as pd

from core.trading_radar import TradingRadar


class RadarLoader:
    def __init__(self):
        dates = pd.date_range("2024-01-01", periods=90, freq="D")
        self.data = {
            "close": pd.DataFrame({
                "2330": [100 + i * 0.5 for i in range(90)],
                "2317": [80 + i * 0.1 for i in range(90)],
                "2454": [120 - i * 0.2 for i in range(90)],
            }, index=dates),
            "open": pd.DataFrame({
                "2330": [99 + i * 0.5 for i in range(90)],
                "2317": [79 + i * 0.1 for i in range(90)],
                "2454": [121 - i * 0.2 for i in range(90)],
            }, index=dates),
            "volume": pd.DataFrame({
                "2330": [1000] * 85 + [1300, 1350, 1400, 1500, 1600],
                "2317": [900] * 90,
                "2454": [800] * 89 + [2400],
            }, index=dates),
            "pe_ratio": pd.DataFrame({"2330": [15] * 90, "2317": [20] * 90, "2454": [30] * 90}, index=dates),
            "pb_ratio": pd.DataFrame({"2330": [2] * 90, "2317": [2.5] * 90, "2454": [5] * 90}, index=dates),
            "dividend_yield": pd.DataFrame({"2330": [4] * 90, "2317": [3] * 90, "2454": [1] * 90}, index=dates),
            "revenue_yoy": pd.DataFrame({"2330": [45] * 90, "2317": [12] * 90, "2454": [-8] * 90}, index=dates),
            "revenue_mom": pd.DataFrame({"2330": [18] * 90, "2317": [3] * 90, "2454": [-12] * 90}, index=dates),
            "market_value": pd.DataFrame({"2330": [1000] * 90, "2317": [800] * 90, "2454": [500] * 90}, index=dates),
            "foreign_investors": pd.DataFrame({"2330": [100] * 90, "2317": [0] * 90, "2454": [-100] * 90}, index=dates),
            "investment_trust": pd.DataFrame({"2330": [50] * 90, "2317": [0] * 90, "2454": [-50] * 90}, index=dates),
            "dealer": pd.DataFrame({"2330": [20] * 90, "2317": [0] * 90, "2454": [-20] * 90}, index=dates),
            "categories": pd.DataFrame({
                "stock_id": ["2330", "2317", "2454"],
                "name": ["台積電", "鴻海", "聯發科"],
                "category": ["半導體", "電子代工", "半導體"],
            }),
        }

    def get(self, key):
        return self.data[key]


def test_trading_radar_analyze_stock_returns_action_and_signals():
    result = TradingRadar(RadarLoader()).analyze_stock("2330")

    assert result["stock_id"] == "2330"
    assert result["action"]
    assert result["radar_score"] >= 0
    assert "accumulation" in result["signals"]
    assert result["invalidation_conditions"]


def test_trading_radar_scan_returns_categories(monkeypatch):
    monkeypatch.setattr("core.trading_radar.get_active_stocks", lambda: ["2330", "2317", "2454"])

    result = TradingRadar(RadarLoader()).scan(top_n=10)

    assert result["stocks"]
    assert "accumulation" in result["categories"]
    assert "distribution_risk" in result["categories"]
