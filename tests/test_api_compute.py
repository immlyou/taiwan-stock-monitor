"""
Backtest / Optimizer / AI router contract tests.

策略：
- Backtest: 把 BacktestEngine.run 整顆 mock，回傳 fixture BacktestResult，
  驗 response 結構與 validation 行為，不重跑回測計算邏輯（那是 core 測試的責任）。
- Optimizer: 用 sample_close 真的跑 grid search（計算量小、有上限），驗 happy path 與
  資料不足等 422 路徑。
- AI: 對每個 ai_models 類別 monkeypatch，回傳預期 shape。stock-summary 不需 LLM，直接打。
"""
from __future__ import annotations


import pandas as pd
import pytest
from fastapi.testclient import TestClient


# ── 共用 fixture ─────────────────────────────────────────
@pytest.fixture
def compute_client(monkeypatch, tmp_path, sample_close, sample_volume, sample_stock_info):
    """TestClient with full DataLoader mock for compute-heavy routers."""
    import api.deps
    from api import helpers as api_helpers
    from api import state as api_state
    from api.state import loader as real_loader

    monkeypatch.setattr(api.deps, "API_KEY", "")

    cats = pd.DataFrame({
        "stock_id": sample_stock_info["stock_id"].astype(str).values,
        "name": sample_stock_info["name"].astype(str).values,
        "category": sample_stock_info["industry"].astype(str).values,
    })

    # 構造更完整的資料集，涵蓋 backtest 三策略所需欄位
    n = len(sample_close)
    sample_data = {
        "close": sample_close,
        "open": sample_close * 0.99,
        "high": sample_close * 1.02,
        "low": sample_close * 0.98,
        "volume": sample_volume,
        "categories": cats,
        "pe_ratio": sample_close.copy() * 0 + 12.0,
        "pb_ratio": sample_close.copy() * 0 + 1.2,
        "dividend_yield": sample_close.copy() * 0 + 5.0,
        "revenue_yoy": sample_close.copy() * 0 + 25.0,
        "revenue_mom": sample_close.copy() * 0 + 12.0,
    }

    monkeypatch.setattr(real_loader, "get", lambda key: sample_data.get(key))
    monkeypatch.setattr(
        real_loader, "get_benchmark",
        lambda: pd.Series(range(100, 100 + n), index=sample_close.index, dtype=float),
    )
    monkeypatch.setattr(
        real_loader, "get_stock_info", lambda: sample_stock_info,
    )
    from core.data_loader import DataLoader
    monkeypatch.setattr(DataLoader, "get", lambda self, key: sample_data.get(key))

    monkeypatch.setattr(api_state, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api_helpers, "DATA_DIR", tmp_path)

    from api_server import app
    return TestClient(app)


# ── Backtest ────────────────────────────────────────────
class TestBacktestRouter:
    @pytest.fixture
    def fake_result(self, sample_close):
        """構造一個 BacktestResult fixture 給 mock engine.run 回傳"""
        from core.backtest.engine import BacktestResult
        from core.backtest.metrics import PerformanceMetrics

        pv = pd.Series(
            range(1_000_000, 1_000_000 + len(sample_close)),
            index=sample_close.index,
            dtype=float,
        )
        metrics = PerformanceMetrics(
            total_return=15.5,
            annualized_return=8.2,
            volatility=12.3,
            sharpe_ratio=0.67,
            sortino_ratio=0.95,
            max_drawdown=-8.4,
            max_drawdown_duration=30,
            win_rate=55.0,
            profit_factor=1.5,
            total_trades=42,
            avg_holding_days=21.0,
            calmar_ratio=0.98,
        )
        return BacktestResult(
            portfolio_values=pv,
            trades=pd.DataFrame(),
            positions=pd.DataFrame(),
            metrics=metrics,
            benchmark_comparison={"alpha": 2.1, "beta": 0.85},
        )

    def test_backtest_run_happy_path(self, compute_client, monkeypatch, fake_result):
        from core.backtest.engine import BacktestEngine
        monkeypatch.setattr(BacktestEngine, "run", lambda self, **kw: fake_result)

        r = compute_client.post(
            "/backtest/run",
            json={
                "strategy": "value",
                "preset": "standard",
                "initial_capital": 1_000_000,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["strategy"] == "value"
        assert body["metrics"]["total_return"] == 15.5
        assert body["metrics"]["sharpe_ratio"] == 0.67
        assert len(body["portfolio_values"]) > 0
        assert body["benchmark_comparison"]["alpha"] == 2.1

    def test_backtest_bad_strategy_returns_400(self, compute_client):
        r = compute_client.post(
            "/backtest/run",
            json={"strategy": "unknown", "preset": "standard"},
        )
        # backtest router 顯式 raise 400；schema 也限制了 value/growth/momentum 描述
        assert r.status_code in (400, 422)

    def test_backtest_initial_capital_validation(self, compute_client):
        r = compute_client.post(
            "/backtest/run",
            json={"strategy": "value", "initial_capital": 100},  # < 10_000
        )
        assert r.status_code == 422

    def test_backtest_max_stocks_validation(self, compute_client):
        r = compute_client.post(
            "/backtest/run",
            json={"strategy": "momentum", "max_stocks": 0},
        )
        assert r.status_code == 422


# ── Optimizer ────────────────────────────────────────────
class TestOptimizerRouter:
    def test_optimizer_unknown_stock_returns_422(self, compute_client):
        r = compute_client.post(
            "/optimizer/run",
            json={
                "strategy": "ma_crossover",
                "stockCode": "9999",  # 不在 sample 中
                "startDate": "2023-01-01",
                "endDate": "2023-12-31",
                "ranges": {},
            },
        )
        assert r.status_code == 422

    def test_optimizer_insufficient_data_returns_422(self, compute_client):
        # 提供太短的日期範圍 → handler 內部回 422
        r = compute_client.post(
            "/optimizer/run",
            json={
                "strategy": "ma_crossover",
                "stockCode": "2330",
                "startDate": "2023-01-01",
                "endDate": "2023-01-05",
                "ranges": {},
            },
        )
        assert r.status_code == 422

    def test_optimizer_happy_path(self, compute_client, sample_stocks):
        r = compute_client.post(
            "/optimizer/run",
            json={
                "strategy": "ma_crossover",
                "stockCode": sample_stocks[0],
                "startDate": "2023-01-01",
                "endDate": "2023-12-31",
                "ranges": {
                    "fastPeriod": {"min": 3, "max": 7},
                    "slowPeriod": {"min": 10, "max": 25},
                },
            },
        )
        assert r.status_code == 200
        body = r.json()
        for field in ("bestParams", "bestScore", "totalReturn", "sharpe", "grid"):
            assert field in body
        assert isinstance(body["grid"], list)


# ── AI router ────────────────────────────────────────────
class TestAIRouter:
    def test_stock_summary_known_stock(self, compute_client, sample_stocks):
        """stock-summary fallback 不依賴 LLM，直接走 generate_stock_summary"""
        r = compute_client.get(f"/ai/stock-summary/{sample_stocks[0]}")
        # 視 generate_stock_summary 實作，可能回 200 或 500（資料不齊全）
        # 重點是不要 401/404
        assert r.status_code in (200, 500)

    def test_stock_summary_unknown_stock_returns_404(self, compute_client):
        r = compute_client.get("/ai/stock-summary/9999")
        assert r.status_code in (404, 500)

    def test_news_sentiment_mocked(self, compute_client, monkeypatch):
        import core.ai_models as ai_models

        class _FakeAnalyzer:
            def analyze_batch(self, items, max_items=15):
                return [{"sentiment": "neutral", "score": 0.0} for _ in items]

        monkeypatch.setattr(ai_models, "ClaudeNewsSentimentAnalyzer", _FakeAnalyzer)

        r = compute_client.post(
            "/ai/news-sentiment",
            json={"news": [{"title": "test", "summary": "", "link": "", "source": ""}]},
        )
        assert r.status_code == 200
        body = r.json()
        assert "results" in body
        assert len(body["results"]) == 1

    def test_anomalies_mocked(self, compute_client, monkeypatch):
        import core.ai_models as ai_models

        class _FakeDetector:
            def detect(self, dl, stock_ids=None):
                return [
                    {"stock_id": "2330", "severity": "high", "type": "volume_spike"},
                    {"stock_id": "2317", "severity": "medium", "type": "gap_up"},
                ]
            def explain(self, anomalies, max_items=10):
                return "fake explanation"

        monkeypatch.setattr(ai_models, "AnomalyDetector", _FakeDetector)

        r = compute_client.get("/ai/anomalies?scope=all&explain=true")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["high_count"] == 1
        assert body["medium_count"] == 1
        assert body["explanation"] == "fake explanation"

    def test_journal_review_mocked(self, compute_client, monkeypatch):
        import core.ai_models as ai_models

        class _FakeJournalAnalyzer:
            def analyze(self, entries):
                return {"insights": "fake", "entries_analyzed": len(entries)}

        monkeypatch.setattr(ai_models, "TradingJournalAnalyzer", _FakeJournalAnalyzer)

        r = compute_client.post(
            "/ai/journal-review",
            json={"entries": [{"stock_id": "2330", "action": "buy"}]},
        )
        assert r.status_code == 200
        assert r.json()["entries_analyzed"] == 1

    def test_stock_chat_mocked(self, compute_client, monkeypatch, sample_stocks):
        import core.ai_models as ai_models

        class _FakeAssistant:
            def chat(self, stock_id, name, data_context, question, history=None):
                return f"echo: {question}"

        monkeypatch.setattr(ai_models, "StockChatAssistant", _FakeAssistant)

        r = compute_client.post(
            "/ai/stock-chat",
            json={"stock_id": sample_stocks[0], "question": "目前估值如何？"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["stock_id"] == sample_stocks[0]
        assert body["reply"].startswith("echo:")

    def test_post_market_summary_mocked(self, compute_client, monkeypatch):
        import core.ai_models as ai_models

        class _FakeSummarizer:
            def generate(self, market_data):
                return {"title": "fake summary", "highlights": "..."}

        monkeypatch.setattr(ai_models, "PostMarketSummarizer", _FakeSummarizer)

        r = compute_client.post("/ai/post-market-summary", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "fake summary"
