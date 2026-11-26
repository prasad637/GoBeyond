import os
import time
import threading
from typing import Optional, Dict, Tuple
from fastapi import HTTPException, status
import redis
from app.core.config import settings

# Atomic Compare-and-Delete Lua Script
# Guarantees that only the worker/process holding the exact lock_token can delete the key.
# Prevents race conditions where a delayed worker deletes a newer customer's lock.
LUA_RELEASE_LOCK = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class InMemoryLockManager:
    """
    Thread-safe in-memory lock manager used strictly for isolated local tests.
    Prohibited in production multi-replica environments.
    """
    def __init__(self):
        self._locks: Dict[str, Tuple[str, float]] = {}  # key -> (token, expire_timestamp)
        self._mutex = threading.Lock()

    def acquire(self, key: str, token: str, expiry_seconds: int = 600) -> bool:
        with self._mutex:
            now = time.time()
            if key in self._locks:
                current_token, expires_at = self._locks[key]
                if now >= expires_at:
                    del self._locks[key]
                else:
                    return False
            self._locks[key] = (token, now + expiry_seconds)
            return True

    def release(self, key: str, token: str) -> bool:
        with self._mutex:
            if key in self._locks:
                current_token, _ = self._locks[key]
                if current_token == token:
                    del self._locks[key]
                    return True
            return False

    def is_locked(self, key: str) -> bool:
        with self._mutex:
            now = time.time()
            if key in self._locks:
                _, expires_at = self._locks[key]
                if now < expires_at:
                    return True
                else:
                    del self._locks[key]
            return False

    def get_all_locked(self, prefix: str = "") -> list:
        with self._mutex:
            now = time.time()
            active = []
            for k, (t, exp) in list(self._locks.items()):
                if now < exp:
                    if not prefix or k.startswith(prefix):
                        active.append(k)
                else:
                    del self._locks[k]
            return active


class LockService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_manager = InMemoryLockManager()
        self._reconnect_lock = threading.Lock()
        self._needs_reconnect: bool = False
        self._reconnect_after: float = 0.0
        self._reconnect_cooldown: float = 2.5
        self._init_redis()

    def _init_redis(self):
        try:
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.5,
                socket_timeout=1.5,
            )
            client.ping()
            self.redis_client = client
            self._needs_reconnect = False
            self._reconnect_after = 0.0
        except Exception:
            self.redis_client = None
            self._needs_reconnect = True
            self._reconnect_after = time.monotonic() + self._reconnect_cooldown

    def _mark_redis_down(self):
        self.redis_client = None
        self._needs_reconnect = True
        self._reconnect_after = time.monotonic() + self._reconnect_cooldown

    def _get_client(self) -> Optional[redis.Redis]:
        if self.redis_client is not None:
            return self.redis_client
        if self._needs_reconnect and time.monotonic() >= self._reconnect_after:
            with self._reconnect_lock:
                if self.redis_client is None and self._needs_reconnect and time.monotonic() >= self._reconnect_after:
                    self._init_redis()
        return self.redis_client

    def _is_test_env(self) -> bool:
        """
        Determines if the runtime is an isolated local in-memory test runner.
        Strictly prohibited when ENVIRONMENT is 'production' or 'integration_test',
        or when USE_MEMORY_LOCK_FALLBACK is explicitly False.
        """
        if settings.ENVIRONMENT in ("production", "integration_test") or not settings.USE_MEMORY_LOCK_FALLBACK:
            return False
        return (
            settings.ENVIRONMENT == "test"
            or "PYTEST_CURRENT_TEST" in os.environ
        ) and settings.USE_MEMORY_LOCK_FALLBACK

    def acquire_lock(self, key: str, token: str, expiry_seconds: Optional[int] = None) -> bool:
        """
        Acquires a temporary lock atomically.
        If Redis is down in production/development, fails safely with HTTP 503
        rather than allowing uncoordinated bookings across app instances.
        """
        ttl = expiry_seconds or settings.LOCK_EXPIRY_SECONDS
        client = self._get_client()

        if client:
            try:
                redis_key = f"gobeyond:lock:{key}"
                result = client.set(redis_key, token, nx=True, ex=ttl)
                return bool(result)
            except Exception:
                # Redis connection failed during call; mark for automatic reconnect
                self._mark_redis_down()

        # Fail-Safe check
        if self._is_test_env():
            return self.memory_manager.acquire(key, token, ttl)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory lock service is temporarily unavailable. Please try again shortly."
        )

    def release_lock(self, key: str, token: str) -> bool:
        """
        Releases a temporary lock using atomic Lua compare-and-delete.
        Verifies ownership: only deletes if the key still holds this exact token.
        """
        if not token:
            raise ValueError("lock_token is required to release an inventory lock.")

        client = self._get_client()
        if client:
            try:
                redis_key = f"gobeyond:lock:{key}"
                res = client.eval(LUA_RELEASE_LOCK, 1, redis_key, token)
                return bool(res == 1)
            except Exception:
                self._mark_redis_down()

        if self._is_test_env():
            return self.memory_manager.release(key, token)

        return False

    def is_locked(self, key: str) -> bool:
        client = self._get_client()
        if client:
            try:
                return bool(client.exists(f"gobeyond:lock:{key}"))
            except Exception:
                self._mark_redis_down()

        if self._is_test_env():
            return self.memory_manager.is_locked(key)

        return False

    def get_locked_keys(self, prefix: str = "") -> list:
        client = self._get_client()
        if client:
            try:
                pattern = f"gobeyond:lock:{prefix}*"
                return [k.replace("gobeyond:lock:", "") for k in client.keys(pattern)]
            except Exception:
                self._mark_redis_down()

        if self._is_test_env():
            return self.memory_manager.get_all_locked(prefix)

        return []


lock_service = LockService()
