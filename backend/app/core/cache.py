import json
import logging
from typing import Any, Optional
from datetime import datetime, date
from decimal import Decimal
from app.core.redis import get_redis

logger = logging.getLogger("gobeyond.cache")

# Strictly forbidden key prefixes - These can NEVER be cached as source of truth!
CRITICAL_INVENTORY_KEYWORDS = {"seat", "lock", "payment", "inventory", "reservation", "payable"}


def _serialize_helper(obj: Any) -> Any:
    """Helper to serialize datetime and Decimal objects for Redis JSON cache."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} is not serializable for cache")


class CacheService:
    """
    Production Redis caching service for public discovery and read-only catalog data.
    Guarantees that critical inventory and payment states are NEVER cached.
    """

    @staticmethod
    def _is_critical_inventory(key: str) -> bool:
        lower_key = key.lower()
        return any(kw in lower_key for kw in CRITICAL_INVENTORY_KEYWORDS)

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Retrieves cached JSON object or returns None on cache miss or Redis outage."""
        if cls._is_critical_inventory(key):
            logger.error(f"Attempted to access cache for critical inventory key '{key}'. Refusing cache access.")
            return None

        redis_client = get_redis()
        if redis_client is None:
            return None

        try:
            val = redis_client.get(f"gobeyond:cache:{key}")
            if val:
                return json.loads(val)
        except Exception as e:
            logger.warning(f"Cache get error for key '{key}': {str(e)}")
        return None

    @classmethod
    def set(cls, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Stores JSON-serializable value in cache with a TTL (default 5 mins)."""
        if cls._is_critical_inventory(key):
            logger.error(f"Refusing to cache critical inventory or financial state for key '{key}'.")
            return False

        redis_client = get_redis()
        if redis_client is None:
            return False

        try:
            serialized = json.dumps(value, default=_serialize_helper)
            redis_client.setex(f"gobeyond:cache:{key}", ttl_seconds, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key '{key}': {str(e)}")
            return False

    @classmethod
    def delete(cls, key: str) -> bool:
        """Invalidates a single cache key."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            redis_client.delete(f"gobeyond:cache:{key}")
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key '{key}': {str(e)}")
            return False

    @classmethod
    def invalidate_pattern(cls, pattern: str) -> int:
        """Invalidates all keys matching the specified pattern."""
        redis_client = get_redis()
        if redis_client is None:
            return 0
        try:
            full_pattern = f"gobeyond:cache:{pattern}*"
            keys = redis_client.keys(full_pattern)
            if keys:
                return redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Cache invalidate_pattern error for pattern '{pattern}': {str(e)}")
        return 0

    @classmethod
    def invalidate_discovery(cls) -> int:
        """Helper to clear public discovery and catalog caches on listing mutations."""
        return cls.invalidate_pattern("discovery:") + cls.invalidate_pattern("locations:")

