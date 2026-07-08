from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, Enum, JSON, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from ..core.database import Base

class TradeMode(str, enum.Enum):
    PAPER = "paper"
    APPROVAL = "approval"
    LIVE = "live"

class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class SignalDirection(str, enum.Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    trade_mode = Column(Enum(TradeMode), default=TradeMode.PAPER)
    max_risk_per_trade = Column(Float, default=2.0)
    max_daily_loss = Column(Float, default=5.0)
    max_drawdown = Column(Float, default=20.0)
    max_open_positions = Column(Integer, default=5)
    min_confidence_score = Column(Float, default=65.0)
    min_risk_reward = Column(Float, default=2.0)

    # Risky Mode — user-controlled, on-demand loosening of signal-quality
    # thresholds. Deliberately NOT a way to remove the daily-loss/drawdown
    # circuit breaker entirely — those still apply, just with a higher
    # (still capped) ceiling while this is active. See risk_manager.py for
    # the absolute ceilings that can't be overridden from here.
    risky_mode_enabled = Column(Boolean, default=False)
    risky_mode_expires_at = Column(DateTime(timezone=True), nullable=True)
    risky_min_confidence_score = Column(Float, default=40.0)
    risky_min_risk_reward = Column(Float, default=1.2)
    risky_max_risk_per_trade = Column(Float, default=5.0)
    risky_max_daily_loss = Column(Float, default=15.0)
    risky_max_drawdown = Column(Float, default=30.0)

    telegram_chat_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="user", cascade="all, delete-orphan")

class Watchlist(Base):
    __tablename__ = "watchlists"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), default="1h")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watchlists")

class Signal(Base):
    __tablename__ = "signals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    direction = Column(Enum(SignalDirection), nullable=False)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    confidence_score = Column(Float)
    risk_reward_ratio = Column(Float)
    risk_percentage = Column(Float)
    reason = Column(Text)
    trade_explanation = Column(Text)
    ai_analysis = Column(JSON)
    indicators_data = Column(JSON)
    market_context = Column(Text)
    news_sentiment = Column(String(20))
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    timeframe = Column(String(10))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="signals")
    trade = relationship("Trade", back_populates="signal", uselist=False)

class Trade(Base):
    __tablename__ = "trades"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), unique=True)
    symbol = Column(String(20), nullable=False)
    direction = Column(Enum(SignalDirection), nullable=False)
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    pnl = Column(Float)
    pnl_percentage = Column(Float)
    risk_percentage = Column(Float)
    risk_reward_ratio = Column(Float)
    confidence_score = Column(Float)
    ai_reasoning = Column(Text)
    broker_order_id = Column(String(100))
    broker_response = Column(JSON)
    trade_mode = Column(Enum(TradeMode))
    entry_time = Column(DateTime(timezone=True))
    exit_time = Column(DateTime(timezone=True))
    screenshot_url = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="trades")
    signal = relationship("Signal", back_populates="trade")

class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    vwap = Column(Float)
    rsi = Column(Float)
    macd_line = Column(Float)
    macd_signal = Column(Float)
    macd_histogram = Column(Float)
    ema_9 = Column(Float)
    ema_21 = Column(Float)
    ema_50 = Column(Float)
    ema_200 = Column(Float)
    bb_upper = Column(Float)
    bb_middle = Column(Float)
    bb_lower = Column(Float)
    atr = Column(Float)
    support_1 = Column(Float)
    support_2 = Column(Float)
    resistance_1 = Column(Float)
    resistance_2 = Column(Float)
    trend = Column(String(10))
    momentum = Column(Float)
    volume_ratio = Column(Float)
    liquidity_score = Column(Float)
    breakout_signal = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Portfolio(Base):
    __tablename__ = "portfolio"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, default=0)
    avg_entry_price = Column(Float)
    current_price = Column(Float)
    unrealized_pnl = Column(Float)
    realized_pnl = Column(Float, default=0)
    total_invested = Column(Float, default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PnLSummary(Base):
    __tablename__ = "pnl_summary"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    daily_pnl = Column(Float, default=0)
    total_pnl = Column(Float, default=0)
    win_rate = Column(Float, default=0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    largest_win = Column(Float, default=0)
    largest_loss = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
