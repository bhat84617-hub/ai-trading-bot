"""
Risk Config API router.
GET/PUT /api/risk-config
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database import get_supabase
from app.models.schemas import RiskConfigRead, RiskConfigUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/risk-config", tags=["risk"])


@router.get("", response_model=RiskConfigRead)
async def get_risk_config():
    """Get the current risk configuration."""
    db = get_supabase()
    result = db.table("risk_config").select("*").limit(1).execute()
    if not result.data:
        # If no config exists, create default
        default_config = {
            "risk_pct_per_trade": 1.0,
            "daily_loss_limit_pct": 3.0,
            "max_open_positions": 5,
        }
        insert_result = db.table("risk_config").insert(default_config).execute()
        if not insert_result.data:
            raise HTTPException(status_code=500, detail="Failed to initialize default risk config")
        return insert_result.data[0]
    return result.data[0]


@router.put("", response_model=RiskConfigRead)
async def update_risk_config(config: RiskConfigUpdate):
    """Update the risk configuration."""
    db = get_supabase()
    
    # Check if a config row exists
    existing = db.table("risk_config").select("*").limit(1).execute()
    
    update_data = {}
    if config.risk_pct_per_trade is not None:
        update_data["risk_pct_per_trade"] = config.risk_pct_per_trade
    if config.daily_loss_limit_pct is not None:
        update_data["daily_loss_limit_pct"] = config.daily_loss_limit_pct
    if config.max_open_positions is not None:
        update_data["max_open_positions"] = config.max_open_positions
        
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    if not existing.data:
        # Create new config
        result = db.table("risk_config").insert(update_data).execute()
    else:
        # Update existing config row using its ID
        config_id = existing.data[0]["id"]
        result = db.table("risk_config").update(update_data).eq("id", config_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update risk config")
        
    return result.data[0]
