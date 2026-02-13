"""
AUTO-BROKER: Redis Service
"""
import json
import os
from typing import Optional, Any, Dict
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


class RedisService:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        
    async def connect(self):
        try:
            self.client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
            await self.client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.error("Redis connection failed", error=str(e))
            raise
    
    async def disconnect(self):
        if self.client:
            await self.client.close()
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.client.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error("Redis set error", error=str(e))
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            value = await self.client.get(key)
            if value is None:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error("Redis get error", error=str(e))
            return None
    
    async def check_health(self) -> dict:
        try:
            await self.client.ping()
            info = await self.client.info()
            return {"status": "healthy", "version": info.get("redis_version", "unknown")}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}


redis_service = RedisService()


async def get_redis() -> RedisService:
    if redis_service.client is None:
        await redis_service.connect()
    return redis_service
