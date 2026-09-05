"""XGBoost endpoint resilience contracts."""

from __future__ import annotations

import asyncio
import threading
import time

import pandas as pd

import api_server
from api.routers import strategy as strategy_router
from core.cache import get_cache


def test_concurrent_xgboost_requests_train_only_once(monkeypatch):
    """Concurrent cold misses for one key share the same model training run."""
    calls = 0
    calls_lock = threading.Lock()

    class FakePicker:
        def predict(self, _loader):
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.05)
            return [
                {
                    "stock_id": f"{index:04d}",
                    "predicted_return": 0.05 - index / 1000,
                    "confidence": 0.8,
                    "factors": {},
                    "__feature_importance__": {"ret20": 0.5},
                }
                for index in range(50)
            ]

    get_cache().clear()
    monkeypatch.setattr(strategy_router, "_get_stock_name_map", lambda: {"2330": "台積電"})
    monkeypatch.setattr(strategy_router, "_get_xgboost_picker", lambda: FakePicker())
    monkeypatch.setattr(
        strategy_router.loader,
        "get",
        lambda key: pd.DataFrame({"2330": [100.0]}) if key == "close" else None,
    )

    async def request_twice():
        return await asyncio.gather(
            strategy_router.strategy_ai_xgboost(top_n=10),
            strategy_router.strategy_ai_xgboost(top_n=37),
        )

    first, second = asyncio.run(request_twice())

    assert len(first["stocks"]) == 10
    assert len(second["stocks"]) == 37
    assert calls == 1


def test_warm_xgboost_force_refreshes_the_canonical_top_20(monkeypatch):
    calls = []

    async def fake_canonical(**kwargs):
        calls.append(kwargs)
        return {"stocks": []}

    monkeypatch.setattr(
        strategy_router, "_strategy_ai_xgboost_canonical", fake_canonical
    )

    strategy_router.warm_xgboost()

    assert calls == [{"_refresh_cache": True}]


def test_service_startup_prewarms_xgboost_in_background(monkeypatch):
    warmed = threading.Event()

    class WarmCache:
        def has(self, _key, max_age=0):
            return True

    monkeypatch.setattr("core.data_loader.DataCache", WarmCache)
    monkeypatch.setattr("core.stock_score.calculate_score_table", lambda _loader: None)
    monkeypatch.setattr(
        "core.intelligence.calculate_score_history",
        lambda _loader, _stock_id, days: None,
    )
    monkeypatch.setattr("api.routers.reports.warm_morning_report", lambda: None)
    monkeypatch.setattr("api.routers.radar.warm_radar", lambda: None)
    monkeypatch.setattr("api.routers.strategy.warm_xgboost", warmed.set)
    monkeypatch.setattr("core.scheduler.start_scheduler", lambda: None)
    monkeypatch.setattr("core.scheduler.shutdown_scheduler", lambda: None)

    async def start_service():
        async with api_server._lifespan(api_server.app):
            assert warmed.wait(timeout=2)

    asyncio.run(start_service())
