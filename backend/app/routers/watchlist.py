"""
Watchlist API router.
GET/POST/DELETE /api/watchlist
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database import get_supabase
from app.models.schemas import WatchlistItemCreate, WatchlistItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItem])
async def get_watchlist():
    """Get all watchlist symbols."""
    db = get_supabase()
    result = db.table("watchlist").select("*").order("created_at", desc=True).execute()
    return result.data or []


@router.post("", response_model=WatchlistItem)
async def add_to_watchlist(item: WatchlistItemCreate):
    """
    Add a symbol to the watchlist.
    Also creates a default strategy_config for the symbol.
    """
    db = get_supabase()

    # Check if already exists
    existing = (
        db.table("watchlist")
        .select("id")
        .eq("symbol", item.symbol.upper())
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail=f"{item.symbol} already in watchlist")

    # Add to watchlist
    result = db.table("watchlist").insert({
        "symbol": item.symbol.upper(),
        "asset_type": item.asset_type,
        "active": True,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to add symbol")

    # Create default strategy config for this symbol
    db.table("strategy_config").insert({
        "symbol": item.symbol.upper(),
        "live_eligible": False,
    }).execute()

    return result.data[0]


@router.delete("/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Remove a symbol from the watchlist."""
    db = get_supabase()
    result = (
        db.table("watchlist")
        .delete()
        .eq("symbol", symbol.upper())
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist")
    return {"message": f"{symbol} removed from watchlist"}


@router.patch("/{symbol}/toggle")
async def toggle_watchlist(symbol: str):
    """Toggle active status of a watchlist symbol."""
    db = get_supabase()

    current = (
        db.table("watchlist")
        .select("active")
        .eq("symbol", symbol.upper())
        .limit(1)
        .execute()
    )
    if not current.data:
        raise HTTPException(status_code=404, detail=f"{symbol} not found")

    new_active = not current.data[0]["active"]
    result = (
        db.table("watchlist")
        .update({"active": new_active})
        .eq("symbol", symbol.upper())
        .execute()
    )
    return result.data[0] if result.data else {"symbol": symbol, "active": new_active}
