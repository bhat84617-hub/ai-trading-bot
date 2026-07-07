from typing import Dict, Optional, Tuple
from datetime import datetime, date
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.models import Trade, TradeStatus, SignalDirection
from ..core.config import settings

class RiskManager:
    def __init__(self, user_settings: Optional[Dict] = None):
        self.max_risk_per_trade = user_settings.get("max_risk_per_trade", settings.MAX_RISK_PER_TRADE) if user_settings else settings.MAX_RISK_PER_TRADE
        self.max_daily_loss = user_settings.get("max_daily_loss", settings.MAX_DAILY_LOSS) if user_settings else settings.MAX_DAILY_LOSS
        self.max_drawdown = user_settings.get("max_drawdown", settings.MAX_DRAWDOWN) if user_settings else settings.MAX_DRAWDOWN
        self.max_open_positions = user_settings.get("max_open_positions", settings.MAX_OPEN_POSITIONS) if user_settings else settings.MAX_OPEN_POSITIONS
        self.min_confidence = user_settings.get("min_confidence_score", settings.MIN_CONFIDENCE_SCORE) if user_settings else settings.MIN_CONFIDENCE_SCORE
        self.min_risk_reward = user_settings.get("min_risk_reward", settings.MIN_RISK_REWARD) if user_settings else settings.MIN_RISK_REWARD

    async def validate_signal(self, signal_data: Dict, user_id: str, db: AsyncSession) -> Tuple[bool, str]:
        direction = signal_data.get("direction", "neutral")
        confidence = signal_data.get("confidence_score", 0)
        risk_reward = signal_data.get("risk_reward_ratio", 0)
        risk_pct = signal_data.get("risk_percentage", 0)
        entry = signal_data.get("entry_price", 0)
        sl = signal_data.get("stop_loss", 0)
        tp = signal_data.get("take_profit", 0)

        if direction == "neutral":
            return False, "No trade signal (neutral direction)"

        if confidence < self.min_confidence:
            return False, f"Low confidence: {confidence}% < {self.min_confidence}% minimum"

        if risk_reward < self.min_risk_reward:
            return False, f"Poor R:R ratio: {risk_reward:.2f} < {self.min_risk_reward} minimum"

        if risk_pct > self.max_risk_per_trade:
            return False, f"Risk {risk_pct}% exceeds max {self.max_risk_per_trade}% per trade"

        if not await self._check_daily_loss_limit(user_id, db):
            return False, f"Daily loss limit ({self.max_daily_loss}%) reached"

        if not await self._check_drawdown_limit(user_id, db):
            return False, f"Max drawdown ({self.max_drawdown}%) exceeded"

        if not await self._check_position_limit(user_id, db):
            return False, f"Max open positions ({self.max_open_positions}) reached"

        if sl and entry and direction == "long" and sl >= entry:
            return False, "Stop loss must be below entry for long trades"
        if sl and entry and direction == "short" and sl <= entry:
            return False, "Stop loss must be above entry for short trades"
        if tp and entry and direction == "long" and tp <= entry:
            return False, "Take profit must be above entry for long trades"
        if tp and entry and direction == "short" and tp >= entry:
            return False, "Take profit must be below entry for short trades"

        return True, "Signal validated"

    async def _check_daily_loss_limit(self, user_id: str, db: AsyncSession) -> bool:
        today_start = datetime.combine(date.today(), datetime.min.time())
        result = await db.execute(
            select(func.sum(Trade.pnl)).where(
                Trade.user_id == user_id,
                Trade.status == TradeStatus.CLOSED,
                Trade.entry_time >= today_start,
                Trade.pnl < 0
            )
        )
        daily_loss = abs(result.scalar() or 0)
        if daily_loss > 0:
            loss_pct = (daily_loss / 100000) * 100
            if loss_pct >= self.max_daily_loss:
                return False
        return True

    async def _check_drawdown_limit(self, user_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(Trade.pnl).where(
                Trade.user_id == user_id,
                Trade.status == TradeStatus.CLOSED
            ).order_by(Trade.entry_time.desc()).limit(20)
        )
        pnls = result.scalars().all()
        if len(pnls) < 5:
            return True
        peak = 0
        drawdown = 0
        running_total = 0
        for pnl in reversed(pnls):
            running_total += (pnl or 0)
            if running_total > peak:
                peak = running_total
                drawdown = 0
            else:
                drawdown = peak - running_total
        total_pnl = sum(pnl for pnl in pnls if pnl)
        if total_pnl > 0 and drawdown > 0:
            dd_pct = (drawdown / (peak + abs(total_pnl))) * 100 if peak > 0 else 0
            if dd_pct >= self.max_drawdown:
                return False
        return True

    async def _check_position_limit(self, user_id: str, db: AsyncSession) -> bool:
        result = await db.execute(
            select(func.count(Trade.id)).where(
                Trade.user_id == user_id,
                Trade.status == TradeStatus.OPEN
            )
        )
        open_count = result.scalar() or 0
        return open_count < self.max_open_positions

    def calculate_position_size(self, account_balance: float, entry_price: float, stop_loss: float, risk_percentage: float) -> Tuple[float, float]:
        risk_amount = account_balance * (risk_percentage / 100)
        price_risk = abs(entry_price - stop_loss)
        if price_risk == 0:
            return 0, 0
        quantity = risk_amount / price_risk
        actual_risk = (quantity * price_risk / account_balance) * 100
        return round(quantity, 4), round(actual_risk, 2)

    async def check_overall_risk(self, user_id: str, db: AsyncSession) -> Dict:
        return {
            "daily_loss_ok": await self._check_daily_loss_limit(user_id, db),
            "drawdown_ok": await self._check_drawdown_limit(user_id, db),
            "position_limit_ok": await self._check_position_limit(user_id, db)
        }

risk_manager = RiskManager()
