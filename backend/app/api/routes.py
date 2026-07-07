from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Header
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, date
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
    LoginRequest, TokenResponse, MessageResponse
)
from ..services.market_data import market_data_service
from ..services.indicators import indicators_service
from ..services.ai_analysis import ai_service
from ..services.risk_manager import risk_manager, RiskManager
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

async def get_current_user(authorization: str = Header(None), token: str = Query(None), db: AsyncSession = Depends(get_db)) -> User:
    auth = token or authorization
    if auth and auth.startswith("Bearer "):
        auth = auth[7:]
    if not auth:
        raise HTTPException(401, "No authorization token")
    payload = verify_token(auth)
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
    if data.action == "reject":
        signal.status = TradeStatus.REJECTED
        await db.commit()
        return MessageResponse(message="Signal rejected")
    signal.status = TradeStatus.APPROVED
    await db.commit()
    account_balance = await broker_service.get_account_balance()
    local_rm = RiskManager({
        "max_risk_per_trade": user.max_risk_per_trade,
        "max_daily_loss": user.max_daily_loss,
        "max_drawdown": user.max_drawdown,
        "max_open_positions": user.max_open_positions,
        "min_confidence_score": user.min_confidence_score,
        "min_risk_reward": user.min_risk_reward,
    })
    quantity, actual_risk = local_rm.calculate_position_size(account_balance, signal.entry_price, signal.stop_loss, signal.risk_percentage)
    if user.trade_mode == TradeMode.LIVE:
        side = "sell" if signal.direction == SignalDirection.SHORT else "buy"
        order = await broker_service.place_market_order(signal.symbol, side, quantity)
        order_id = order.get("id", "") if order else ""
        broker_resp = order if order else None
    else:
        order_id = f"paper_{uuid.uuid4()}"
        broker_resp = {"mode": "paper", "order_id": order_id}
    trade = Trade(user_id=user.id, signal_id=signal.id, symbol=signal.symbol, direction=signal.direction, entry_price=signal.entry_price, quantity=quantity, stop_loss=signal.stop_loss, take_profit=signal.take_profit, status=TradeStatus.OPEN, risk_percentage=actual_risk, risk_reward_ratio=signal.risk_reward_ratio, confidence_score=signal.confidence_score, ai_reasoning=signal.trade_explanation, broker_order_id=order_id, broker_response=broker_resp, trade_mode=user.trade_mode, entry_time=datetime.utcnow())
    db.add(trade)
    await db.commit()
    await notifier.notify_trade_execution({"symbol": signal.symbol, "direction": signal.direction.value, "entry_price": signal.entry_price, "quantity": quantity, "order_id": order_id})
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
    await notifier.notify_trade_result({"symbol": trade.symbol, "direction": trade.direction.value, "entry_price": trade.entry_price, "exit_price": trade.exit_price, "pnl": trade.pnl, "pnl_percentage": trade.pnl_percentage})
    return MessageResponse(message=f"Trade closed. PnL: {trade.pnl:.2f}")

@router.get("/api/portfolio", response_model=List[PortfolioResponse])
async def get_portfolio(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user.id))
    return [PortfolioResponse.model_validate(p) for p in result.scalars().all()]

@router.get("/api/pnl", response_model=PnLSummaryResponse)
async def get_pnl(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    total_pnl = (await db.execute(select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0
    daily_pnl = (await db.execute(select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.exit_time >= datetime.combine(date.today(), datetime.min.time())))).scalar() or 0
    total_trades = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0
    winning = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl > 0))).scalar() or 0
    losing = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl < 0))).scalar() or 0
    win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
    return PnLSummaryResponse(daily_pnl=float(daily_pnl), total_pnl=float(total_pnl), win_rate=round(win_rate, 1), total_trades=total_trades, winning_trades=winning, losing_trades=losing)

@router.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    total_pnl = float((await db.execute(select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0)
    daily_pnl = float((await db.execute(select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.exit_time >= datetime.combine(date.today(), datetime.min.time()))).scalar() or 0))
    total_trades = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0
    wins = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl > 0))).scalar() or 0
    win_rate = round(wins / total_trades * 100, 1) if total_trades > 0 else 0
    open_count = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.OPEN))).scalar() or 0
    active_sig_count = (await db.execute(select(func.count(Signal.id)).where(Signal.user_id == user.id, Signal.status == TradeStatus.PENDING))).scalar() or 0
    balance = await broker_service.get_account_balance()
    trades = (await db.execute(select(Trade).where(Trade.user_id == user.id).order_by(desc(Trade.created_at)).limit(5))).scalars().all()
    signals = (await db.execute(select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(5))).scalars().all()
    watchlist = (await db.execute(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at))).scalars().all()
    return DashboardResponse(total_pnl=total_pnl, daily_pnl=daily_pnl, win_rate=win_rate, open_positions=open_count, total_trades=total_trades, active_signals=active_sig_count, portfolio_value=balance, recent_trades=[TradeResponse.model_validate(t) for t in trades], recent_signals=[SignalResponse.model_validate(s) for s in signals], watchlist=[WatchlistResponse.model_validate(w) for w in watchlist])

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
    return AIAnalysisResponse(symbol=data.symbol, direction=SignalDirection(result["direction"]), entry_price=result["entry_price"], stop_loss=result["stop_loss"], take_profit=result["take_profit"], confidence_score=result["confidence_score"], risk_reward_ratio=result["risk_reward_ratio"], risk_percentage=result["risk_percentage"], reason=result["reason"], trade_explanation=result["trade_explanation"], news_sentiment=result.get("news_sentiment", "neutral"), market_context=result.get("market_context", ""), indicators_data=indicators)

@router.post("/api/broker/switch")
async def switch_broker(data: dict, user: User = Depends(get_current_user)):
    broker = data.get("broker", "binance")
    await broker_service.switch_broker(broker)
    return {"message": f"Switched to {broker}", "broker": broker, "success": True}

@router.get("/api/broker/list")
async def broker_list(user: User = Depends(get_current_user)):
    return {"brokers": [
        {"id":"binance","label":"Binance","type":"crypto"}, {"id":"bybit","label":"Bybit","type":"crypto"},
        {"id":"okx","label":"OKX","type":"crypto"}, {"id":"kucoin","label":"KuCoin","type":"crypto"},
        {"id":"kraken","label":"Kraken","type":"crypto"}, {"id":"coinbase","label":"Coinbase","type":"crypto"},
        {"id":"gateio","label":"Gate.io","type":"crypto"}, {"id":"bitget","label":"Bitget","type":"crypto"},
        {"id":"mexc","label":"MEXC","type":"crypto"}, {"id":"coindcx","label":"CoinDCX","type":"crypto"},
        {"id":"alpaca","label":"Alpaca","type":"stocks"}, {"id":"dhan","label":"Dhan (India)","type":"stocks"},
        {"id":"oanda","label":"OANDA","type":"forex"}, {"id":"octafx","label":"OctaFX","type":"forex"},
    ]}
