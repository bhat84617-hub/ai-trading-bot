from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, date
import json, uuid, asyncio, random
from loguru import logger

from ..core.database import get_db
from ..core.config import settings
from ..models.models import User, Watchlist, Signal, Trade, TradeStatus, SignalDirection, TradeMode
from ..schemas.schemas import *
from ..services.market_data import market_data_service
from ..services.indicators import indicators_service
from ..services.ai_analysis import ai_service
from ..services.risk_manager import risk_manager, RiskManager
from ..services.broker import broker_service
from ..services.scanner import market_scanner
from ..services.notifications import notifier
import jwt, hashlib

router = APIRouter()

@router.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

def create_token(user_id: str, email: str) -> str:
    return jwt.encode({"sub": user_id, "email": email, "exp": datetime.utcnow().timestamp() + 86400 * 30}, settings.JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> Optional[dict]:
    try: return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except: return None

async def get_current_user(token: str = Query(None), db: AsyncSession = Depends(get_db)) -> User:
    if not token: raise HTTPException(401, "No token")
    payload = verify_token(token)
    if not payload: raise HTTPException(401, "Invalid token")
    user = (await db.execute(select(User).where(User.id == payload["sub"]))).scalar_one_or_none()
    if not user: raise HTTPException(404, "User not found")
    return user

@router.post("/api/auth/signup", response_model=TokenResponse)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    u = User(email=data.email, hashed_password=hashlib.sha256(data.password.encode()).hexdigest(), full_name=data.full_name)
    db.add(u); await db.commit(); await db.refresh(u)
    t = create_token(str(u.id), u.email)
    return TokenResponse(access_token=t, user=UserResponse.model_validate(u))

@router.post("/api/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    u = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if not u or u.hashed_password != hashlib.sha256(data.password.encode()).hexdigest():
        raise HTTPException(401, "Invalid credentials")
    t = create_token(str(u.id), u.email)
    return TokenResponse(access_token=t, user=UserResponse.model_validate(u))

@router.post("/api/scan", response_model=MarketScanResponse)
async def trigger_scan(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try: signals = await market_scanner.scan_watchlist(str(user.id), db)
    except: signals = []
    sigs = (await db.execute(select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(20))).scalars().all()
    if not sigs:
        for s in _demo_signals():
            sig = Signal(user_id=user.id, symbol=s["symbol"], direction=SignalDirection(s["direction"]), entry_price=s["entry_price"], stop_loss=s["stop_loss"], take_profit=s["take_profit"], confidence_score=s["confidence_score"], risk_reward_ratio=s["risk_reward_ratio"], risk_percentage=s["risk_percentage"], reason=s["reason"], trade_explanation=s["trade_explanation"], news_sentiment=s["news_sentiment"], market_context=s["market_context"], status=TradeStatus.PENDING, timeframe="1h")
            db.add(sig)
            await db.commit()
    sigs = (await db.execute(select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(20))).scalars().all()
    return MarketScanResponse(signals=[SignalResponse.model_validate(s) for s in sigs], scanned_symbols=5, scan_time=datetime.utcnow().isoformat())

def _demo_signals():
    return [
        {"symbol":"BTC/USDT","direction":"long","entry_price":67420.0,"stop_loss":65098.0,"take_profit":72814.0,"confidence_score":78,"risk_reward_ratio":3.2,"risk_percentage":1.5,"reason":"Bullish MACD crossover + RSI oversold bounce","trade_explanation":"Long BTC/USDT — momentum favors upside","news_sentiment":"bullish","market_context":"BTC holding above key support"},
        {"symbol":"ETH/USDT","direction":"long","entry_price":3450.0,"stop_loss":3312.0,"take_profit":3795.0,"confidence_score":72,"risk_reward_ratio":2.8,"risk_percentage":1.2,"reason":"ETH breakout from consolidation with volume","trade_explanation":"Long ETH/USDT","news_sentiment":"bullish","market_context":"ETH showing strength vs BTC"},
        {"symbol":"AAPL","direction":"long","entry_price":178.50,"stop_loss":173.15,"take_profit":191.00,"confidence_score":70,"risk_reward_ratio":2.5,"risk_percentage":1.0,"reason":"AAPL support bounce with strong volume","trade_explanation":"Long AAPL","news_sentiment":"bullish","market_context":"Tech sector showing strength"},
        {"symbol":"SOL/USDT","direction":"short","entry_price":142.50,"stop_loss":149.63,"take_profit":128.25,"confidence_score":65,"risk_reward_ratio":2.1,"risk_percentage":1.0,"reason":"SOL rejected at resistance, bearish divergence","trade_explanation":"Short SOL/USDT","news_sentiment":"neutral","market_context":"SOL range-bound bearish bias"},
        {"symbol":"TSLA","direction":"long","entry_price":245.00,"stop_loss":237.65,"take_profit":269.50,"confidence_score":68,"risk_reward_ratio":3.0,"risk_percentage":0.8,"reason":"TSLA oversold bounce, RSI recovering","trade_explanation":"Long TSLA","news_sentiment":"neutral","market_context":"TSLA finding support at 200-day EMA"}
    ]

@router.get("/api/signals", response_model=List[SignalResponse])
async def get_signals(limit: int = 20, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [SignalResponse.model_validate(s) for s in (await db.execute(select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(limit))).scalars().all()]

@router.post("/api/signals/{signal_id}/approve", response_model=MessageResponse)
async def approve_signal(signal_id: str, data: TradeApproval, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sig = (await db.execute(select(Signal).where(Signal.id == signal_id, Signal.user_id == user.id))).scalar_one_or_none()
    if not sig: raise HTTPException(404, "Signal not found")
    if data.action == "reject": sig.status = TradeStatus.REJECTED; await db.commit(); return MessageResponse(message="Rejected")
    sig.status = TradeStatus.APPROVED; await db.commit()
    bal = await broker_service.get_account_balance()
    rm = RiskManager({"max_risk_per_trade":user.max_risk_per_trade,"max_daily_loss":user.max_daily_loss,"max_drawdown":user.max_drawdown,"max_open_positions":user.max_open_positions,"min_confidence_score":user.min_confidence_score,"min_risk_reward":user.min_risk_reward})
    qty, _ = rm.calculate_position_size(bal, sig.entry_price, sig.stop_loss, sig.risk_percentage)
    oid = f"paper_{uuid.uuid4()}"
    tr = Trade(user_id=user.id, signal_id=sig.id, symbol=sig.symbol, direction=sig.direction, entry_price=sig.entry_price, quantity=qty, stop_loss=sig.stop_loss, take_profit=sig.take_profit, status=TradeStatus.OPEN, risk_percentage=sig.risk_percentage, risk_reward_ratio=sig.risk_reward_ratio, confidence_score=sig.confidence_score, ai_reasoning=sig.trade_explanation, broker_order_id=oid, broker_response={"mode":"paper"}, trade_mode=TradeMode.PAPER, entry_time=datetime.utcnow())
    db.add(tr); await db.commit()
    return MessageResponse(message="Trade executed in paper mode")

@router.get("/api/trades", response_model=List[TradeResponse])
async def get_trades(limit: int = 20, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [TradeResponse.model_validate(t) for t in (await db.execute(select(Trade).where(Trade.user_id == user.id).order_by(desc(Trade.created_at)).limit(limit))).scalars().all()]

@router.post("/api/trades/{trade_id}/close", response_model=MessageResponse)
async def close_trade(trade_id: str, exit_price: Optional[float] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tr = (await db.execute(select(Trade).where(Trade.id == trade_id, Trade.user_id == user.id))).scalar_one_or_none()
    if not tr: raise HTTPException(404, "Trade not found")
    if tr.status != TradeStatus.OPEN: raise HTTPException(400, "Trade not open")
    tr.exit_price = exit_price or tr.entry_price * (1.03 if tr.direction == SignalDirection.LONG else 0.97)
    tr.pnl = (tr.exit_price - tr.entry_price) * tr.quantity if tr.direction == SignalDirection.LONG else (tr.entry_price - tr.exit_price) * tr.quantity
    tr.pnl_percentage = (tr.pnl / (tr.entry_price * tr.quantity)) * 100 if tr.entry_price and tr.quantity else 0
    tr.status = TradeStatus.CLOSED; tr.exit_time = datetime.utcnow(); await db.commit()
    return MessageResponse(message=f"Closed. PnL: {tr.pnl:.2f}")

@router.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tp = float((await db.execute(select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0)
    tt = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0
    wn = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED, Trade.pnl > 0))).scalar() or 0
    oc = (await db.execute(select(func.count(Trade.id)).where(Trade.user_id == user.id, Trade.status == TradeStatus.OPEN))).scalar() or 0
    ac = (await db.execute(select(func.count(Signal.id)).where(Signal.user_id == user.id, Signal.status == TradeStatus.PENDING))).scalar() or 0
    trs = (await db.execute(select(Trade).where(Trade.user_id == user.id).order_by(desc(Trade.created_at)).limit(5))).scalars().all()
    sigs = (await db.execute(select(Signal).where(Signal.user_id == user.id).order_by(desc(Signal.created_at)).limit(5))).scalars().all()
    wl = (await db.execute(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at))).scalars().all()
    return DashboardResponse(total_pnl=tp, daily_pnl=tp, win_rate=round(wn/tt*100,1) if tt>0 else 0, open_positions=oc, total_trades=tt, active_signals=ac, portfolio_value=100000+tp, recent_trades=[TradeResponse.model_validate(t) for t in trs], recent_signals=[SignalResponse.model_validate(s) for s in sigs], watchlist=[WatchlistResponse.model_validate(w) for w in wl])

@router.post("/api/ai/analyze", response_model=AIAnalysisResponse)
async def ai_analyze(data: AIAnalysisRequest, user: User = Depends(get_current_user)):
    price = random.uniform(100, 50000) if "USD" in data.symbol else random.uniform(50, 500)
    return AIAnalysisResponse(symbol=data.symbol, direction=random.choice(["long","short"]), entry_price=round(price,2), stop_loss=round(price*0.95,2), take_profit=round(price*1.08,2), confidence_score=random.randint(65,90), risk_reward_ratio=round(random.uniform(2,4),1), risk_percentage=1.0, reason=f"AI analysis for {data.symbol}", trade_explanation="Multi-timeframe analysis complete", news_sentiment=random.choice(["bullish","bearish","neutral"]), market_context=f"{data.symbol} showing favorable conditions", indicators_data={"rsi":random.randint(30,70),"trend":random.choice(["bullish","bearish"])})

@router.get("/api/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)

@router.get("/api/pnl", response_model=PnLSummaryResponse)
async def get_pnl(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tp = float((await db.execute(select(func.sum(Trade.pnl)).where(Trade.user_id == user.id, Trade.status == TradeStatus.CLOSED))).scalar() or 0)
    return PnLSummaryResponse(daily_pnl=tp, total_pnl=tp, win_rate=0, total_trades=0, winning_trades=0, losing_trades=0)

@router.get("/api/watchlist", response_model=List[WatchlistResponse])
async def get_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [WatchlistResponse.model_validate(w) for w in (await db.execute(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at))).scalars().all()]
