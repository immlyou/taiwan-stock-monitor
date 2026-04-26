"""Smoke test: assert all 24 router modules contribute at least one route."""
from api_server import app


def test_all_routers_registered():
    paths = {r.path for r in app.routes if hasattr(r, "path")}

    # (router_name, representative_path_that_must_exist)
    expected = [
        ("market",           "/market/summary"),
        ("stock",            "/stock/{stock_id}"),
        ("stock_profile",    "/stock/{stock_id}/profile"),
        ("stock_scorecard",  "/stock/{stock_id}/scorecard"),
        ("stock_score_history", "/stock/{stock_id}/score-history"),
        ("strategy",         "/strategy/{strategy_type}"),
        ("ai",               "/ai/stock-chat"),
        ("ai_stock_summary", "/ai/stock-summary/{stock_id}"),
        ("backtest",         "/backtest/run"),
        ("screener",         "/screener"),
        ("screener_scores",  "/screener/scores"),
        ("screener_score_upgrades", "/screener/score-upgrades"),
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
        ("alerts_types",      "/alerts/types"),
        ("alerts_smart_preview", "/alerts/smart-preview"),
        ("portfolios",       "/portfolios"),
        ("portfolio_diagnostics", "/portfolios/{portfolio_id}/diagnostics"),
        ("predictions",      "/predictions"),
        ("saved_strategies", "/strategies/saved"),
        ("settings",         "/settings"),
        ("dashboard_config",  "/dashboard/config"),
        ("news",             "/news/latest"),
        ("industry_rotation", "/market/industry-rotation"),
        ("social",           "/social/hot-stocks"),
        ("system",           "/health"),
    ]

    for router_name, path in expected:
        assert path in paths, (
            f"Router '{router_name}': expected path '{path}' not registered. "
            "Was this router removed or its routes renamed?"
        )
