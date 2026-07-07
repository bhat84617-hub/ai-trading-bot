import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from loguru import logger
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.scanner import market_scanner
from app.core.redis_client import redis_client

async def run_scanner():
    await redis_client.connect()
    logger.info(f"Scanner worker started. Scanning every {settings.SCAN_INTERVAL_MINUTES} minutes")
    from sqlalchemy import select
    from app.models.models import User
    async with SessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            await market_scanner.continuous_scan(str(user.id), SessionLocal)
        else:
            logger.warning("No users found. Create a user first via API.")

if __name__ == "__main__":
    try:
        asyncio.run(run_scanner())
    except KeyboardInterrupt:
        market_scanner.stop()
        logger.info("Scanner stopped")
