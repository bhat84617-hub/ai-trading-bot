from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Header
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, date, timedelta
import json
import uuid
import asyncio
from loguru import logger

from ..core.database import get_db
from ..core.redis_client import redis_client
from ..core.config import settings
from ..models.models import User, Watchlist, Signal, Trade, Portfolio, PnLSummary, TradeStatus, SignalDirection, TradeMode
from ..schemas.schemas import (
    UserCreate, UserResponse, UserSettingsUpdate, WatchlistCreate, WatchlistResponse,
    SignalResponse, TradeResponse, TradeApproval, AIAnalysisRequest, AIAnalysisResponse,
    MarketScanResponse, PnLSummaryResponse, PortfolioResponse, DashboardResponse,
    LoginRequest, TokenResponse, MessageResponse, RiskyModeToggle, RiskyModeStatus
)
from ..services.market_data import market_data_service
from ..services.indicators import indicators_service
from ..services.ai_analysis import ai_service
from ..services.risk_manager import risk_manager, RiskManager, is_risky_mode_active, ABSOLUTE_MAX_DAILY_LOSS, ABSOLUTE_MAX_DRAWDOWN, ABSOLUTE_MAX_RISK_PER_TRADE
from ..services.broker import broker_service
from ..services.scanner import market_scanner
from ..services.notifications import notifier
import jwt
import hashlib

router = APIRouter()

def create_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": datetime.utcnow().timestamp() + 86400 * 30}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except:
        return None

async def get_current_user(
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Bug fix: frontend sends "Authorization: Bearer <token>" header for most calls,
    # but only ?token= query param for approve/close. Support both so real requests
    # from the dashboard stop failing with 401/422.
    final_token = token
    if not final_token and authorization and authorization.lower().startswith("bearer "):
        final_token = authorization.split(" ", 1)[1]

    if not final_token:
        raise HTTPException(401, "Missing token")

    payload = verify_token(final_token)
    if not payload:
        raise HTTPException(401, "Invalid token")
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    return user

@router.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION, "timestamp": datetime.utcnow().isoformat()}

@router.post("/api/auth/signup", response_model=TokenResponse)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    user = User(email=data.email, hashed_password=hashlib.sha256(data.password.encode()).hexdigest(), full_name=data.full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_token(str(user.id), user.email)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

@router.post("/api/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or user.hashed_password != hashlib.sha256(data.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid credentials")
    token = create_token(str(user.id), user.email)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

@router.get("/api/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)

@router.put("/api/me/settings", response_model=UserResponse)
async def update_settings(data: UserSettingsUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

@router.get("/api/watchlist", response_model=List[WatchlistResponse])
async def get_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at))
    return [WatchlistResponse.model_validate(w) for w in result.scalars().all()]

@router.post("/api/watchlist", response_model=WatchlistResponse)
async def add_to_watchlist(data: WatchlistCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    watch = Watchlist(user_id=user.id, symbol=data.symbol.upper(), timeframe=data.timeframe)
    db.add(watch)
    await db.commit()
    await db.refresh(watch)
    return WatchlistResponse.model_validate(watch)

@router.delete("/api/watchlist/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == user.id))
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(404, "Watchlist item not found")
    await db.delete(w)
    await db.commit()
    return MessageResponse(message="Removed from watchlist")

@router.post("/api/scan", response_model=MarketScanResponse)
async def trigger_scan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    signals = await market_scanner.scan_watchlist(str(user.id), db)
    result = await db.execute(
        select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(20)
    )
    signal_responses = [SignalResponse.model_validate(s) for s in result.scalars().all()]
    return MarketScanResponse(
        signals=signal_responses,
        scanned_symbols=len(settings.WATCHLIST_SYMBOLS.split(",")),
        scan_time=datetime.utcnow().isoformat()
    )

@router.get("/api/signals", response_model=List[SignalResponse])
async def get_signals(limit: int = 20, status: Optional[str] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Signal).where(Signal.user_id == user.id)
    if status:
        query = query.where(Signal.status == TradeStatus(status))
    query = query.order_by(desc(Signal.created_at)).limit(limit)
    result = await db.execute(query)
    return [SignalResponse.model_validate(s) for s in result.scalars().all()]

@router.post("/api/signals/{signal_id}/approve", response_model=MessageResponse)
async def approve_signal(signal_id: str, data: TradeApproval, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id, Signal.user_id == user.id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")

    if signal.status != TradeStatus.PENDING:
        raise HTTPException(400, f"Signal is already '{signal.status.value}' — can't approve again (likely already auto-executed).")

    if data.action == "reject":
        signal.status = TradeStatus.REJECTED
        await db.commit()
        return MessageResponse(message="Signal rejected")

    signal.status = TradeStatus.APPROVED
    await db.commit()

    result = await market_scanner.execute_signal(signal, user, db)
    if not result.get("executed"):
        raise HTTPException(400, result.get("reason", "Trade execution failed"))

    return MessageResponse(message=f"Trade executed in {user.trade_mode.value} mode")

@router.get("/api/trades", response_model=List[TradeResponse])
async def get_trades(limit: int = 20, status: Optional[str] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Trade).where(Trade.user_id == user.id)
    if status:
        query = query.where(Trade.status == TradeStatus(status))
    query = query.order_by(desc(Trade.created_at)).limit(limit)
    result = await db.execute(query)
    return [TradeResponse.model_validate(t) for t in result.scalars().all()]

@router.post("/api/trades/{trade_id}/close", response_model=MessageResponse)
async def close_trade(trade_id: str, exit_price: Optional[float] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trade).where(Trade.id == trade_id, Trade.user_id == user.id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(404, "Trade not found")
    if trade.status != TradeStatus.OPEN:
        raise HTTPException(400, "Trade is not open")

    # Bug fix: this used to only update the DB row — in live mode the real
    # position stayed open at the broker while the dashboard showed
    # "closed". Actually flatten the position for live trades.
    if trade.trade_mode == TradeMode.LIVE:
        close_side = "sell" if trade.direction == SignalDirection.LONG else "buy"
        order = await broker_service.place_market_order(trade.symbol, close_side, trade.quantity)
        if not order:
            raise HTTPException(502, "Broker close order failed — position is still open. Check broker API keys/logs before retrying.")

    if exit_price:
        trade.exit_price = exit_price
    else:
        price = await market_data_service.get_current_price(trade.symbol)
        trade.exit_price = price or trade.entry_price

    if trade.direction == SignalDirection.LONG:
        trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
    else:
        trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity
    trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100 if trade.entry_price and trade.quantity else 0
    trade.status = TradeStatus.CLOSED
    trade.exit_time = datetime.utcnow()
    await db.commit()

    await notifier.notify_trade_result({
        "symbol": trade.symbol, "direction": trade.direction.value,
        "entry_price": trade.entry_price, "exit_price": trade.exit_price,
        "pnl": trade.pnl, "pnl_percentage": trade.pnl_percentage
    })

    return MessageResponse(message=f"Trade closed. PnL: {trade.pnl:.2f}")

@router.get("/api/portfolio", response_model=List[PortfolioResponse])
async def get_portfolio(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user.id))
    return [PortfolioResponse.model_validate(p) for p in result.scalars().all()]

@router.get("/api/pnl", response_model=PnLSummaryResponse)
async def get_pnl(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED)
    )
    total_pnl = result.scalar() or 0

    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await db.execute(
        select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.exit_time >= today_start)
    )
    daily_pnl = result.scalar() or 0

    result = await db.execute(
        select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED)
    )
    total_trades = result.scalar() or 0

    result = await db.execute(
        select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl > 0)
    )
    winning = result.scalar() or 0

    result = await db.execute(
        select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl < 0)
    )
    losing = result.scalar() or 0

    result = await db.execute(
        select(func.max(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED)
    )
    largest_win = result.scalar() or 0
    result = await db.execute(
        select(func.min(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED)
    )
    largest_loss = result.scalar() or 0

    win_rate = (winning / total_trades * 100) if total_trades > 0 else 0

    return PnLSummaryResponse(
        daily_pnl=float(daily_pnl), total_pnl=float(total_pnl), win_rate=round(win_rate, 1),
        total_trades=total_trades, winning_trades=winning, losing_trades=losing
    )

@router.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pnl_result = await db.execute(
        select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED)
    )
    total_pnl = float(pnl_result.scalar() or 0)

    today_start = datetime.combine(date.today(), datetime.min.time())
    daily_result = await db.execute(
        select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.exit_time >= today_start)
    )
    daily_pnl = float(daily_result.scalar() or 0)

    win_result = await db.execute(
        select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED)
    )
    total_trades = win_result.scalar() or 0
    win_count = await db.execute(
        select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl > 0)
    )
    win_rate = round((win_count.scalar() or 0) / total_trades * 100, 1) if total_trades > 0 else 0

    open_pos = await db.execute(
        select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.OPEN)
    )
    open_count = open_pos.scalar() or 0

    active_sig = await db.execute(
        select(func.count(Signal.id)).where(Signal.user_id == user.id, Signal.status == TradeStatus.PENDING)
    )
    active_sig_count = active_sig.scalar() or 0

    balance = await broker_service.get_account_balance()

    recent_trades = await db.execute(
        select(Trade).where(Trade.user_id == user.id).order_by(desc(Trade.created_at)).limit(5)
    )
    recent_signals = await db.execute(
        select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(5)
    )
    watchlist_items = await db.execute(
        select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at)
    )

    return DashboardResponse(
        total_pnl=total_pnl, daily_pnl=daily_pnl, win_rate=win_rate,
        open_positions=open_count, total_trades=total_trades,
        active_signals=active_sig_count, portfolio_value=balance,
        recent_trades=[TradeResponse.model_validate(t) for t in recent_trades.scalars().all()],
        recent_signals=[SignalResponse.model_validate(s) for s in recent_signals.scalars().all()],
        watchlist=[WatchlistResponse.model_validate(w) for w in watchlist_items.scalars().all()]
    )

@router.get("/api/risk/risky-mode", response_model=RiskyModeStatus)
async def get_risky_mode(user: User = Depends(get_current_user)):
    return RiskyModeStatus(
        enabled=is_risky_mode_active(user),
        expires_at=user.risky_mode_expires_at,
        min_confidence_score=user.risky_min_confidence_score,
        min_risk_reward=user.risky_min_risk_reward,
        max_risk_per_trade=min(user.risky_max_risk_per_trade, ABSOLUTE_MAX_RISK_PER_TRADE),
        max_daily_loss=min(user.risky_max_daily_loss, ABSOLUTE_MAX_DAILY_LOSS),
        max_drawdown=min(user.risky_max_drawdown, ABSOLUTE_MAX_DRAWDOWN),
    )

@router.post("/api/risk/risky-mode", response_model=RiskyModeStatus)
async def set_risky_mode(data: RiskyModeToggle, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Bug-safety note: values are clamped to ABSOLUTE_* ceilings no matter
    # what's posted here — Risky Mode loosens signal-quality bars, it does
    # not remove the circuit breaker. See risk_manager.py.
    if data.enabled:
        user.risky_mode_enabled = True
        user.risky_mode_expires_at = datetime.utcnow() + timedelta(minutes=max(1, min(data.duration_minutes, 1440)))
        if data.min_confidence_score is not None:
            user.risky_min_confidence_score = max(0, min(data.min_confidence_score, 100))
        if data.min_risk_reward is not None:
            user.risky_min_risk_reward = max(0.1, data.min_risk_reward)
        if data.max_risk_per_trade is not None:
            user.risky_max_risk_per_trade = min(data.max_risk_per_trade, ABSOLUTE_MAX_RISK_PER_TRADE)
        if data.max_daily_loss is not None:
            user.risky_max_daily_loss = min(data.max_daily_loss, ABSOLUTE_MAX_DAILY_LOSS)
        if data.max_drawdown is not None:
            user.risky_max_drawdown = min(data.max_drawdown, ABSOLUTE_MAX_DRAWDOWN)
    else:
        user.risky_mode_enabled = False
        user.risky_mode_expires_at = None

    await db.commit()
    await db.refresh(user)
    return RiskyModeStatus(
        enabled=is_risky_mode_active(user),
        expires_at=user.risky_mode_expires_at,
        min_confidence_score=user.risky_min_confidence_score,
        min_risk_reward=user.risky_min_risk_reward,
        max_risk_per_trade=min(user.risky_max_risk_per_trade, ABSOLUTE_MAX_RISK_PER_TRADE),
        max_daily_loss=min(user.risky_max_daily_loss, ABSOLUTE_MAX_DAILY_LOSS),
        max_drawdown=min(user.risky_max_drawdown, ABSOLUTE_MAX_DRAWDOWN),
    )

@router.get("/api/broker/list")
async def list_brokers(user: User = Depends(get_current_user)):
    from ..services.broker import SUPPORTED_EXCHANGES
    return {
        "crypto_broker": broker_service._crypto_broker_name,
        "stock_broker": "alpaca",
        "override": broker_service._override_broker,
        "mode": "live" if broker_service.is_live else "paper",
        "alpaca_configured": bool(settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY),
        "crypto_configured": bool(settings.CRYPTO_API_KEY and settings.CRYPTO_SECRET_KEY),
        "available": sorted(SUPPORTED_EXCHANGES.keys()),
    }

@router.post("/api/broker/switch", response_model=MessageResponse)
async def switch_broker(data: dict, user: User = Depends(get_current_user)):
    # Bug fix: same as above — endpoint didn't exist, so "adding" a broker from
    # the UI silently did nothing.
    from ..services.broker import SUPPORTED_EXCHANGES
    broker_name = (data.get("broker") or "").lower().strip()
    if not broker_name:
        raise HTTPException(400, "broker name is required")
    if broker_name not in SUPPORTED_EXCHANGES:
        raise HTTPException(
            400,
            f"Unsupported broker '{broker_name}'. Supported: {sorted(SUPPORTED_EXCHANGES.keys())}"
        )
    await broker_service.switch_broker(broker_name)
    return MessageResponse(message=f"Switched to {broker_name}")

@router.post("/api/ai/analyze", response_model=AIAnalysisResponse)
async def ai_analyze(data: AIAnalysisRequest, user: User = Depends(get_current_user)):
    df = await market_data_service.fetch_ohlcv(data.symbol, data.timeframe)
    if df.empty:
        raise HTTPException(400, f"No data for {data.symbol}")
    indicators = indicators_service.compute_all_indicators(df)
    if not indicators:
        raise HTTPException(400, "Could not compute indicators")
    result = await ai_service.analyze_signal(data.symbol, indicators)
    if not result:
        raise HTTPException(400, "AI analysis failed")
    return AIAnalysisResponse(
        symbol=data.symbol, direction=SignalDirection(result["direction"]),
        entry_price=result["entry_price"], stop_loss=result["stop_loss"],
        take_profit=result["take_profit"], confidence_score=result["confidence_score"],
        risk_reward_ratio=result["risk_reward_ratio"], risk_percentage=result["risk_percentage"],
        reason=result["reason"], trade_explanation=result["trade_explanation"],
        news_sentiment=result.get("news_sentiment", "neutral"),
        market_context=result.get("market_context", ""), indicators_data=indicators
    )

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    pubsub = await redis_client.subscribe("signals")
    if not pubsub:
        await websocket.send_json({"error": "Redis unavailable"})
        await websocket.close()
        return
    try:
        while True:
            message = await pubsub.get_message(timeout=1)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
            try:
                control = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                if control == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user_id}")
    finally:
        await pubsub.unsubscribe("signals")
