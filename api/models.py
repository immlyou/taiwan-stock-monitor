"""API 請求/回應的 Pydantic 模型

集中管理所有 request body 的 schema 定義，避免散落在各 router。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── 自選股 ────────────────────────────────────────────
class WatchlistCreateRequest(BaseModel):
    name: str
    stocks: Optional[List[str]] = []


class WatchlistUpdateRequest(BaseModel):
    name: Optional[str] = None
    stocks: Optional[List[str]] = None


# ─── 交易日誌 ──────────────────────────────────────────
class JournalEntryRequest(BaseModel):
    stock_id: str
    action: str = Field(description="buy | sell | note")
    shares: Optional[int] = None
    price: Optional[float] = None
    note: Optional[str] = ""
    date: Optional[str] = None


# ─── 警報 ─────────────────────────────────────────────
class AlertCreateRequest(BaseModel):
    stock_id: str
    type: str = Field(
        description=(
            "price_above | price_below | rsi_above | rsi_below | "
            "volume_spike | ma_cross_up | ma_cross_down | new_high | new_low"
        )
    )
    value: float
    note: Optional[str] = ""


# ─── 投資組合 ──────────────────────────────────────────
class HoldingItem(BaseModel):
    stock_id: str
    shares: int = Field(ge=1)
    cost_price: float = Field(ge=0)
    buy_date: Optional[str] = None


class PortfolioCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class PortfolioUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    holdings: Optional[List[HoldingItem]] = None


# ─── 策略 / 回測 / 預測 ──────────────────────────────────
class BacktestRequest(BaseModel):
    strategy: str = Field(description="value | growth | momentum")
    preset: str = Field(default="standard", description="conservative | standard | aggressive")
    initial_capital: float = Field(default=1_000_000, ge=10_000)
    rebalance_freq: str = Field(default="ME", description="ME=月底, QE=季底")
    max_stocks: int = Field(default=10, ge=1, le=50)
    weight_method: str = Field(default="equal", description="equal | market_cap")
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PredictionRequest(BaseModel):
    stock_id: str
    horizon_days: int = Field(default=5, ge=1, le=60)
    method: str = Field(default="trend", description="trend | mean_reversion")


class StrategyCreateRequest(BaseModel):
    name: str
    strategy_type: str
    preset: str = "standard"
    description: Optional[str] = ""
    params: Optional[Dict[str, Any]] = None


# ─── 風險 ─────────────────────────────────────────────
class PortfolioRiskRequest(BaseModel):
    holdings: List[Dict[str, Any]] = Field(description="[{stock_id, weight}]")
    days: int = Field(default=252, ge=30, le=1260)


# ─── 設定 ─────────────────────────────────────────────
class SettingsUpdateRequest(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    default_days: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


# ─── AI ──────────────────────────────────────────────
class NewsSentimentRequest(BaseModel):
    news: List[Dict[str, str]] = Field(default=[], description="新聞列表 [{title, summary, link, source}]")


class JournalReviewRequest(BaseModel):
    entries: List[Dict[str, Any]] = Field(default=[], description="交易日誌條目列表")


class StockChatRequest(BaseModel):
    stock_id: str = Field(description="股票代號")
    question: str = Field(description="用戶問題")
    history: Optional[List[Dict[str, str]]] = Field(default=None, description="對話歷史")


class PostMarketSummaryRequest(BaseModel):
    market_data: Optional[Dict[str, Any]] = Field(default=None, description="市場數據，若為空則自動收集")
