"""
Account API router.
GET /api/account — account overview
GET /api/positions — open positions
GET /api/equity-curve — historical equity snapshots
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.database import get_supabase
from app.brokers.alpaca import AlpacaAdapter
from app.models.schemas import AccountOverview, PositionInfo, EquityPoint

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["account"])


def _get_broker():
    """Get broker adapter instance."""
    try:
        return AlpacaAdapter()
    except Exception as e:
        logger.error(f"Failed to initialize broker: {e}")
        return None


@router.get("/account", response_model=AccountOverview)
async def get_account():
    """Get account overview with equity, buying power, daily P&L."""
    db = get_supabase()

    # Get system state
    state = db.table("system_state").select("*").limit(1).execute()
    system = state.data[0] if state.data else {}

    broker = _get_broker()
    if broker:
        try:
            acct = broker.get_account()
            positions = broker.get_positions()
            return AccountOverview(
                equity=acct.equity,
                buying_power=acct.buying_power,
                daily_pnl=acct.daily_pnl,
                open_positions=len(positions),
                trading_mode=system.get("trading_mode", "paper"),
                kill_switch_active=system.get("kill_switch_active", False),
            )
        except Exception as e:
            logger.error(f"Broker error: {e}")

    # Fallback to latest snapshot
    snapshot = (
        db.table("account_snapshots")
        .select("*")
        .order("snapshot_at", desc=True)
        .limit(1)
        .execute()
    )
    if snapshot.data:
        s = snapshot.data[0]
        return AccountOverview(
            equity=s.get("equity", 0),
            buying_power=s.get("buying_power", 0),
            daily_pnl=s.get("daily_pnl", 0),
            open_positions=0,
            trading_mode=system.get("trading_mode", "paper"),
            kill_switch_active=system.get("kill_switch_active", False),
        )

    return AccountOverview(
        equity=0, buying_power=0, daily_pnl=0, open_positions=0,
        trading_mode="paper", kill_switch_active=False,
    )


@router.get("/positions", response_model=list[PositionInfo])
async def get_positions():
    """Get all open positions from broker."""
    broker = _get_broker()
    if not broker:
        return []

    try:
        positions = broker.get_positions()
        return [
            PositionInfo(
                symbol=p.symbol,
                qty=p.qty,
                avg_entry_price=p.avg_entry_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                market_value=p.market_value,
                side=p.side,
            )
            for p in positions
        ]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []


@router.get("/equity-curve", response_model=list[EquityPoint])
async def get_equity_curve():
    """Get historical equity snapshots for charting."""
    db = get_supabase()
    result = (
        db.table("account_snapshots")
        .select("equity, snapshot_at")
        .order("snapshot_at", desc=False)
        .limit(500)
        .execute()
    )
    return result.data or []
