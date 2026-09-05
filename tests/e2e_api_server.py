"""Test-only real API server: isolated disk + deterministic market-data boundary.

Run through Playwright's contract config, never deploy this module. All routes,
authentication, request validation and persistence are the production versions.
Only external market data/notifications are replaced. Lifespan is disabled by
the runner so background warmups cannot contact external services.
"""
import atexit
import tempfile
from pathlib import Path

import pandas as pd

from api import helpers, state
from core import notification
from core.timeutils import today_taipei

_storage = tempfile.TemporaryDirectory(prefix="stock-contract-")
atexit.register(_storage.cleanup)
state.DATA_DIR = helpers.DATA_DIR = Path(_storage.name)
notification.NOTIFICATION_DATA_DIR = state.DATA_DIR

dates = pd.date_range(end=today_taipei(), periods=120, freq="D")
prices = pd.DataFrame({"2330": [100.] * 120}, index=dates)
categories = pd.DataFrame({"stock_id": ["2330"], "name": ["台積電"]})


def market_data(key):
    if key == "categories":
        return categories
    if key == "volume":
        return prices * 1000
    return prices


state.loader.get = market_data


def disabled_delivery(*args, **kwargs):
    raise RuntimeError("External notifications are disabled in contract tests")


notification.TelegramChannel.send = disabled_delivery
notification.EmailChannel.send = disabled_delivery
notification.LineNotifyChannel.send = disabled_delivery

# Import real routers after binding storage/data; no fake API payloads.
from fastapi import FastAPI
from api.response import SafeJSONResponse
from api.routers import alerts, dashboard, predictions, settings

app = FastAPI(default_response_class=SafeJSONResponse)
for router in (alerts.router, dashboard.router, predictions.router, settings.router):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "fixture": "contract"}
