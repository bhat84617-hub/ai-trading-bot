from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
import uuid

class TradeMode(str, Enum):
    PAPER = "paper"
    APPROVAL = "approval"
    LIVE = "live"

class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"

class TradeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    trade_mode: TradeMode
    max_risk_per_trade: float
    max_daily_loss: float
    max_drawdown: float
    max_open_positions: int
    min_confidence_score: float
    min_risk_reward: float
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserSettingsUpdate(BaseModel):
    trade_mode: Optional[TradeMode] = None
    max_risk_per_trade: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_open_positions: Optional[int] = None
    min_confidence_score: Optional[float] = None
    min_risk_reward: Optional[float] = None
    telegram_chat_id: Optional[str] = None

class WatchlistCreate(BaseModel):
    symbol: str
    timeframe: str = "1h"

class WatchlistResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    timeframe: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SignalResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    direction: SignalDirection
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence_score: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    risk_percentage: Optional[float] = None
    reason: Optional[str] = None
    trade_explanation: Optional[str] = None
    news_sentiment: Optional[str] = None
    status: TradeStatus
    timeframe: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TradeResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    direction: SignalDirection
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: Optional[float] = None
    status: TradeStatus
    pnl: Optional[float] = None
    pnl_percentage: Optional[float] = None
    risk_percentage: Optional[float] = None
    confidence_score: Optional[float] = None
    trade_mode: Optional[TradeMode] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TradeApproval(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")

class AIAnalysisRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"

class AIAnalysisResponse(BaseModel):
    symbol: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    risk_reward_ratio: float
    risk_percentage: float
    reason: str
    trade_explanation: str
    news_sentiment: str
    market_context: str
    indicators_data: dict

class MarketScanResponse(BaseModel):
    signals: List[SignalResponse]
    scanned_symbols: int
    scan_time: str

class PnLSummaryResponse(BaseModel):
    daily_pnl: float
    total_pnl: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int

class PortfolioResponse(BaseModel):
    symbol: str
    quantity: float
    avg_entry_price: Optional[float] = None
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: float
    total_invested: float

class DashboardResponse(BaseModel):
    total_pnl: float
    daily_pnl: float
    win_rate: float
    open_positions: int
    total_trades: int
    active_signals: int
    portfolio_value: float
    recent_trades: List[TradeResponse]
    recent_signals: List[SignalResponse]
    watchlist: List[WatchlistResponse]

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class RiskyModeToggle(BaseModel):
    enabled: bool
    duration_minutes: int = 240  # auto-expires; re-enable explicitly after this
    min_confidence_score: Optional[float] = None
    min_risk_reward: Optional[float] = None
    max_risk_per_trade: Optional[float] = None
    max_daily_loss: Optional[float] = None
    max_drawdown: Optional[float] = None

class RiskyModeStatus(BaseModel):
    enabled: bool
    expires_at: Optional[datetime] = None
    min_confidence_score: float
    min_risk_reward: float
    max_risk_per_trade: float
    max_daily_loss: float
    max_drawdown: float

class MessageResponse(BaseModel):
    message: str
    success: bool = True
