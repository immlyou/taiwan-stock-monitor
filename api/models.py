"""API 請求/回應的 Pydantic 模型

集中管理所有 request body 的 schema 定義，避免散落在各 router。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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


class AlertUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    value: Optional[float] = None
    note: Optional[str] = None


class AlertRuleCondition(BaseModel):
    field: Literal["price", "change_pct", "rsi", "volume_ratio"]
    operator: Literal["gt", "gte", "lt", "lte", "eq"]
    value: float


class AlertRuleTarget(BaseModel):
    stockIds: List[str] = Field(default_factory=list)
    watchlistId: Optional[str] = None

    @model_validator(mode="after")
    def require_target(self):
        if not self.stockIds and not self.watchlistId:
            raise ValueError("target requires stockIds or watchlistId")
        return self


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    match: Literal["all", "any"] = "all"
    target: AlertRuleTarget
    conditions: List[AlertRuleCondition] = Field(min_length=1, max_length=10)
    frequency: Literal["once", "repeating"] = "repeating"
    cooldownMinutes: int = Field(default=60, ge=0, le=43200)
    channels: List[Literal["telegram", "email"]] = Field(default_factory=list)
    enabled: bool = True


class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    match: Optional[Literal["all", "any"]] = None
    target: Optional[AlertRuleTarget] = None
    conditions: Optional[List[AlertRuleCondition]] = Field(
        default=None, min_length=1, max_length=10
    )
    frequency: Optional[Literal["once", "repeating"]] = None
    cooldownMinutes: Optional[int] = Field(default=None, ge=0, le=43200)
    channels: Optional[List[Literal["telegram", "email"]]] = None
    enabled: Optional[bool] = None


class AlertEvaluateRequest(BaseModel):
    ruleIds: Optional[List[str]] = None
    sendNotifications: bool = False


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


class PortfolioWhatIfOperation(BaseModel):
    action: Literal["add", "update", "remove"]
    stock_id: str = Field(min_length=1)
    shares: Optional[int] = Field(default=None, ge=1)
    cost_price: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_add_values(self):
        if self.action == "add" and (self.shares is None or self.cost_price is None):
            raise ValueError("add requires shares and cost_price")
        return self


class PortfolioWhatIfRequest(BaseModel):
    operations: Optional[List[PortfolioWhatIfOperation]] = Field(
        default=None, min_length=1, max_length=100
    )
    holdings: Optional[List[HoldingItem]] = None

    @model_validator(mode="after")
    def require_one_scenario(self):
        if (self.operations is None) == (self.holdings is None):
            raise ValueError("provide exactly one of operations or holdings")
        return self


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
class TelegramSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    botToken: Optional[str] = None
    chatId: Optional[str] = None


class EmailSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    smtpHost: Optional[str] = None
    smtpPort: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    recipient: Optional[str] = None


class SystemSettingsUpdate(BaseModel):
    dataUpdateInterval: Optional[int] = Field(default=None, ge=5, le=86400)
    timezone: Optional[str] = None
    autoBacktest: Optional[bool] = None
    marketOpenTime: Optional[str] = None
    marketCloseTime: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    default_days: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None
    telegram: Optional[TelegramSettingsUpdate] = None
    email: Optional[EmailSettingsUpdate] = None
    system: Optional[SystemSettingsUpdate] = None


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
