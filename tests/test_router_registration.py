"""Smoke test: assert all 47 router modules contribute at least one route."""
from api_server import app


def test_all_routers_registered():
    # 用 OpenAPI schema 列舉已註冊路由：版本無關。
    # （較新版 FastAPI 的 include_router 會以 _IncludedRouter 掛載物件呈現，
    #  沒有 .path 屬性，直接讀 app.routes 會漏掉 included 路由。）
    paths = set(app.openapi().get("paths", {}).keys())

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
        ("radar_stocks",     "/radar/stocks"),
        ("radar_stock",      "/radar/stock/{stock_id}"),
        ("radar_backtest",   "/radar/backtest"),
        ("radar_tracking",   "/radar/tracking"),
        ("radar_portfolio_health", "/radar/portfolio-health/{portfolio_id}"),
        ("radar_peers",      "/radar/peers/{stock_id}"),
        ("radar_daily_report", "/radar/daily-report"),
        ("radar_notifications", "/radar/notifications/preview"),
        ("radar_events",     "/radar/events/{stock_id}"),
        ("radar_price_plan", "/radar/price-plan/{stock_id}"),
        ("radar_news_revenue", "/radar/news-revenue/{stock_id}"),
        ("radar_broker_chip", "/radar/broker-chip/{stock_id}"),
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
