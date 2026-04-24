"""風險端點：/risk/stock/{id}, /risk/portfolio"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import verify_api_key
from api.helpers import _safe_json
from api.models import PortfolioRiskRequest
from api.state import loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["風險"], dependencies=[Depends(verify_api_key)])


@router.get("/risk/stock/{stock_id}")
async def risk_stock(
    stock_id: str,
    days: int = Query(default=252, ge=60, le=1260, description="計算用歷史天數"),
):
    """個股風險指標 - VaR、CVaR、波動率、最大回撤、Beta。"""
    try:
        from core.risk import RiskAnalyzer
        close = loader.get("close")
        if stock_id not in close.columns:
            raise HTTPException(status_code=404, detail=f"找不到股票: {stock_id}")

        series = close[stock_id].dropna().tail(days)
        benchmark = loader.get_benchmark().reindex(series.index).dropna()

        analyzer = RiskAnalyzer()
        metrics = analyzer.analyze(series, benchmark_prices=benchmark if len(benchmark) > 10 else None)

        return {
            "stock_id": stock_id,
            "days": len(series),
            "date_range": {
                "start": series.index[0].strftime("%Y-%m-%d"),
                "end": series.index[-1].strftime("%Y-%m-%d"),
            },
            "risk_metrics": {
                "var_95": _safe_json(metrics.var_95),
                "var_99": _safe_json(metrics.var_99),
                "cvar_95": _safe_json(metrics.cvar_95),
                "cvar_99": _safe_json(metrics.cvar_99),
                "volatility": _safe_json(metrics.volatility),
                "downside_volatility": _safe_json(metrics.downside_volatility),
                "max_drawdown": _safe_json(metrics.max_drawdown),
                "beta": _safe_json(metrics.beta),
                "tracking_error": _safe_json(metrics.tracking_error),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk/portfolio")
async def risk_portfolio(req: PortfolioRiskRequest):
    """投資組合風險分析 - 計算加權 VaR 及組合波動率。"""
    try:
        from core.risk import RiskAnalyzer, calculate_portfolio_var

        if not req.holdings:
            raise HTTPException(status_code=400, detail="請提供至少一個持股")

        close = loader.get("close")

        total_weight = sum(h.get("weight", 1) for h in req.holdings)
        weights = {
            h["stock_id"]: h.get("weight", 1) / total_weight
            for h in req.holdings
            if h.get("stock_id") in close.columns
        }

        if not weights:
            raise HTTPException(status_code=400, detail="所有股票代號均找不到")

        valid_ids = list(weights.keys())
        returns_df = close[valid_ids].tail(req.days).pct_change().dropna()

        portfolio_var_95 = calculate_portfolio_var(weights, returns_df, 0.95) * 100
        portfolio_var_99 = calculate_portfolio_var(weights, returns_df, 0.99) * 100

        analyzer = RiskAnalyzer()
        weighted_vol = sum(
            weights[sid] * analyzer.calculate_volatility(returns_df[sid].dropna())
            for sid in valid_ids if sid in returns_df.columns
        )

        weighted_returns = sum(
            returns_df[sid] * weights[sid] for sid in valid_ids if sid in returns_df.columns
        )

        portfolio_prices = (1 + weighted_returns).cumprod()
        max_dd, peak_date, trough_date = analyzer.calculate_max_drawdown(portfolio_prices)

        stock_risks = []
        for sid in valid_ids:
            if sid not in returns_df.columns:
                continue
            m = analyzer.analyze(close[sid].dropna().tail(req.days))
            stock_risks.append({
                "stock_id": sid,
                "weight": round(weights[sid], 4),
                "volatility": _safe_json(m.volatility),
                "var_95": _safe_json(m.var_95),
                "max_drawdown": _safe_json(m.max_drawdown),
            })

        return {
            "days": req.days,
            "holdings": len(weights),
            "portfolio_risk": {
                "var_95": round(float(portfolio_var_95), 4) if portfolio_var_95 is not None else None,
                "var_99": round(float(portfolio_var_99), 4) if portfolio_var_99 is not None else None,
                "weighted_volatility": round(weighted_vol * 100, 4) if weighted_vol is not None else None,
                "max_drawdown": round(float(max_dd) * 100, 4) if max_dd is not None else None,
                "peak_date": peak_date.strftime("%Y-%m-%d") if peak_date else None,
                "trough_date": trough_date.strftime("%Y-%m-%d") if trough_date else None,
            },
            "stock_risks": stock_risks,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
