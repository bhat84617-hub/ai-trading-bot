"""
Background scan scheduler.
Polls the scan cycle at SCAN_INTERVAL_SECONDS (default 5 mins) or configurable setting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.brokers.alpaca import AlpacaAdapter
from app.engine.executor import run_scan_cycle
from app.config import get_settings

logger = logging.getLogger(__name__)
_scheduler = None


def _scheduled_scan():
    """Execution payload triggered by scheduler."""
    logger.info("Executing scheduled scan cycle...")
    try:
        alpaca = AlpacaAdapter()
        result = run_scan_cycle(alpaca)
        logger.info(
            f"Scheduled scan completed. Scanned: {result.get('scanned_symbols', 0)} symbols. "
            f"Orders placed: {len(result.get('orders_placed', []))}"
        )
    except Exception as e:
        logger.error(f"Scheduled scan failed: {e}", exc_info=True)


def init_scheduler():
    """Start background scheduler for scanning."""
    global _scheduler
    if _scheduler is not None:
        return

    settings = get_settings()
    interval = settings.scan_interval_seconds

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _scheduled_scan,
        trigger=IntervalTrigger(seconds=interval),
        id="trading_scan_job",
        name="Market Scan & Position Exec",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(f"Background scanner started. Running every {interval} seconds.")


def shutdown_scheduler():
    """Shutdown background scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Background scanner scheduler shut down.")
