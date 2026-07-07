"""Dummy Redis client used when redis module is not installed."""
import json
from typing import Optional, Any
from loguru import logger


class DummyRedisClient:
    async def connect(self):
        logger.info("Redis not available — running without cache")

    async def disconnect(self):
        pass

    async def get(self, key: str) -> Optional[str]:
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        pass

    async def delete(self, key: str):
        pass

    async def publish(self, channel: str, message: Any):
        pass

    async def subscribe(self, channel: str):
        return None

    async def exists(self, key: str) -> bool:
        return False

    async def ping(self):
        return True


redis_client = DummyRedisClient()
