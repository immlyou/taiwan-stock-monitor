"""Smoke test: assert all 24 router modules contribute at least one route."""
from api_server import app


def test_all_routers_registered():
    paths = {r.path for r in app.routes if hasattr(r, "path")}

    # (router_name, representative_path_that_must_exist)
    expected = [
        ("market",           "/market/summary"),
        ("stock",            "/stock/{stock_id}"),
        ("stock_scorecard",  "/stock/{stock_id}/scorecard"),
        ("strategy",         "/strategy/{strategy_type}"),
        ("ai",               "/ai/stock-chat"),
        ("backtest",         "/backtest/run"),
        ("screener",         "/screener"),
        ("screener_scores",  "/screener/scores"),
        ("optimizer",        "/optimizer/run"),
        ("reports",          "/morning-report"),
        ("compare",          "/stocks/compare"),
        ("after_hours",      "/market/after-hours"),
        ("risk",             "/risk/portfolio"),
        ("scanner",          "/scanner/hidden-gems"),
        ("quote",            "/quote/realtime/batch"),
        ("stocks",           "/stocks/list"),
        ("watchlists",       "/watchlists"),
        ("journal",          "/journal"),
        ("alerts",           "/alerts"),
        ("portfolios",       "/portfolios"),
        ("predictions",      "/predictions"),
        ("saved_strategies", "/strategies/saved"),
        ("settings",         "/settings"),
        ("news",             "/news/latest"),
        ("social",           "/social/hot-stocks"),
        ("system",           "/health"),
    ]

    for router_name, path in expected:
        assert path in paths, (
            f"Router '{router_name}': expected path '{path}' not registered. "
            "Was this router removed or its routes renamed?"
        )
