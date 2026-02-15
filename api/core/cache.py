"""
Redis Cache Implementation - BIG TECH 100 Standards
====================================================
Cache-Aside pattern with decorators and async support.
"""

import json
import hashlib
import pickle
import logging
from functools import wraps
from typing import Optional, Callable, Any, Union, TypeVar
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheStrategy(Enum):
    """Strategie di caching disponibili."""
    CACHE_ASIDE = "cache_aside"  # Manuale
    READ_THROUGH = "read_through"  # Lettura automatica
    WRITE_THROUGH = "write_through"  # Scrittura automatica
    WRITE_BEHIND = "write_behind"  # Scrittura async


@dataclass
class CacheConfig:
    """Configurazione cache."""
    default_ttl: int = 300  # 5 minuti
    max_key_length: int = 250
    prefix: str = "auto-broker"
    serializer: str = "json"  # json, pickle
    compression: bool = False
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 30


class CacheSerializer:
    """Serializer per dati cache."""
    
    @staticmethod
    def serialize(data: Any, method: str = "json") -> str:
        """Serializza dati."""
        if method == "json":
            return json.dumps(data, default=str)
        elif method == "pickle":
            return pickle.dumps(data).hex()
        else:
            raise ValueError(f"Unknown serializer: {method}")
    
    @staticmethod
    def deserialize(data: str, method: str = "json") -> Any:
        """Deserializza dati."""
        if method == "json":
            return json.loads(data)
        elif method == "pickle":
            return pickle.loads(bytes.fromhex(data))
        else:
            raise ValueError(f"Unknown serializer: {method}")


class CacheManager:
    """
    Manager per cache Redis con pattern Cache-Aside.
    Supporta circuit breaker per resilienza.
    """
    
    def __init__(self, redis_client=None, config: Optional[CacheConfig] = None):
        self.redis = redis_client
        self.config = config or CacheConfig()
        self.serializer = CacheSerializer()
        
        # Circuit breaker state
        self._failures = 0
        self._last_failure_time: Optional[datetime] = None
        self._circuit_open = False
        self._lock = asyncio.Lock()
    
    def _generate_key(self, key: str, prefix: Optional[str] = None) -> str:
        """Genera una chiave cache con prefisso."""
        prefix = prefix or self.config.prefix
        full_key = f"{prefix}:{key}"
        
        # Hash se troppo lunga
        if len(full_key) > self.config.max_key_length:
            hashed = hashlib.sha256(full_key.encode()).hexdigest()[:32]
            full_key = f"{prefix}:hash:{hashed}"
        
        return full_key
    
    def _is_circuit_open(self) -> bool:
        """Controlla se il circuit breaker è aperto."""
        if not self.config.circuit_breaker_enabled:
            return False
        
        if not self._circuit_open:
            return False
        
        # Controlla se possiamo provare di nuovo
        if self._last_failure_time:
            elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
            if elapsed > self.config.recovery_timeout:
                self._circuit_open = False
                self._failures = 0
                return False
        
        return True
    
    async def _record_failure(self):
        """Registra un fallimento."""
        async with self._lock:
            self._failures += 1
            self._last_failure_time = datetime.utcnow()
            
            if self._failures >= self.config.failure_threshold:
                self._circuit_open = True
                logger.warning("Cache circuit breaker OPENED")
    
    async def _record_success(self):
        """Registra un successo."""
        if self._failures > 0:
            async with self._lock:
                self._failures = max(0, self._failures - 1)
    
    async def get(
        self,
        key: str,
        prefix: Optional[str] = None
    ) -> Optional[Any]:
        """
        Recupera un valore dalla cache.
        Cache-Aside pattern: se miss, ritorna None.
        """
        if not self.redis or self._is_circuit_open():
            return None
        
        try:
            cache_key = self._generate_key(key, prefix)
            data = await self.redis.get(cache_key)
            
            if data is None:
                return None
            
            await self._record_success()
            return self.serializer.deserialize(data, self.config.serializer)
            
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            await self._record_failure()
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        prefix: Optional[str] = None
    ) -> bool:
        """
        Salva un valore in cache.
        """
        if not self.redis or self._is_circuit_open():
            return False
        
        try:
            cache_key = self._generate_key(key, prefix)
            ttl = ttl or self.config.default_ttl
            
            serialized = self.serializer.serialize(value, self.config.serializer)
            await self.redis.setex(cache_key, ttl, serialized)
            
            await self._record_success()
            return True
            
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            await self._record_failure()
            return False
    
    async def delete(self, key: str, prefix: Optional[str] = None) -> bool:
        """Elimina un valore dalla cache."""
        if not self.redis:
            return False
        
        try:
            cache_key = self._generate_key(key, prefix)
            await self.redis.delete(cache_key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    async def delete_pattern(self, pattern: str, prefix: Optional[str] = None) -> int:
        """Elimina chiavi che matchano un pattern."""
        if not self.redis:
            return 0
        
        try:
            search_pattern = f"{prefix or self.config.prefix}:{pattern}"
            keys = await self.redis.keys(search_pattern)
            
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete_pattern error: {e}")
            return 0
    
    async def exists(self, key: str, prefix: Optional[str] = None) -> bool:
        """Controlla se una chiave esiste."""
        if not self.redis:
            return False
        
        try:
            cache_key = self._generate_key(key, prefix)
            return await self.redis.exists(cache_key) > 0
        except Exception:
            return False
    
    async def ttl(self, key: str, prefix: Optional[str] = None) -> int:
        """Restituisce il TTL rimanente di una chiave."""
        if not self.redis:
            return -2
        
        try:
            cache_key = self._generate_key(key, prefix)
            return await self.redis.ttl(cache_key)
        except Exception:
            return -2
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
        prefix: Optional[str] = None
    ) -> Any:
        """
        Pattern Cache-Aside completo.
        Se cache miss, chiama factory e salva il risultato.
        """
        # Prova cache
        cached = await self.get(key, prefix)
        if cached is not None:
            return cached
        
        # Cache miss - genera valore
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        
        # Salva in cache
        await self.set(key, value, ttl, prefix)
        
        return value
    
    async def invalidate(
        self,
        tags: Optional[list] = None,
        key_patterns: Optional[list] = None
    ) -> int:
        """
        Invalidazione cache per tag o pattern.
        """
        if not self.redis:
            return 0
        
        deleted = 0
        
        try:
            # Invalida per tag
            if tags:
                for tag in tags:
                    tag_key = f"{self.config.prefix}:tag:{tag}"
                    keys = await self.redis.smembers(tag_key)
                    if keys:
                        deleted += await self.redis.delete(*keys)
                    await self.redis.delete(tag_key)
            
            # Invalida per pattern
            if key_patterns:
                for pattern in key_patterns:
                    deleted += await self.delete_pattern(pattern)
            
            return deleted
        except Exception as e:
            logger.warning(f"Cache invalidate error: {e}")
            return deleted
    
    async def add_to_tag(self, tag: str, key: str):
        """Aggiunge una chiave a un tag per invalidazione groupata."""
        if not self.redis:
            return
        
        try:
            tag_key = f"{self.config.prefix}:tag:{tag}"
            cache_key = self._generate_key(key)
            await self.redis.sadd(tag_key, cache_key)
        except Exception as e:
            logger.warning(f"Cache add_to_tag error: {e}")
    
    async def health_check(self) -> dict:
        """Controlla lo stato della cache."""
        if not self.redis:
            return {"status": "disabled", "healthy": False}
        
        try:
            await self.redis.ping()
            return {
                "status": "connected",
                "healthy": True,
                "circuit_open": self._circuit_open,
                "failures": self._failures
            }
        except Exception as e:
            return {
                "status": "error",
                "healthy": False,
                "error": str(e)
            }


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_generator: Optional[Callable] = None,
    cache_manager: Optional[CacheManager] = None
):
    """
    Decorator per caching di funzioni.
    
    Usage:
        @cached(ttl=600, key_prefix="user")
        async def get_user(user_id: int):
            return await db.get_user(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Ottieni cache manager
            cm = cache_manager or _global_cache_manager
            if not cm or not cm.redis:
                return await func(*args, **kwargs)
            
            # Genera chiave
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func, args, kwargs)
            
            full_prefix = f"{key_prefix}:{func.__name__}" if key_prefix else func.__name__
            
            # Prova cache
            cached_value = await cm.get(cache_key, prefix=full_prefix)
            if cached_value is not None:
                return cached_value
            
            # Esegui funzione
            result = await func(*args, **kwargs)
            
            # Salva in cache
            await cm.set(cache_key, result, ttl=ttl, prefix=full_prefix)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Per funzioni sync, esegui in asyncio
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def cache_invalidate(
    tags: Optional[list] = None,
    key_patterns: Optional[list] = None,
    cache_manager: Optional[CacheManager] = None
):
    """
    Decorator per invalidare cache dopo esecuzione.
    
    Usage:
        @cache_invalidate(tags=["users"])
        async def update_user(user_id: int, data: dict):
            return await db.update_user(user_id, data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)
            
            cm = cache_manager or _global_cache_manager
            if cm:
                await cm.invalidate(tags=tags, key_patterns=key_patterns)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            cm = cache_manager or _global_cache_manager
            if cm:
                asyncio.run(cm.invalidate(tags=tags, key_patterns=key_patterns))
            
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def _generate_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """Genera una chiave cache unica dalla firma della funzione."""
    key_parts = [func.__module__, func.__name__]
    
    # Serializza args
    for arg in args[1:] if len(args) > 0 and hasattr(args[0], '__class__') else args:
        key_parts.append(str(arg))
    
    # Serializza kwargs (ordinate)
    for k in sorted(kwargs.keys()):
        key_parts.append(f"{k}={kwargs[k]}")
    
    key_string = ":".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()[:32]


# Global cache manager instance
_global_cache_manager: Optional[CacheManager] = None


def init_cache_manager(redis_client=None, config: Optional[CacheConfig] = None):
    """Inizializza il cache manager globale."""
    global _global_cache_manager
    _global_cache_manager = CacheManager(redis_client, config)
    return _global_cache_manager


def get_cache_manager() -> Optional[CacheManager]:
    """Restituisce il cache manager globale."""
    return _global_cache_manager


# Esporta tutto
__all__ = [
    "CacheManager",
    "CacheConfig",
    "CacheStrategy",
    "CacheSerializer",
    "cached",
    "cache_invalidate",
    "init_cache_manager",
    "get_cache_manager",
]
