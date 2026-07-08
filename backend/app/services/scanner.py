import asyncio
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.config import settings
from ..core.redis_client import redis_client
from .market_data import market_data_service
from .indicators import indicators_service
from .ai_analysis import ai_service
from .news_service import news_service
from .risk_manager import risk_manager, RiskManager
from .broker import broker_service
from .notifications import notifier
from ..models.models import Watchlist, Signal, Trade, TradeStatus, SignalDirection, TradeMode, User


class MarketScanner:
    def __init__(self):
        self.is_scanning = False
        self.scan_count = 0

    async def execute_signal(self, signal: Signal, user: User, db: AsyncSession) -> Dict:
        """
        Turns a validated signal into an actual trade — real broker order in
        live mode, a paper-fill record in paper mode. Shared by both the
        auto-execute path (scanner) and the manual "Approve" button
        (routes.py) so there's exactly one place this logic lives.
        """
        account_balance = await broker_service.get_account_balance()
        local_rm = RiskManager(user=user)
        quantity, actual_risk = local_rm.calculate_position_size(
            account_balance, signal.entry_price, signal.stop_loss, signal.risk_percentage
        )

        if user.trade_mode == TradeMode.LIVE:
            side = "sell" if signal.direction == SignalDirection.SHORT else "buy"
            order = await broker_service.place_market_order(signal.symbol, side, quantity)
            if not order:
                signal.status = TradeStatus.REJECTED
                await db.commit()
                return {"executed": False, "reason": "Broker order failed — check broker API keys/logs"}
            order_id = order.get("id", "")
            broker_resp = order
        else:
            order_id = f"paper_{uuid.uuid4()}"
            broker_resp = {"mode": "paper", "order_id": order_id}

        signal.status = TradeStatus.APPROVED
        trade = Trade(
            user_id=user.id, signal_id=signal.id, symbol=signal.symbol,
            direction=signal.direction, entry_price=signal.entry_price,
            quantity=quantity, stop_loss=signal.stop_loss, take_profit=signal.take_profit,
            status=TradeStatus.OPEN, risk_percentage=actual_risk,
            risk_reward_ratio=signal.risk_reward_ratio, confidence_score=signal.confidence_score,
            ai_reasoning=signal.trade_explanation, broker_order_id=order_id,
            broker_response=broker_resp, trade_mode=user.trade_mode, entry_time=datetime.utcnow()
        )
        db.add(trade)
        await db.commit()

        await notifier.notify_trade_execution({
            "symbol": signal.symbol, "direction": signal.direction.value,
            "entry_price": signal.entry_price, "quantity": quantity, "order_id": order_id
        })
        return {"executed": True, "trade_id": str(trade.id), "order_id": order_id}

    async def scan_symbol(self, symbol: str, user: User, user_settings: Dict, db: AsyncSession) -> Optional[Dict]:
        try:
            # Bug fix: this used to fetch 5 timeframes (5m/15m/1h/4h/1d) per
            # symbol via fetch_multiple_timeframes, but only ever read '1h'
            # out of the result — the other 4 were fetched and thrown away.
            # For a watchlist of even 10 symbols that's 50 API calls per scan
            # cycle instead of 10, which is exactly the kind of load that
            # gets yfinance/exchange rate-limited or blocked. Fetch only what
            # gets used.
            primary_tf = '1h'
            df = await market_data_service.fetch_ohlcv(symbol, primary_tf, limit=200)
            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                return None

            indicators = indicators_service.compute_all_indicators(df)
            if not indicators:
                return None

            # Real news headlines feed into the AI's own sentiment judgment
            # (previously always "" — see news_service.py docstring).
            news_text = await news_service.get_headlines(symbol)

            ai_result = await ai_service.analyze_signal(symbol, indicators, news=news_text)
            if not ai_result:
                return None

            if ai_result["direction"] == "neutral":
                return None

            local_rm = RiskManager(user=user)
            validated, msg = await local_rm.validate_signal(ai_result, str(user.id), db)
            if not validated:
                logger.info(f"{symbol}: {msg}")
                return None

            signal_record = Signal(
                user_id=user.id,
                symbol=symbol,
                direction=SignalDirection(ai_result["direction"]),
                entry_price=ai_result.get("entry_price"),
                stop_loss=ai_result.get("stop_loss"),
                take_profit=ai_result.get("take_profit"),
                confidence_score=ai_result.get("confidence_score"),
                risk_reward_ratio=ai_result.get("risk_reward_ratio"),
                risk_percentage=ai_result.get("risk_percentage"),
                reason=ai_result.get("reason", ""),
                trade_explanation=ai_result.get("trade_explanation", ""),
                ai_analysis=ai_result,
                indicators_data=indicators,
                news_sentiment=ai_result.get("news_sentiment", "neutral"),
                market_context=ai_result.get("market_context", ""),
                status=TradeStatus.PENDING,
                timeframe=primary_tf
            )
            db.add(signal_record)
            await db.commit()
            await db.refresh(signal_record)

            execution_result = None
            if settings.AUTO_EXECUTE:
                try:
                    execution_result = await self.execute_signal(signal_record, user, db)
                except Exception as e:
                    logger.error(f"Auto-execute failed for {symbol}: {e}")
                    execution_result = {"executed": False, "reason": str(e)}

            signal_data = {
                "id": str(signal_record.id),
                "symbol": symbol,
                "direction": ai_result["direction"],
                "entry_price": ai_result.get("entry_price"),
                "stop_loss": ai_result.get("stop_loss"),
                "take_profit": ai_result.get("take_profit"),
                "confidence": ai_result.get("confidence_score"),
                "risk_reward": ai_result.get("risk_reward_ratio"),
                "reason": ai_result.get("reason", ""),
                "auto_executed": bool(execution_result and execution_result.get("executed")),
                "timestamp": datetime.utcnow().isoformat()
            }

            await redis_client.publish("signals", signal_data)
            logger.info(f"Signal generated: {symbol} {ai_result['direction']} (confidence: {ai_result.get('confidence_score', 0)}%, auto_executed={signal_data['auto_executed']})")
            return signal_data

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    async def scan_watchlist(self, user_id: str, db: AsyncSession) -> List[Dict]:
        result = await db.execute(
            select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.is_active == True)
        )
        watchlist = result.scalars().all()
        if not watchlist:
            default_symbols = settings.WATCHLIST_SYMBOLS.split(",")
            for sym in default_symbols:
                wl = Watchlist(user_id=user_id, symbol=sym.strip(), timeframe="1h")
                db.add(wl)
            await db.commit()
            watchlist = default_symbols
        else:
            watchlist = [w.symbol for w in watchlist]

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return []

        user_settings = {
            "max_risk_per_trade": user.max_risk_per_trade,
            "max_daily_loss": user.max_daily_loss,
            "max_drawdown": user.max_drawdown,
            "max_open_positions": user.max_open_positions,
            "min_confidence_score": user.min_confidence_score,
            "min_risk_reward": user.min_risk_reward,
        }

        # Bug fix: the original code ran `asyncio.gather(*tasks)` where every
        # task shared the SAME AsyncSession `db`. SQLAlchemy's AsyncSession is
        # not safe for concurrent use across coroutines — under real load this
        # throws "this session is already in use" or silently corrupts state.
        # Scan sequentially instead; each scan_symbol call already does its own
        # commit so this is still correct, just not parallel across symbols.
        results = []
        for sym in watchlist:
            try:
                r = await self.scan_symbol(sym, user, user_settings, db)
                results.append(r)
            except Exception as e:
                logger.error(f"Error scanning {sym}: {e}")
        self.scan_count += 1
        return [r for r in results if isinstance(r, dict)]

    async def continuous_scan(self, user_id: str, db_factory):
        self.is_scanning = True
        while self.is_scanning:
            try:
                async with db_factory() as db:
                    signals = await self.scan_watchlist(user_id, db)
                    if signals:
                        logger.info(f"Scan {self.scan_count}: {len(signals)} signals found")
                    else:
                        logger.debug(f"Scan {self.scan_count}: No signals")
            except Exception as e:
                logger.error(f"Scan cycle error: {e}")
            await asyncio.sleep(settings.SCAN_INTERVAL_MINUTES * 60)

    def stop(self):
        self.is_scanning = False

market_scanner = MarketScanner()
