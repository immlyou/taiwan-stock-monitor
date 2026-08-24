"""投資組合 (Portfolios) 端點"""
from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from api.deps import get_user_id, verify_api_key
from api.helpers import _get_stock_name_map
from api.models import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    PortfolioWhatIfRequest,
)
from api.state import loader, quote_service
from core.intelligence import diagnose_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["投資組合"], dependencies=[Depends(verify_api_key)])


@router.get("/portfolios")
async def portfolios_list(user_id: str = Depends(get_user_id)):
    """取得所有投資組合列表。"""
    try:
        from app.components.portfolio_utils import load_portfolios
        portfolios = load_portfolios(user_id)
        result = []
        for name, data in portfolios.items():
            result.append({
                "id": name,
                "name": name,
                "description": data.get("description", ""),
                "created_at": data.get("created_at", ""),
                "holdings_count": len(data.get("holdings", [])),
            })
        return {"total": len(result), "portfolios": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolios")
async def portfolio_create(
    req: PortfolioCreateRequest, user_id: str = Depends(get_user_id)
):
    """建立新投資組合。"""
    try:
        from app.components.portfolio_utils import (
            load_portfolios, portfolio_file, save_portfolios,
        )
        from core.json_store import file_lock
        with file_lock(portfolio_file(user_id)):
            portfolios = load_portfolios(user_id)
            if req.name in portfolios:
                raise HTTPException(status_code=409, detail=f"投資組合 '{req.name}' 已存在")
            portfolios[req.name] = {
                "description": req.description or "",
                "created_at": datetime.now().isoformat(),
                "holdings": [],
            }
            save_portfolios(portfolios, user_id)
        return {"message": "建立成功", "id": req.name, "name": req.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}")
async def portfolio_get(
    portfolio_id: str, user_id: str = Depends(get_user_id)
):
    """取得指定投資組合詳情，含各持股當前報酬率計算。"""
    try:
        from app.components.portfolio_utils import load_portfolios, plausible_pnl_pct
        from api.helpers import resolve_default_id
        portfolios = load_portfolios(user_id)
        resolved, empty_default = resolve_default_id(portfolios, portfolio_id)
        if empty_default:
            # 完全沒有投資組合時回空結構（200），讓前端顯示空狀態而非吃 404。
            return {
                "id": "default", "name": "default", "description": "",
                "created_at": "", "holdings": [],
                "summary": {"total_cost": 0.0, "total_value": 0.0,
                            "total_pnl": 0.0, "total_pnl_pct": 0.0},
            }
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
        portfolio_id = resolved

        data = portfolios[portfolio_id]
        holdings = data.get("holdings", [])
        try:
            close = loader.get("close")
        except Exception as exc:
            # Live providers can still price holdings when FinLab is unavailable.
            logger.warning("Portfolio close history unavailable: %s", exc)
            close = None
        name_map = _get_stock_name_map()

        stock_ids = [str(h.get("stock_id", "")).strip().upper() for h in holdings]
        try:
            live_quotes = await run_in_threadpool(quote_service.get_quotes, stock_ids)
        except Exception as exc:
            logger.warning("Portfolio quote enrichment failed: %s", exc)
            live_quotes = []
        quotes_by_id = {item["stock_id"]: item for item in live_quotes}

        enriched_holdings = []
        total_cost = 0.0
        total_value = 0.0

        for h in holdings:
            sid = str(h.get("stock_id", "")).strip().upper()
            shares = h.get("shares", 0)
            cost_price = h.get("cost_price", 0)
            cost = shares * cost_price

            current_price = cost_price
            price_history: list[float] = []
            quote = quotes_by_id.get(sid)
            has_daily_price = False
            try:
                if close is not None and sid in close.columns:
                    recent = close[sid].dropna()
                    if not recent.empty:
                        current_price = float(recent.iloc[-1])
                        has_daily_price = True
                        # 近 30 個交易日收盤價，供前端繪製持股迷你走勢 (sparkline)
                        price_history = [round(float(p), 2) for p in recent.tail(30).tolist()]
            except Exception:
                pass
            if quote and quote.get("price") is not None:
                current_price = float(quote["price"])

            current_value = shares * current_price
            # 成本價明顯異常（資料輸入錯誤）時不計損益，回 None 而非荒謬百分比，
            # 且不納入整體彙總，避免單筆壞資料毒化 total_pnl。
            safe_pnl_pct = plausible_pnl_pct(current_price, cost_price)
            if safe_pnl_pct is None:
                pnl = None
                pnl_pct = None
            else:
                pnl = round(current_value - cost, 2)
                pnl_pct = safe_pnl_pct
                total_cost += cost
                total_value += current_value

            enriched_holdings.append({
                **h,
                "name": (quote.get("name") if quote else "") or name_map.get(sid, ""),
                "current_price": round(current_price, 2),
                "current_value": round(current_value, 2),
                "cost_value": round(cost, 2),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "price_history": price_history,
                "source": quote.get("source") if quote else ("finlab" if has_daily_price else "unavailable"),
                "is_realtime": bool(quote.get("is_realtime")) if quote else False,
                "freshness": quote.get("freshness", "close") if quote else ("close" if has_daily_price else "unavailable"),
                "market_state": quote.get("market_state", "closed") if quote else "closed",
                "timestamp": quote.get("timestamp") if quote else None,
                "quote_date": quote.get("date") if quote else None,
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        return {
            "id": portfolio_id,
            "name": portfolio_id,
            "description": data.get("description", ""),
            "created_at": data.get("created_at", ""),
            "holdings": enriched_holdings,
            "summary": {
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}/diagnostics")
async def portfolio_diagnostics(
    portfolio_id: str, user_id: str = Depends(get_user_id)
):
    """投資組合診斷：集中度、產業配置、風險與調整建議。"""
    try:
        from app.components.portfolio_utils import load_portfolios
        from api.helpers import resolve_default_id
        portfolios = load_portfolios(user_id)
        resolved, empty_default = resolve_default_id(portfolios, portfolio_id)
        if empty_default:
            # 沒有任何投資組合 -> 用空組合走診斷（安全降級，不回 404）。
            return diagnose_portfolio(loader, "default", {"holdings": []})
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
        return diagnose_portfolio(loader, resolved, portfolios[resolved])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolios/{portfolio_id}/what-if")
async def portfolio_what_if(
    portfolio_id: str,
    req: PortfolioWhatIfRequest,
    user_id: str = Depends(get_user_id),
):
    """Evaluate a hypothetical portfolio without changing persisted holdings."""
    from app.components.portfolio_utils import load_portfolios
    from api.helpers import resolve_default_id

    portfolios = load_portfolios(user_id)
    resolved, empty_default = resolve_default_id(portfolios, portfolio_id)
    if empty_default or resolved is None:
        raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")

    baseline_portfolio = deepcopy(portfolios[resolved])
    scenario_holdings = deepcopy(baseline_portfolio.get("holdings", []))
    if req.holdings is not None:
        scenario_holdings = [item.model_dump() for item in req.holdings]
    else:
        for operation in req.operations or []:
            stock_id = operation.stock_id.strip().upper()
            index = next(
                (
                    idx for idx, holding in enumerate(scenario_holdings)
                    if str(holding.get("stock_id", "")).upper() == stock_id
                ),
                None,
            )
            if operation.action == "add":
                if index is not None:
                    raise HTTPException(
                        status_code=422, detail=f"持股已存在，請改用 update: {stock_id}"
                    )
                scenario_holdings.append(
                    {
                        "stock_id": stock_id,
                        "shares": operation.shares,
                        "cost_price": operation.cost_price,
                    }
                )
            elif operation.action == "update":
                if index is None:
                    raise HTTPException(
                        status_code=422, detail=f"找不到要更新的持股: {stock_id}"
                    )
                if operation.shares is not None:
                    scenario_holdings[index]["shares"] = operation.shares
                if operation.cost_price is not None:
                    scenario_holdings[index]["cost_price"] = operation.cost_price
            else:
                if index is None:
                    raise HTTPException(
                        status_code=422, detail=f"找不到要移除的持股: {stock_id}"
                    )
                scenario_holdings.pop(index)

    scenario_portfolio = {
        **deepcopy(baseline_portfolio),
        "holdings": scenario_holdings,
    }
    baseline = diagnose_portfolio(loader, resolved, baseline_portfolio)
    scenario = diagnose_portfolio(loader, resolved, scenario_portfolio)
    delta = {
        "holdings_count": scenario["holdings_count"] - baseline["holdings_count"],
        "total_value": round(scenario["total_value"] - baseline["total_value"], 2),
        "top_holding_weight": round(
            scenario["concentration"]["top_holding_weight"]
            - baseline["concentration"]["top_holding_weight"],
            2,
        ),
        "annualized_volatility_pct": round(
            scenario["risk"]["annualized_volatility_pct"]
            - baseline["risk"]["annualized_volatility_pct"],
            2,
        ),
        "max_drawdown_pct": round(
            scenario["risk"]["max_drawdown_pct"]
            - baseline["risk"]["max_drawdown_pct"],
            2,
        ),
    }
    return {
        "portfolioId": resolved,
        "persisted": False,
        "baseline": baseline,
        "scenario": scenario,
        "delta": delta,
        "scenarioHoldings": scenario_holdings,
    }


@router.put("/portfolios/{portfolio_id}")
async def portfolio_update(
    portfolio_id: str,
    req: PortfolioUpdateRequest,
    user_id: str = Depends(get_user_id),
):
    """更新投資組合（描述或持股清單）。"""
    try:
        from app.components.portfolio_utils import (
            load_portfolios, portfolio_file, save_portfolios,
        )
        from api.helpers import resolve_default_id
        from core.json_store import file_lock
        with file_lock(portfolio_file(user_id)):
            portfolios = load_portfolios(user_id)
            resolved, empty_default = resolve_default_id(portfolios, portfolio_id)
            if empty_default:
                resolved = "default"
                portfolios[resolved] = {
                    "description": "預設組合",
                    "created_at": datetime.now().isoformat(),
                    "holdings": [],
                }
            elif resolved is None:
                raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
            portfolio_id = resolved

            if req.description is not None:
                portfolios[portfolio_id]["description"] = req.description
            if req.holdings is not None:
                portfolios[portfolio_id]["holdings"] = [h.model_dump() for h in req.holdings]

            save_portfolios(portfolios, user_id)
        return {"message": "更新成功", "id": portfolio_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/portfolios/{portfolio_id}")
async def portfolio_delete(
    portfolio_id: str, user_id: str = Depends(get_user_id)
):
    """刪除投資組合。"""
    try:
        from app.components.portfolio_utils import (
            load_portfolios, portfolio_file, save_portfolios,
        )
        from core.json_store import file_lock
        with file_lock(portfolio_file(user_id)):
            portfolios = load_portfolios(user_id)
            if portfolio_id not in portfolios:
                raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
            del portfolios[portfolio_id]
            save_portfolios(portfolios, user_id)
        return {"message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
