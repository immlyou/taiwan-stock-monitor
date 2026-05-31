"""投資組合 (Portfolios) 端點"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.deps import verify_api_key
from api.helpers import _get_stock_name_map
from api.models import PortfolioCreateRequest, PortfolioUpdateRequest
from api.state import loader
from core.intelligence import diagnose_portfolio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["投資組合"], dependencies=[Depends(verify_api_key)])


@router.get("/portfolios")
async def portfolios_list():
    """取得所有投資組合列表。"""
    try:
        from app.components.portfolio_utils import load_portfolios
        portfolios = load_portfolios()
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
async def portfolio_create(req: PortfolioCreateRequest):
    """建立新投資組合。"""
    try:
        from app.components.portfolio_utils import load_portfolios, save_portfolios
        portfolios = load_portfolios()
        if req.name in portfolios:
            raise HTTPException(status_code=409, detail=f"投資組合 '{req.name}' 已存在")
        portfolios[req.name] = {
            "description": req.description or "",
            "created_at": datetime.now().isoformat(),
            "holdings": [],
        }
        save_portfolios(portfolios)
        return {"message": "建立成功", "id": req.name, "name": req.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}")
async def portfolio_get(portfolio_id: str):
    """取得指定投資組合詳情，含各持股當前報酬率計算。"""
    try:
        from app.components.portfolio_utils import load_portfolios
        portfolios = load_portfolios()
        if portfolio_id not in portfolios:
            raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")

        data = portfolios[portfolio_id]
        holdings = data.get("holdings", [])
        close = loader.get("close")
        name_map = _get_stock_name_map()

        enriched_holdings = []
        total_cost = 0.0
        total_value = 0.0

        for h in holdings:
            sid = h.get("stock_id", "")
            shares = h.get("shares", 0)
            cost_price = h.get("cost_price", 0)
            cost = shares * cost_price

            current_price = cost_price
            try:
                if sid in close.columns:
                    current_price = float(close[sid].dropna().iloc[-1])
            except Exception:
                pass

            current_value = shares * current_price
            pnl = current_value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0

            total_cost += cost
            total_value += current_value

            enriched_holdings.append({
                **h,
                "name": name_map.get(sid, ""),
                "current_price": round(current_price, 2),
                "current_value": round(current_value, 2),
                "cost_value": round(cost, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
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
async def portfolio_diagnostics(portfolio_id: str):
    """投資組合診斷：集中度、產業配置、風險與調整建議。"""
    try:
        from app.components.portfolio_utils import load_portfolios
        portfolios = load_portfolios()
        if portfolio_id not in portfolios:
            raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
        return diagnose_portfolio(loader, portfolio_id, portfolios[portfolio_id])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/portfolios/{portfolio_id}")
async def portfolio_update(portfolio_id: str, req: PortfolioUpdateRequest):
    """更新投資組合（描述或持股清單）。"""
    try:
        from app.components.portfolio_utils import load_portfolios, save_portfolios
        portfolios = load_portfolios()
        if portfolio_id not in portfolios:
            raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")

        if req.description is not None:
            portfolios[portfolio_id]["description"] = req.description
        if req.holdings is not None:
            portfolios[portfolio_id]["holdings"] = [h.dict() for h in req.holdings]

        save_portfolios(portfolios)
        return {"message": "更新成功", "id": portfolio_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/portfolios/{portfolio_id}")
async def portfolio_delete(portfolio_id: str):
    """刪除投資組合。"""
    try:
        from app.components.portfolio_utils import load_portfolios, save_portfolios
        portfolios = load_portfolios()
        if portfolio_id not in portfolios:
            raise HTTPException(status_code=404, detail=f"找不到投資組合: {portfolio_id}")
        del portfolios[portfolio_id]
        save_portfolios(portfolios)
        return {"message": "刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
