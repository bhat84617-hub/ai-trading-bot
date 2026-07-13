"""
Pydantic schemas for all API request/response payloads.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Watchlist ──────────────────────────────────────────────────────────

class WatchlistItemCreate(BaseModel):
    symbol: str
    asset_type: str = Field(pattern=r"^(stock|crypto)$")


class WatchlistItem(BaseModel):
    id: str
    symbol: str
    asset_type: str
    active: bool
    created_at: datetime


# ── Strategy Config ───────────────────────────────────────────────────

class StrategyConfig(BaseModel):
    id: Optional[str] = None
    symbol: str
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ma_short: int = 20
    ma_long: int = 50
    live_eligible: bool = False
    updated_at: Optional[datetime] = None


# ── Risk Config ───────────────────────────────────────────────────────

class RiskConfigRead(BaseModel):
    id: str
    risk_pct_per_trade: float
    daily_loss_limit_pct: float
    max_open_positions: int
    updated_at: datetime


class RiskConfigUpdate(BaseModel):
    risk_pct_per_trade: Optional[float] = None
    daily_loss_limit_pct: Optional[float] = None
    max_open_positions: Optional[int] = None


# ── System State ──────────────────────────────────────────────────────

class SystemStateRead(BaseModel):
    id: str
    kill_switch_active: bool
    kill_switch_reason: Optional[str] = None
    trading_mode: str
    live_armed_until: Optional[datetime] = None
    updated_at: datetime


class KillSwitchRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


class ModeChangeRequest(BaseModel):
    mode: str = Field(pattern=r"^(paper|live)$")


class ArmLiveRequest(BaseModel):
    hours: int = Field(ge=1, le=24, default=4)


# ── Trade History ─────────────────────────────────────────────────────

class TradeRecord(BaseModel):
    id: str
    symbol: str
    side: str
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: Optional[float] = None
    status: str
    signal_reason: Optional[dict] = None
    broker: str
    mode: str
    opened_at: datetime
    closed_at: Optional[datetime] = None


# ── Account ───────────────────────────────────────────────────────────

class AccountOverview(BaseModel):
    equity: float
    buying_power: float
    daily_pnl: float
    open_positions: int
    trading_mode: str
    kill_switch_active: bool


class PositionInfo(BaseModel):
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    market_value: float
    side: str


class EquityPoint(BaseModel):
    equity: float
    snapshot_at: datetime


# ── Backtest ──────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    symbol: str
    period_start: date
    period_end: date
    # Optional strategy overrides
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ma_short: int = 20
    ma_long: int = 50


class BacktestResult(BaseModel):
    id: Optional[str] = None
    symbol: str
    strategy_config_id: Optional[str] = None
    period_start: date
    period_end: date
    total_trades: int
    win_rate: float
    avg_r_multiple: float
    profit_factor: float
    max_drawdown_pct: float
    created_at: datetime


# ── Walk-Forward ──────────────────────────────────────────────────────

class WalkForwardRequest(BaseModel):
    symbol: str
    period_start: date
    period_end: date
    num_windows: int = Field(ge=2, le=20, default=5)
    min_trades_threshold: int = 50
    min_profit_factor_threshold: float = 1.2


class WalkForwardResult(BaseModel):
    id: Optional[str] = None
    symbol: str
    strategy_config_id: Optional[str] = None
    num_windows: int
    total_trades_across_windows: int
    aggregate_win_rate: float
    aggregate_profit_factor: float
    worst_window_drawdown_pct: float
    passed: bool
    min_trades_threshold: int
    min_profit_factor_threshold: float
    created_at: datetime


# ── Signal ────────────────────────────────────────────────────────────

class SignalDetail(BaseModel):
    symbol: str
    direction: str  # 'buy', 'sell', 'hold'
    regime: str  # 'trending', 'ranging'
    confirming_indicators: list[str]
    indicator_values: dict
    confidence: int  # number of confirming indicators (2-4)
    timestamp: datetime


# ── Scan Response ─────────────────────────────────────────────────────

class ScanResponse(BaseModel):
    signals: list[SignalDetail]
    scanned_symbols: int
    scan_time_ms: float
