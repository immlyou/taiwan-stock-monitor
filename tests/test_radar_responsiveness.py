"""Public responsiveness contract for CPU-heavy radar endpoints."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient


def test_health_remains_responsive_while_radar_work_is_running(monkeypatch):
    """A slow radar calculation must not block unrelated HTTP requests."""
    import api.deps
    from api_server import app
    from core.radar_pro import RadarPro

    monkeypatch.setattr(api.deps, "API_KEY", "")
    started = threading.Event()

    def slow_price_plan(self, stock_id):
        started.set()
        time.sleep(0.35)
        return {"stock_id": stock_id, "status": "ok"}

    monkeypatch.setattr(RadarPro, "price_plan", slow_price_plan)

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        radar_response = pool.submit(client.get, "/radar/price-plan/2330")
        assert started.wait(timeout=1)

        health_started = time.monotonic()
        health_response = client.get("/health")
        health_elapsed = time.monotonic() - health_started

        assert health_response.status_code == 200
        assert health_elapsed < 0.2
        assert radar_response.result(timeout=1).status_code == 200
