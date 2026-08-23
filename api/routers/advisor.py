"""投資顧問端點：/advisor/*

POST /advisor/analyze — 資深操盤人投資顧問：
  輸入 持股(或 portfolio_id) + 可投入資金/想拿回金額 + 目標報酬 + 風險偏好 →
  量化持股健檢 + 資金配置/再平衡建議 + 達標可行性 + Claude 專業敘述 +
  可一鍵套用的 proposed_holdings。
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_user_id, verify_api_key
from api.helpers import _get_stock_name_map
from api.state import loader
from core.advisor import analyze_portfolio, advisor_narrative, extract_holdings_from_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["顧問"], dependencies=[Depends(verify_api_key)])


class AdvisorHolding(BaseModel):
    stock_id: str
    shares: float = Field(ge=0)
    cost_price: float = Field(default=0, ge=0)


class ExtractHoldingsRequest(BaseModel):
    image_base64: str = Field(description="持股截圖的 base64（不含 data: 前綴）")
    media_type: str = Field(default="image/png", description="image/png | image/jpeg | image/webp")


class AdvisorRequest(BaseModel):
    portfolio_id: Optional[str] = Field(default=None, description="從既有投組載入持股（與 holdings 二擇一）")
    holdings: Optional[List[AdvisorHolding]] = Field(default=None, description="直接提供持股")
    capital_to_invest: float = Field(default=0, ge=0, description="想投入的新資金")
    withdraw_amount: float = Field(default=0, ge=0, description="想拿回的資金")
    target_roi: Optional[float] = Field(default=None, description="目標年化報酬率(%)")
    risk_tolerance: str = Field(default="moderate", description="conservative | moderate | aggressive")
    horizon_months: int = Field(default=12, ge=1, le=120, description="投資期限(月)")


_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_IMAGE_BYTES = 6_000_000  # 6MB（Claude Vision 單圖上限約 5MB，留緩衝）


@router.post("/advisor/extract-holdings")
async def advisor_extract_holdings(req: ExtractHoldingsRequest) -> Dict[str, Any]:
    """從持股截圖（base64）以 Claude Vision 擷取持股清單，供顧問分析使用。不碰 FinLab。"""
    # 輸入驗證：限制 MIME、解碼大小、拒絕非法 base64（避免把任意/超大內容送給 Vision）
    media_type = "image/jpeg" if req.media_type == "image/jpg" else req.media_type
    if media_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail=f"不支援的圖片類型: {req.media_type}（僅 png/jpeg/webp/gif）")
    try:
        decoded = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="image_base64 不是有效的 base64")
    if not decoded:
        raise HTTPException(status_code=422, detail="空圖片")
    if len(decoded) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"圖片過大（>{_MAX_IMAGE_BYTES // 1_000_000}MB），請壓縮後再上傳")

    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: extract_holdings_from_image(req.image_base64, media_type))
    if not res.get("holdings"):
        raise HTTPException(status_code=422, detail=f"擷取失敗: {res.get('error') or '未辨識出持股'}")
    return res


@router.post("/advisor/analyze")
async def advisor_analyze(
    req: AdvisorRequest, user_id: str = Depends(get_user_id)
) -> Dict[str, Any]:
    """資深操盤人投資顧問分析。"""
    # 取得持股
    holdings: List[Dict[str, Any]] = []
    if req.holdings:
        holdings = [h.dict() for h in req.holdings]
    elif req.portfolio_id:
        try:
            from app.components.portfolio_utils import load_portfolios
            ports = load_portfolios(user_id)
            if req.portfolio_id not in ports:
                raise HTTPException(status_code=404, detail=f"找不到投資組合: {req.portfolio_id}")
            holdings = ports[req.portfolio_id].get("holdings", [])
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"載入投組失敗: {e}")
    # 允許空持股（純新資金配置情境）

    name_map = _get_stock_name_map()
    loop = asyncio.get_event_loop()

    try:
        analysis = await loop.run_in_executor(None, lambda: analyze_portfolio(
            loader,
            holdings=holdings,
            name_map=name_map,
            capital_to_invest=req.capital_to_invest,
            withdraw_amount=req.withdraw_amount,
            target_roi=req.target_roi,
            risk_tolerance=req.risk_tolerance,
            horizon_months=req.horizon_months,
        ))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"顧問分析失敗: {e}")

    narr = await loop.run_in_executor(None, advisor_narrative, analysis)
    analysis["narrative"] = narr.get("narrative", "")
    analysis["narrative_error"] = narr.get("error")
    return analysis
