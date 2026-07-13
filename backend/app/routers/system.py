"""
System State API router.
GET  /api/system-state
POST /api/system-state/kill-switch
POST /api/system-state/mode
POST /api/system-state/arm-live
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException

from app.database import get_supabase
from app.models.schemas import (
    SystemStateRead,
    KillSwitchRequest,
    ModeChangeRequest,
    ArmLiveRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system-state", tags=["system"])


async def _get_or_create_system_state():
    """Retrieve or create a single system state row."""
    db = get_supabase()
    result = db.table("system_state").select("*").limit(1).execute()
    if not result.data:
        default_state = {
            "kill_switch_active": False,
            "kill_switch_reason": None,
            "trading_mode": "paper",
            "live_armed_until": None,
        }
        insert_result = db.table("system_state").insert(default_state).execute()
        if not insert_result.data:
            raise HTTPException(status_code=500, detail="Failed to initialize system state")
        return insert_result.data[0]
    return result.data[0]


@router.get("", response_model=SystemStateRead)
async def get_system_state():
    """Retrieve system state."""
    state = await _get_or_create_system_state()
    return state


@router.post("/kill-switch", response_model=SystemStateRead)
async def set_kill_switch(payload: KillSwitchRequest):
    """Activate or deactivate the global trading kill switch."""
    db = get_supabase()
    state = await _get_or_create_system_state()
    
    update_data = {
        "kill_switch_active": payload.active,
        "kill_switch_reason": payload.reason if payload.active else None,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = db.table("system_state").update(update_data).eq("id", state["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update kill switch state")
        
    logger.warning(f"Kill switch state updated: active={payload.active}, reason={payload.reason}")
    return result.data[0]


@router.post("/mode", response_model=SystemStateRead)
async def set_trading_mode(payload: ModeChangeRequest):
    """
    Switch trading mode between 'paper' and 'live'.
    If switching to live, require explicit arming later or set it to armed depending on flow.
    Switching to paper clears live arming.
    """
    db = get_supabase()
    state = await _get_or_create_system_state()
    
    update_data = {
        "trading_mode": payload.mode,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if payload.mode == "paper":
        update_data["live_armed_until"] = None
        
    result = db.table("system_state").update(update_data).eq("id", state["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update trading mode")
        
    logger.info(f"Trading mode updated to: {payload.mode}")
    return result.data[0]


@router.post("/arm-live", response_model=SystemStateRead)
async def arm_live(payload: ArmLiveRequest):
    """
    Arm the live execution engine for a set number of hours.
    Can only be done if system is in 'live' mode.
    Auto-expires after 'hours' duration.
    """
    db = get_supabase()
    state = await _get_or_create_system_state()
    
    if state.get("trading_mode") != "live":
        raise HTTPException(
            status_code=400,
            detail="System is not in LIVE mode. Change mode to LIVE before arming."
        )
        
    expiry = datetime.now(timezone.utc) + timedelta(hours=payload.hours)
    update_data = {
        "live_armed_until": expiry.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    result = db.table("system_state").update(update_data).eq("id", state["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to arm live trading")
        
    logger.info(f"Live trading armed until {expiry.isoformat()}")
    return result.data[0]
