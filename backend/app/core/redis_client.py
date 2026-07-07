import redis.asyncio as redis
from .config import settings
import json
from typing import Optional, Any
from loguru import logger

class RedisClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance

    async def connect(self):
        if self._client is None:
            try:
                self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                await self._client.ping()
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Running without cache.")
                self._client = None

    async def disconnect(self):
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        return await self._client.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300):
        if not self._client:
            return
        await self._client.set(key, json.dumps(value) if not isinstance(value, str) else value, ex=ttl)

    async def delete(self, key: str):
        if not self._client:
            return
        await self._client.delete(key)

    async def publish(self, channel: str, message: Any):
        if not self._client:
            return
        await self._client.publish(channel, json.dumps(message) if not isinstance(message, str) else message)

    async def subscribe(self, channel: str):
        if not self._client:
            return None
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def exists(self, key: str) -> bool:
        if not self._client:
            return False
        return await self._client.exists(key) > 0

redis_client = RedisClient()
