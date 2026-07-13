"""
Trades API router.
GET /api/trades?limit=&symbol= — trade history
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase
from app.models.schemas import TradeRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=list[TradeRecord])
async def get_trades(
    symbol: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    """Get trade history, optionally filtered by symbol."""
    db = get_supabase()
    query = db.table("trade_history").select("*").order("opened_at", desc=True)

    if symbol:
        query = query.eq("symbol", symbol.upper())

    result = query.limit(limit).execute()
    return result.data or []
