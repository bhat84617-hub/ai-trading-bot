"""
Scan Router API.
POST /api/scan — runs a manual/scheduler scan cycle
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.brokers.alpaca import AlpacaAdapter
from app.engine.executor import run_scan_cycle
from app.models.schemas import ScanResponse, SignalDetail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("", response_model=ScanResponse)
async def trigger_scan():
    """Trigger a market scan cycle using the active watchlist."""
    try:
        alpaca = AlpacaAdapter()
    except Exception as e:
        logger.error(f"Failed to initialize broker for scan: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Broker initialization failed: {e}"
        )

    try:
        # Run scanner cycle
        result = run_scan_cycle(alpaca)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        signals = []
        for s in result.get("signals", []):
            signals.append(
                SignalDetail(
                    symbol=s["symbol"],
                    direction=s["direction"],
                    regime=s["regime"],
                    confirming_indicators=s["confirming_indicators"],
                    indicator_values={},  # omitted to keep endpoint payload small/clean
                    confidence=s["confidence"],
                    timestamp=s.get("timestamp", {}),
                )
            )

        return ScanResponse(
            signals=signals,
            scanned_symbols=result.get("scanned_symbols", 0),
            scan_time_ms=result.get("scan_time_ms", 0.0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Scan cycle failed")
        raise HTTPException(status_code=500, detail=f"Scan execution failed: {str(e)}")
