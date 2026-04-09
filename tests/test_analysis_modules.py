"""
熱門股票、遺珠掃描、報告生成模組測試
涵蓋：hot_stocks、hidden_gems、report_generator
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from pathlib import Path


# ──────────────────────────────────────────────
# hot_stocks
# ──────────────────────────────────────────────
from core.hot_stocks import HotStockScore, HotStockAnalyzer


class TestHotStockScore:
    def _make_score(self, **kwargs):
        defaults = dict(
            stock_id="2330", name="台積電", industry="半導體",
            total_score=75.0, news_score=80.0, volume_score=70.0,
            momentum_score=75.0, volume_ratio=2.5, price_change_5d=3.5,
            price_change_20d=8.0, current_price=600.0
        )
        defaults.update(kwargs)
        return HotStockScore(**defaults)

    def test_is_high_volume_true(self):
        s = self._make_score(volume_ratio=2.5)
        assert s.is_high_volume is True

    def test_is_high_volume_false(self):
        s = self._make_score(volume_ratio=1.5)
        assert s.is_high_volume is False

    def test_is_positive_news(self):
        s = self._make_score(news_sentiment=0.5)
        assert s.is_positive_news is True

    def test_is_negative_news(self):
        s = self._make_score(news_sentiment=-0.5)
        assert s.is_negative_news is True

    def test_neutral_news(self):
        s = self._make_score(news_sentiment=0.0)
        assert not s.is_positive_news
        assert not s.is_negative_news

    def test_trend_direction_strong_up(self):
        s = self._make_score(price_change_5d=5.0)
        assert s.trend_direction == "強勢上漲"

    def test_trend_direction_mild_up(self):
        s = self._make_score(price_change_5d=1.5)
        assert s.trend_direction == "溫和上漲"

    def test_trend_direction_mild_down(self):
        s = self._make_score(price_change_5d=-1.5)
        assert s.trend_direction == "溫和下跌"

    def test_trend_direction_sharp_down(self):
        s = self._make_score(price_change_5d=-5.0)
        assert s.trend_direction == "明顯下跌"

    def test_default_tags_empty(self):
        s = self._make_score()
        assert s.tags == []


@pytest.fixture(scope="module")
def hot_dates():
    return pd.date_range("2022-01-01", periods=60, freq="B")


@pytest.fixture(scope="module")
def hot_close(hot_dates):
    np.random.seed(0)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, (60, 3)), axis=0))
    return pd.DataFrame(prices, index=hot_dates, columns=["2330", "2317", "2454"])


@pytest.fixture(scope="module")
def hot_volume(hot_dates):
    np.random.seed(1)
    data = np.random.randint(1000, 50000, (60, 3)).astype(float) * 1000
    # 讓 2330 最後幾天爆量
    data[-5:, 0] *= 5
    return pd.DataFrame(data, index=hot_dates, columns=["2330", "2317", "2454"])


@pytest.fixture
def mock_loader(hot_close, hot_volume):
    loader = MagicMock()
    loader.get.side_effect = lambda key, **kwargs: {
        "close": hot_close,
        "volume": hot_volume,
    }.get(key)
    return loader


class TestHotStockAnalyzer:

    def test_init(self):
        with patch("core.hot_stocks.get_loader", return_value=MagicMock()):
            analyzer = HotStockAnalyzer()
            assert analyzer.news_weight == 0.4

    def test_calculate_volume_scores(self, mock_loader):
        with patch("core.hot_stocks.get_loader", return_value=mock_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_volume_scores()
            assert isinstance(results, dict)

    def test_volume_score_range(self, mock_loader):
        with patch("core.hot_stocks.get_loader", return_value=mock_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_volume_scores()
            for stock_id, info in results.items():
                assert 0 <= info["score"] <= 100

    def test_calculate_momentum_scores(self, mock_loader):
        with patch("core.hot_stocks.get_loader", return_value=mock_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_momentum_scores()
            assert isinstance(results, dict)

    def test_momentum_score_range(self, mock_loader):
        with patch("core.hot_stocks.get_loader", return_value=mock_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_momentum_scores()
            for stock_id, info in results.items():
                assert 0 <= info["score"] <= 100

    def test_calculate_volume_scores_with_specific_stocks(self, mock_loader):
        with patch("core.hot_stocks.get_loader", return_value=mock_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_volume_scores(stock_ids=["2330"])
            assert isinstance(results, dict)

    def test_calculate_momentum_scores_with_specific_stocks(self, mock_loader):
        with patch("core.hot_stocks.get_loader", return_value=mock_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_momentum_scores(stock_ids=["2330"])
            assert isinstance(results, dict)

    def test_volume_scores_loader_error(self):
        failing_loader = MagicMock()
        failing_loader.get.side_effect = Exception("載入失敗")
        with patch("core.hot_stocks.get_loader", return_value=failing_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_volume_scores()
            assert results == {}

    def test_momentum_scores_loader_error(self):
        failing_loader = MagicMock()
        failing_loader.get.side_effect = Exception("載入失敗")
        with patch("core.hot_stocks.get_loader", return_value=failing_loader):
            analyzer = HotStockAnalyzer()
            results = analyzer.calculate_momentum_scores()
            assert results == {}


# ──────────────────────────────────────────────
# hidden_gems
# ──────────────────────────────────────────────
from core.hidden_gems import (
    HiddenGemsScanner, _safe_last, _latest_row, _last_n_rows,
    MAX_PER_CATEGORY, WEIGHTS,
)


@pytest.fixture(scope="module")
def gems_dates():
    return pd.date_range("2021-01-01", periods=120, freq="B")


@pytest.fixture(scope="module")
def gems_stocks():
    return [f"{i:04d}" for i in range(2300, 2320)]  # 20 支股票


@pytest.fixture(scope="module")
def gems_close(gems_dates, gems_stocks):
    np.random.seed(5)
    prices = 50 * np.exp(np.cumsum(np.random.normal(0, 0.01, (120, len(gems_stocks))), axis=0))
    return pd.DataFrame(prices, index=gems_dates, columns=gems_stocks)


@pytest.fixture(scope="module")
def gems_volume(gems_dates, gems_stocks):
    np.random.seed(6)
    data = np.random.randint(500, 20000, (120, len(gems_stocks))).astype(float) * 1000
    return pd.DataFrame(data, index=gems_dates, columns=gems_stocks)


@pytest.fixture(scope="module")
def gems_pe(gems_dates, gems_stocks):
    np.random.seed(7)
    data = np.random.uniform(5, 25, (120, len(gems_stocks)))
    return pd.DataFrame(data, index=gems_dates, columns=gems_stocks)


@pytest.fixture(scope="module")
def gems_pb(gems_dates, gems_stocks):
    np.random.seed(8)
    data = np.random.uniform(0.3, 3.0, (120, len(gems_stocks)))
    return pd.DataFrame(data, index=gems_dates, columns=gems_stocks)


@pytest.fixture(scope="module")
def gems_yoy(gems_dates, gems_stocks):
    np.random.seed(9)
    data = np.random.uniform(-20, 60, (120, len(gems_stocks)))
    return pd.DataFrame(data, index=gems_dates, columns=gems_stocks)


@pytest.fixture(scope="module")
def gems_foreign(gems_dates, gems_stocks):
    np.random.seed(10)
    data = np.random.randint(-5000, 8000, (120, len(gems_stocks))).astype(float)
    return pd.DataFrame(data, index=gems_dates, columns=gems_stocks)


@pytest.fixture(scope="module")
def gems_market_value(gems_dates, gems_stocks):
    np.random.seed(11)
    data = np.random.uniform(1e9, 1e12, (120, len(gems_stocks)))
    return pd.DataFrame(data, index=gems_dates, columns=gems_stocks)


@pytest.fixture
def gems_loader(gems_close, gems_volume, gems_pe, gems_pb, gems_yoy,
                gems_foreign, gems_market_value, gems_stocks):
    loader = MagicMock()
    cats = pd.DataFrame({
        "stock_id": gems_stocks,
        "name": [f"股票{s}" for s in gems_stocks],
        "category": ["半導體"] * len(gems_stocks),
    })

    def get_side_effect(key, **kwargs):
        mapping = {
            "close": gems_close,
            "volume": gems_volume,
            "pe_ratio": gems_pe,
            "pb_ratio": gems_pb,
            "dividend_yield": gems_pb * 2,
            "revenue_yoy": gems_yoy,
            "revenue_mom": gems_yoy * 0.5,
            "foreign_investors": gems_foreign,
            "investment_trust": gems_foreign * 0.3,
            "market_value": gems_market_value,
            "adj_close": gems_close,
            "inventory_over_400_ratio": gems_pb * 10,
            "inventory_over_1000_ratio": gems_pb * 5,
            "categories": cats,
        }
        return mapping.get(key, pd.DataFrame())

    loader.get.side_effect = get_side_effect
    loader.get_stock_info.return_value = cats
    return loader


class TestHiddenGemsHelpers:
    def test_safe_last(self, gems_close):
        result = _safe_last(gems_close, "2300")
        assert isinstance(result, pd.Series)

    def test_latest_row_normal(self, gems_close):
        result = _latest_row(gems_close)
        assert isinstance(result, pd.Series)

    def test_latest_row_none(self):
        result = _latest_row(None)
        assert isinstance(result, pd.Series)
        assert len(result) == 0

    def test_latest_row_empty(self):
        result = _latest_row(pd.DataFrame())
        assert len(result) == 0

    def test_last_n_rows(self, gems_close):
        result = _last_n_rows(gems_close, 5)
        assert len(result) == 5

    def test_last_n_rows_none(self):
        result = _last_n_rows(None, 5)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestHiddenGemsScanner:
    def test_scan_returns_dict(self, gems_loader):
        scanner = HiddenGemsScanner()
        result = scanner.scan(gems_loader)
        assert isinstance(result, dict)

    def test_scan_has_top_level_keys(self, gems_loader):
        scanner = HiddenGemsScanner()
        result = scanner.scan(gems_loader)
        assert "categories" in result
        assert "composite_top20" in result
        assert "scan_date" in result

    def test_scan_categories_has_expected_keys(self, gems_loader):
        scanner = HiddenGemsScanner()
        result = scanner.scan(gems_loader)
        cats = result["categories"]
        for key in ["value_gems", "revenue_breakout", "stealth_buy",
                    "technical_reversal", "small_cap_growth", "ownership_shift"]:
            assert key in cats, f"缺少鍵：{key}"

    def test_scan_each_category_is_list(self, gems_loader):
        scanner = HiddenGemsScanner()
        result = scanner.scan(gems_loader)
        cats = result["categories"]
        for key in ["value_gems", "revenue_breakout", "stealth_buy"]:
            assert isinstance(cats[key], list)

    def test_scan_max_per_category(self, gems_loader):
        scanner = HiddenGemsScanner()
        result = scanner.scan(gems_loader)
        cats = result["categories"]
        for key in cats:
            assert len(cats[key]) <= MAX_PER_CATEGORY

    def test_scan_composite_top20(self, gems_loader):
        scanner = HiddenGemsScanner()
        result = scanner.scan(gems_loader)
        assert isinstance(result["composite_top20"], list)
        assert len(result["composite_top20"]) <= 20

    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6

    def test_scan_with_no_close_data(self):
        loader = MagicMock()
        loader.get.side_effect = Exception("無資料")
        scanner = HiddenGemsScanner()
        result = scanner.scan(loader)
        assert isinstance(result, dict)
        # 載入失敗時應回傳含有 error 或空結果的 dict，不應崩潰


# ──────────────────────────────────────────────
# report_generator
# ──────────────────────────────────────────────
from core.report_generator import PDFReportGenerator


@pytest.fixture(scope="module")
def rg_dates():
    return pd.date_range("2022-01-01", periods=252, freq="B")


@pytest.fixture(scope="module")
def rg_close(rg_dates):
    np.random.seed(0)
    prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, (252, 3)), axis=0))
    return pd.DataFrame(prices, index=rg_dates, columns=["2330", "2317", "2454"])


@pytest.fixture(scope="module")
def rg_pe(rg_dates):
    return pd.DataFrame(
        np.random.uniform(8, 20, (252, 3)),
        index=rg_dates, columns=["2330", "2317", "2454"]
    )


class TestPDFReportGenerator:

    def test_init(self):
        gen = PDFReportGenerator()
        assert isinstance(gen, PDFReportGenerator)

    def test_css_template_not_empty(self):
        gen = PDFReportGenerator()
        assert len(gen.CSS_TEMPLATE) > 0

    def test_format_number(self):
        gen = PDFReportGenerator()
        assert "億" in gen._format_number(2e8)
        assert "萬" in gen._format_number(2e4)
        assert gen._format_number(float("nan")) == "-"

    def test_format_percent(self):
        gen = PDFReportGenerator()
        assert "+" in gen._format_percent(5.0)
        assert "-" in gen._format_percent(-3.0)
        assert gen._format_percent(float("nan")) == "-"

    def test_get_value_class(self):
        gen = PDFReportGenerator()
        assert gen._get_value_class(1.0) == "positive"
        assert gen._get_value_class(-1.0) == "negative"
        assert gen._get_value_class(0.0) == ""

    def test_generate_stock_analysis_html(self, rg_dates, rg_close):
        gen = PDFReportGenerator()
        close_series = rg_close["2330"]
        volume_series = pd.Series(
            np.random.randint(1000, 50000, len(rg_dates)) * 1000,
            index=rg_dates
        )
        fundamental = {
            "pe": 15.0, "pb": 1.5, "dividend_yield": 4.0,
            "eps": 10.0, "revenue_yoy": 20.0,
        }
        technical = {"rsi": 55.0, "macd": 0.5, "ma20_diff": 2.0}
        html = gen.generate_stock_analysis_html(
            stock_id="2330", stock_name="台積電",
            category="半導體", market="上市",
            close=close_series, volume=volume_series,
            fundamental_data=fundamental, technical_data=technical
        )
        assert isinstance(html, str)
        assert "2330" in html or "台積電" in html

    def test_generate_screening_html(self, rg_close):
        gen = PDFReportGenerator()
        stock_info = pd.DataFrame({
            "stock_id": ["2330", "2317"],
            "name": ["台積電", "鴻海"],
            "category": ["半導體", "電子"],
        })
        scores = pd.Series({"2330": 85.0, "2317": 72.0})
        html = gen.generate_screening_html(
            strategy_name="價值投資",
            params={"pe_max": 20},
            stocks=["2330", "2317"],
            scores=scores,
            stock_info=stock_info,
            close=rg_close,
        )
        assert isinstance(html, str)

    def test_generate_portfolio_html(self, rg_dates, rg_close):
        gen = PDFReportGenerator()
        stock_info = pd.DataFrame({
            "stock_id": ["2330"],
            "name": ["台積電"],
            "category": ["半導體"],
        })
        holdings = [{"stock_id": "2330", "shares": 100,
                     "cost_price": 600.0, "cost": 60000.0}]
        html = gen.generate_portfolio_html(
            portfolio_name="我的組合",
            holdings=holdings,
            stock_info=stock_info,
            close=rg_close,
        )
        assert isinstance(html, str)
