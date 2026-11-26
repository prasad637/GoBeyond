"""GO BEYOND — OTP Service with Redis Expiration & Attempt Throttling

Security Standards:
- OTPs expire strictly in 300 seconds (5 minutes).
- Failed attempt limiting: Maximum 3 attempts before the OTP is permanently invalidated.
- Development Sandbox mode: Clearly identified in response headers and bodies
  with a strict developer notice so sandbox behavior is never mistaken for production.
- Uses Redis 7 for distributed multi-worker consistency; falls back to thread-safe
  memory store only when Redis is unavailable during local tests.
"""
import os
import json
import time
import random
import threading
from typing import Dict, Any, Optional, Tuple
import redis
from app.core.config import settings

OTP_EXPIRY_SECONDS = 300  # 5 minutes
MAX_FAILED_ATTEMPTS = 3


class OTPService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
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

    def _cache_key(self, phone: str, purpose: str) -> str:
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        return f"gobeyond:otp:{clean_phone}:{purpose}"

    def _is_blocked(self, phone: str, purpose: str) -> bool:
        block_key = f"{self._cache_key(phone, purpose)}:blocked"
        client = self._get_client()
        if client:
            try:
                return bool(client.get(block_key))
            except Exception:
                self._mark_redis_down()
        if settings.ENVIRONMENT in ["production", "prod"]:
            return False
        with self._lock:
            blocked_until = self._memory_store.get(block_key, 0)
            if isinstance(blocked_until, (int, float)) and time.time() < blocked_until:
                return True
        return False

    def _set_blocked(self, phone: str, purpose: str, duration: int = 300):
        block_key = f"{self._cache_key(phone, purpose)}:blocked"
        client = self._get_client()
        if client:
            try:
                client.set(block_key, "1", ex=duration)
            except Exception:
                self._mark_redis_down()
        if settings.ENVIRONMENT in ["production", "prod"]:
            return
        with self._lock:
            self._memory_store[block_key] = time.time() + duration

    def send_otp(self, phone: str, purpose: str = "login") -> Dict[str, Any]:
        """
        Generates and stores an OTP with 300-second TTL.
        Returns a response containing the delivery confirmation and sandbox indicator.
        """
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        key = self._cache_key(clean_phone, purpose)
        block_key = f"{key}:blocked"
        client = self._get_client()

        # Clear any prior block when a fresh OTP is officially requested
        if client:
            try:
                client.delete(block_key)
            except Exception:
                self._mark_redis_down()
                client = None
        with self._lock:
            self._memory_store.pop(block_key, None)

        is_sandbox = getattr(settings, "OTP_SANDBOX_MODE", True)
        code = getattr(settings, "OTP_DEFAULT_DEV_CODE", "123456") if is_sandbox else f"{random.randint(100000, 999999):06d}"

        data = {
            "code": code,
            "attempts": 0,
            "created_at": time.time(),
            "expires_at": time.time() + OTP_EXPIRY_SECONDS
        }

        stored_in_redis = False
        if client:
            try:
                client.set(key, json.dumps(data), ex=OTP_EXPIRY_SECONDS)
                stored_in_redis = True
            except Exception:
                self._mark_redis_down()

        if not stored_in_redis:
            if settings.ENVIRONMENT in ["production", "prod"]:
                raise RuntimeError("Redis OTP service unavailable. In-memory fallback is strictly disabled in production.")
            with self._lock:
                self._memory_store[key] = data

        # Record durable outbox notification for OTP dispatch (mask raw OTP code in persisted DB outbox)
        try:
            from app.core.database import SessionLocal
            from app.services.notifications.service import NotificationService
            from app.services.notifications.providers import get_provider
            db = SessionLocal()
            try:
                NotificationService.create_outbox_notification(
                    db=db,
                    event_type="OTP_VERIFICATION",
                    channel="SMS",
                    recipient=clean_phone,
                    title="GO BEYOND Verification Code",
                    content="Your GO BEYOND verification code is ******. Valid for 5 minutes.",
                    payload={"purpose": purpose, "sandbox": is_sandbox},
                    idempotency_key=f"otp_{clean_phone}_{purpose}_{int(time.time() * 1000)}",
                    commit=True
                )
            finally:
                db.close()

            sms_provider_name = (getattr(settings, "SMS_PROVIDER", "mock") or "mock").strip().lower()
            if not is_sandbox and sms_provider_name != "mock":
                sms_provider = get_provider("SMS")
                sms_provider.send(
                    recipient=clean_phone,
                    title="GO BEYOND Verification Code",
                    content=f"Your GO BEYOND verification code is {code}. Valid for 5 minutes.",
                    payload={"purpose": purpose},
                )
        except Exception:
            pass

        result = {
            "message": f"OTP successfully dispatched to {clean_phone}.",
            "phone": clean_phone,
            "purpose": purpose,
            "expires_in_seconds": OTP_EXPIRY_SECONDS,
            "is_sandbox": is_sandbox
        }

        if is_sandbox:
            result["sandbox_code"] = code
            result["dev_notice"] = (
                "[DEVELOPMENT MODE] This OTP is generated for local testing. "
                "In production, SMS is dispatched via gateway and sandbox_code is omitted."
            )

        return result

    def verify_otp(self, phone: str, otp: str, purpose: str = "login") -> Tuple[bool, str]:
        """
        Verifies the provided OTP against the stored record.
        Enforces 300-second expiration and maximum 3 attempts.
        Returns (is_valid, message).
        """
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        if self._is_blocked(clean_phone, purpose):
            return False, "Too many failed attempts. This number is temporarily blocked. Please request a new code."

        key = self._cache_key(clean_phone, purpose)
        now = time.time()

        record = None
        client = self._get_client()
        if client:
            try:
                raw = client.get(key)
                if raw:
                    record = json.loads(raw)
            except Exception:
                self._mark_redis_down()
                client = None

        if not record:
            if settings.ENVIRONMENT in ["production", "prod"]:
                return False, "OTP has expired or does not exist. Please request a new one."
            with self._lock:
                record = self._memory_store.get(key)

        is_sandbox = getattr(settings, "OTP_SANDBOX_MODE", True)

        if not record:
            return False, "OTP has expired or does not exist. Please request a new one."

        # Check expiration
        if now > record.get("expires_at", 0):
            self.clear_otp(clean_phone, purpose)
            return False, "OTP has expired. Please request a new code."

        # Check attempt limit
        attempts = record.get("attempts", 0)
        if attempts >= MAX_FAILED_ATTEMPTS:
            self._set_blocked(clean_phone, purpose, duration=300)
            self.clear_otp(clean_phone, purpose)
            return False, "Too many failed attempts. This OTP has been invalidated for security. Please request a new code."

        expected_code = str(record.get("code", "")).strip()
        user_code = str(otp).strip()

        if user_code == expected_code or (is_sandbox and user_code == "123456"):
            self.clear_otp(clean_phone, purpose)
            return True, "Verification successful."

        # Incorrect OTP - increment attempts
        record["attempts"] = attempts + 1
        remaining = MAX_FAILED_ATTEMPTS - record["attempts"]

        if remaining <= 0:
            self._set_blocked(clean_phone, purpose, duration=300)
            self.clear_otp(clean_phone, purpose)
            return False, "Maximum attempt limit exceeded. OTP invalidated. Request a new code."

        client = self._get_client()
        if client:
            try:
                ttl = int(record["expires_at"] - now)
                if ttl > 0:
                    client.set(key, json.dumps(record), ex=ttl)
                else:
                    client.delete(key)
            except Exception:
                self._mark_redis_down()
        else:
            with self._lock:
                self._memory_store[key] = record

        return False, f"Incorrect OTP code. {remaining} attempt(s) remaining."

    def clear_otp(self, phone: str, purpose: str = "login"):
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        key = self._cache_key(clean_phone, purpose)
        client = self._get_client()
        if client:
            try:
                client.delete(key)
            except Exception:
                self._mark_redis_down()
        with self._lock:
            self._memory_store.pop(key, None)


otp_service = OTPService()

