"""
Redis Cache Service

Provides caching functionality for provider health status and other data.
"""

import json
from typing import Optional, Any, Dict
from datetime import timedelta

import redis.asyncio as redis
import structlog

from app.core.config import settings


logger = structlog.get_logger(__name__)


class RedisCache:
    """
    Redis cache service for provider health and other cached data.
    
    Features:
    - Health status caching with 30-second TTL
    - JSON serialization/deserialization
    - Automatic connection management
    """
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish Redis connection"""
        if self._connected:
            return
        
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info("redis_connected", url=settings.REDIS_URL)
            
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("redis_disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        if not self._connected:
            await self.connect()
        
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            
            # Deserialize JSON
            return json.loads(value)
            
        except Exception as e:
            logger.error("cache_get_failed", key=key, error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time-to-live in seconds (optional)
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            # Serialize to JSON
            serialized = json.dumps(value)
            
            if ttl_seconds:
                await self._client.setex(key, ttl_seconds, serialized)
            else:
                await self._client.set(key, serialized)
            
            return True
            
        except Exception as e:
            logger.error("cache_set_failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            await self._client.delete(key)
            return True
            
        except Exception as e:
            logger.error("cache_delete_failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if key exists, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error("cache_exists_failed", key=key, error=str(e))
            return False
    
    # Provider health specific methods
    
    async def get_provider_health(self, provider: str) -> Optional[Dict]:
        """
        Get cached provider health status.
        
        Args:
            provider: Provider type (e.g., 'claude', 'openai')
        
        Returns:
            Health status dict or None if not cached
        """
        key = f"provider_health:{provider}"
        return await self.get(key)
    
    async def set_provider_health(
        self,
        provider: str,
        health_status: Dict,
        ttl_seconds: int = 30,
    ) -> bool:
        """
        Cache provider health status with 30-second TTL.
        
        Args:
            provider: Provider type (e.g., 'claude', 'openai')
            health_status: Health status dictionary
            ttl_seconds: Time-to-live (default 30 seconds)
        
        Returns:
            True if successful, False otherwise
        """
        key = f"provider_health:{provider}"
        return await self.set(key, health_status, ttl_seconds)
    
    async def get_all_provider_health(self) -> Dict[str, Dict]:
        """
        Get cached health status for all providers.
        
        Returns:
            Dictionary mapping provider names to health status
        """
        if not self._connected:
            await self.connect()
        
        try:
            # Get all provider health keys
            pattern = "provider_health:*"
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            
            if not keys:
                return {}
            
            # Get all values
            result = {}
            for key in keys:
                provider = key.split(":", 1)[1]
                health = await self.get(key)
                if health:
                    result[provider] = health
            
            return result
            
        except Exception as e:
            logger.error("get_all_provider_health_failed", error=str(e))
            return {}
    
    async def invalidate_provider_health(self, provider: Optional[str] = None) -> bool:
        """
        Invalidate cached provider health status.
        
        Args:
            provider: Specific provider to invalidate, or None for all
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()
        
        try:
            if provider:
                # Invalidate specific provider
                key = f"provider_health:{provider}"
                await self.delete(key)
            else:
                # Invalidate all providers
                pattern = "provider_health:*"
                keys = []
                async for key in self._client.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    await self._client.delete(*keys)
            
            logger.info("provider_health_invalidated", provider=provider or "all")
            return True
            
        except Exception as e:
            logger.error("invalidate_provider_health_failed", error=str(e))
            return False


# Global cache instance
redis_cache = RedisCache()
