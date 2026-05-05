from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Auth ─────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── API Keys ──────────────────────────────────────
class ApiKeyCreate(BaseModel):
    broker_name: str
    environment: str
    api_key: str
    secret_key: str


class ApiKeyResponse(BaseModel):
    id: str
    broker_name: str
    environment: str
    is_active: bool = True
    created_at: Optional[datetime] = None


# ── Broker ───────────────────────────────────────
class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str  # "buy" | "sell"
    time_in_force: str = "day"


class OrderResponse(BaseModel):
    id: str
    symbol: str
    qty: str
    side: str
    status: str
    submitted_at: Optional[str] = None


class PositionResponse(BaseModel):
    symbol: str
    qty: str
    side: str
    avg_entry_price: str
    current_price: str
    unrealized_pl: str
    unrealized_plpc: str


class AccountResponse(BaseModel):
    id: str
    equity: str
    cash: str
    buying_power: str
    portfolio_value: str
    currency: str
    status: str


# ── Strategy ─────────────────────────────────────
class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str  # e.g. "mean_reversion", "momentum"
    parameters: Optional[dict] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    parameters: Optional[dict] = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    type: str
    parameters: Optional[dict] = None
    is_active: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Bot ──────────────────────────────────────────
class BotStatusResponse(BaseModel):
    is_running: bool
    strategy: Optional[str] = None
    started_at: Optional[datetime] = None
    uptime_seconds: Optional[float] = None


# ── Metrics ──────────────────────────────────────
class PnLResponse(BaseModel):
    total_pnl: float
    daily_pnl: float
    unrealized_pnl: float
    realized_pnl: float


class PerformanceResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    sharpe_ratio: Optional[float] = None


# ── Dashboard ───────────────────────────────────
class DashboardBotSummary(BaseModel):
    id: str
    name: str
    status: str
    environment: str
    last_run_at: Optional[datetime] = None


class DashboardAccountSummary(BaseModel):
    equity: float
    cash: float
    buying_power: float
    currency: str = "USD"


class DashboardPerformance(BaseModel):
    daily_pnl: float
    total_pnl: float
    open_positions: int
    orders_today: int


class DashboardPosition(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    current_price: float
    unrealized_pnl: float


class DashboardOrder(BaseModel):
    symbol: str
    side: str
    qty: float
    status: str
    submitted_at: Optional[datetime] = None


class DashboardLog(BaseModel):
    level: str
    message: str
    created_at: Optional[datetime] = None


class DashboardSummaryResponse(BaseModel):
    bot: DashboardBotSummary
    account: DashboardAccountSummary
    performance: DashboardPerformance
    positions: list[DashboardPosition]
    recent_orders: list[DashboardOrder]
    recent_logs: list[DashboardLog]
