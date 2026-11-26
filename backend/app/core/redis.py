import time
import threading
import redis
from typing import Optional
from app.core.config import settings

_redis_client: Optional[redis.Redis] = None
_redis_lock = threading.Lock()
_failure_until: float = 0.0
_FAILURE_COOLDOWN_SECONDS: float = 2.5


def get_redis() -> Optional[redis.Redis]:
    """
    Returns a connected Redis client instance or None if unavailable.
    Uses bounded socket timeouts and a brief cooldown after failures so Redis
    outages fail fast and recover automatically without process restart.
    """
    global _redis_client, _failure_until

    with _redis_lock:
        if _redis_client is not None:
            try:
                _redis_client.ping()
                return _redis_client
            except Exception:
                _redis_client = None
                _failure_until = time.monotonic() + _FAILURE_COOLDOWN_SECONDS
                return None

        if time.monotonic() < _failure_until:
            return None

        try:
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            client.ping()
            _redis_client = client
            _failure_until = 0.0
            return _redis_client
        except Exception:
            _redis_client = None
            _failure_until = time.monotonic() + _FAILURE_COOLDOWN_SECONDS
            return None

