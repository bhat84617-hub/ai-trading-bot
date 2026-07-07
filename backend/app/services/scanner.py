import asyncio
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
from .risk_manager import risk_manager, RiskManager
from ..models.models import Watchlist, Signal, Trade, TradeStatus, SignalDirection, User

class MarketScanner:
    def __init__(self):
        self.is_scanning = False
        self.scan_count = 0

    async def scan_symbol(self, symbol: str, user_id: str, user_settings: Dict, db: AsyncSession) -> Optional[Dict]:
        try:
            timeframes = ['5m', '15m', '1h', '4h', '1d']
            multi_tf_data = await market_data_service.fetch_multiple_timeframes(symbol, timeframes)
            if not multi_tf_data:
                logger.warning(f"No data for {symbol}")
                return None

            primary_tf = '1h'
            df = multi_tf_data.get(primary_tf)
            if df is None or df.empty:
                return None

            indicators = indicators_service.compute_all_indicators(df)
            if not indicators:
                return None

            ai_result = await ai_service.analyze_signal(symbol, indicators)
            if not ai_result:
                return None

            if ai_result["direction"] == "neutral":
                return None

            local_rm = RiskManager(user_settings)
            validated, msg = await local_rm.validate_signal(ai_result, user_id, db)
            if not validated:
                logger.info(f"{symbol}: {msg}")
                return None

            signal_record = Signal(
                user_id=user_id,
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
                "timestamp": datetime.utcnow().isoformat()
            }

            await redis_client.publish("signals", signal_data)
            logger.info(f"Signal generated: {symbol} {ai_result['direction']} (confidence: {ai_result.get('confidence_score', 0)}%)")
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

        tasks = [self.scan_symbol(sym, user_id, user_settings, db) for sym in watchlist]
        results = await asyncio.gather(*tasks, return_exceptions=True)
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
