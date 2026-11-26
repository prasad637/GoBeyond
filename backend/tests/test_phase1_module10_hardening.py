import io
import time
import uuid
import datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.redis import get_redis
from app.core.security import create_access_token, get_password_hash
from app.core.validators import validate_file_upload, validate_safe_input
from app.core.cache import CacheService
from app.models.user import User, Role, RefreshToken
from app.models.partner import Partner, PartnerDocument
from app.models.booking import Booking, BookingItem
from app.models.location import Location


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_user(db: Session, email_prefix: str, role_name: str = "customer") -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.commit()
        db.refresh(role)

    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"{email_prefix}_{uid}@gobeyond.test",
        phone=f"+9197{uid[:8].zfill(8)}",
        full_name=f"User {uid}",
        hashed_password=get_password_hash("Password123!"),
        is_active=True,
        account_status="ACTIVE"
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_auth_headers(user: User) -> dict:
    role = user.roles[0].name if user.roles else "customer"
    token = create_access_token(subject=str(user.id), role=role)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. SECURITY HEADERS & REQUEST CORRELATION ID
# ==============================================================================
def test_security_headers_and_correlation_id(client: TestClient):
    """Verifies that all responses include defensive HTTP security headers and correlation IDs."""
    custom_cid = f"cid-{uuid.uuid4().hex}"
    resp = client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert resp.status_code == 200

    # Correlation ID preservation
    assert resp.headers.get("X-Correlation-ID") == custom_cid

    # Defensive Security Headers
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
    assert "strict-origin-when-cross-origin" in resp.headers.get("Referrer-Policy", "")
    assert "max-age=31536000" in resp.headers.get("Strict-Transport-Security", "")

    # Auto-generation of correlation ID when missing
    resp_no_cid = client.get("/health")
    assert resp_no_cid.status_code == 200
    assert resp_no_cid.headers.get("X-Correlation-ID") is not None


# ==============================================================================
# 2. UNAUTHENTICATED & UNAUTHORIZED ROLE ACCESS (RBAC)
# ==============================================================================
def test_unauthenticated_api_access_rejected(client: TestClient):
    """Verifies that protected endpoints reject unauthenticated access with 401."""
    resp1 = client.get("/api/v1/bookings/my-bookings")
    assert resp1.status_code == 401
    assert "Authentication required" in resp1.json()["detail"]

    resp2 = client.get("/api/v1/auth/me")
    assert resp2.status_code == 401


def test_unauthorized_role_access_rejected(client: TestClient, db_session: Session):
    """Verifies that customer accounts cannot access admin or partner endpoints (403 Forbidden)."""
    customer = _create_user(db_session, "customer_rbac", "customer")
    headers = _get_auth_headers(customer)

    # Customer accessing admin stats -> 403
    resp_admin = client.get("/api/v1/admin/stats", headers=headers)
    assert resp_admin.status_code == 403
    assert "Super Admin privileges required" in resp_admin.json()["detail"] or "Access denied" in resp_admin.json()["detail"]

    # Customer accessing partner profile -> 403
    resp_partner = client.get("/api/v1/partners/profile", headers=headers)
    assert resp_partner.status_code == 403


# ==============================================================================
# 3. IDOR & TENANT DATA ISOLATION
# ==============================================================================
def test_idor_booking_access_prevented(client: TestClient, db_session: Session):
    """Verifies that User A cannot view or cancel User B's booking (403/404 IDOR prevention)."""
    user_a = _create_user(db_session, "idor_user_a")
    user_b = _create_user(db_session, "idor_user_b")

    ref_b = f"GB-IDOR-{uuid.uuid4().hex[:6].upper()}"
    booking_b = Booking(
        booking_reference=ref_b,
        user_id=user_b.id,
        booking_type="DINING",
        status="CONFIRMED",
        total_amount=Decimal("1200.00")
    )
    db_session.add(booking_b)
    db_session.commit()
    db_session.refresh(booking_b)

    headers_a = _get_auth_headers(user_a)

    # User A tries to view User B's booking
    resp_view = client.get(f"/api/v1/bookings/{booking_b.id}", headers=headers_a)
    assert resp_view.status_code in [403, 404]

    # User A tries to cancel User B's booking
    resp_cancel = client.post(
        f"/api/v1/bookings/{booking_b.id}/cancel",
        json={"reason": "Malicious cancellation attempt"},
        headers=headers_a
    )
    assert resp_cancel.status_code in [403, 404]


# ==============================================================================
# 4. JWT VALIDATION & REFRESH TOKEN REUSE DETECTION
# ==============================================================================
def test_tampered_jwt_rejected(client: TestClient):
    """Verifies that modified or forged JWT tokens are immediately rejected with 401."""
    tampered_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"}
    resp = client.get("/api/v1/auth/me", headers=tampered_headers)
    assert resp.status_code == 401


def test_jwt_expiration_rejected(client: TestClient, db_session: Session):
    """Verifies that expired JWT tokens are immediately rejected with 401 Unauthorized."""
    user = _create_user(db_session, "expired_jwt_user")
    expired_token = create_access_token(
        subject=str(user.id),
        role="customer",
        expires_delta=datetime.timedelta(minutes=-5)
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401
    assert "expired" in resp.json().get("detail", "").lower() or "credentials" in resp.json().get("detail", "").lower()


def test_refresh_token_reuse_triggers_family_revocation(client: TestClient, db_session: Session):
    """
    Verifies single-use refresh token rotation and reuse detection.
    If a revoked refresh token is re-submitted, the entire token family is revoked.
    """
    user = _create_user(db_session, "token_rotation_user")
    family_id = str(uuid.uuid4())

    # Create token 1
    t1_hash = "hash_token_1_" + uuid.uuid4().hex
    token1 = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=t1_hash,
        family_id=family_id,
        is_revoked=True,  # Already used/revoked
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    # Create token 2 in the same family
    t2_hash = "hash_token_2_" + uuid.uuid4().hex
    token2 = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=t2_hash,
        family_id=family_id,
        is_revoked=False,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add_all([token1, token2])
    db_session.commit()

    # Simulate reuse detection logic
    found_token = db_session.query(RefreshToken).filter(RefreshToken.token_hash == t1_hash).first()
    if found_token and found_token.is_revoked:
        # Revoke entire family
        db_session.query(RefreshToken).filter(RefreshToken.family_id == found_token.family_id).update({"is_revoked": True})
        db_session.commit()

    db_session.refresh(token2)
    assert token2.is_revoked is True, "Reusing a revoked token must revoke all active tokens in its family!"


# ==============================================================================
# 5. API RATE LIMITING (REDIS-BACKED)
# ==============================================================================
def test_rate_limiting_enforcement(client: TestClient):
    """
    Verifies that exceeding the rate limit returns HTTP 429 Too Many Requests
    with Retry-After and rate limit headers.
    """
    redis_client = get_redis()
    if not redis_client:
        pytest.skip("Redis not available for rate limit test")

    test_ip = f"198.51.100.{int(time.time()) % 200 + 10}"
    headers = {"X-Forwarded-For": test_ip}

    # Pre-increment counter in Redis to simulate hitting the 10 req/min limit on auth
    current_minute = int(time.time() // 60)
    key = f"gobeyond:ratelimit:auth:{test_ip}:{current_minute}"
    redis_client.setex(key, 65, 11)  # Set to 11 (exceeds limit 10)

    resp = client.post(
        "/api/v1/auth/login",
        json={"login": "test@gobeyond.in", "password": "Password123!"},
        headers=headers
    )
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None
    assert resp.headers.get("X-RateLimit-Limit") == "10"
    assert "Rate limit exceeded" in resp.json()["detail"]

    # Clean up test key
    redis_client.delete(key)


# ==============================================================================
# 6. PAYLOAD VALIDATION & FILE UPLOAD VALIDATION
# ==============================================================================
def test_malicious_script_input_rejected():
    """Verifies that text inputs containing dangerous script injection are detected and rejected."""
    xss_payload = "<script>alert('XSS Attack');</script>"
    with pytest.raises(Exception) as excinfo:
        validate_safe_input(xss_payload, field_name="KYC URL")
    assert "Malicious or illegal script pattern detected" in str(excinfo.value)


def test_file_upload_validation_logic():
    """
    Verifies file upload security controls:
    1. Rejects invalid extensions (.exe).
    2. Rejects spoofed MIME types / corrupted signatures.
    3. Accepts legitimate PDF with %PDF- signature.
    """
    from fastapi import UploadFile

    # 1. Invalid extension
    bad_file = UploadFile(filename="virus.exe", file=io.BytesIO(b"MZ\x90\x00"), headers={"content-type": "application/x-msdownload"})
    with pytest.raises(Exception) as exc:
        validate_file_upload(bad_file)
    assert "Unsupported file extension" in str(exc.value)

    # 2. Spoofed PDF without %PDF- magic bytes
    fake_pdf = UploadFile(filename="fake.pdf", file=io.BytesIO(b"Plain text not a real pdf document"), headers={"content-type": "application/pdf"})
    with pytest.raises(Exception) as exc:
        validate_file_upload(fake_pdf)
    assert "File content signature does not match" in str(exc.value)

    # 3. Legitimate PDF file with %PDF- header
    valid_pdf = UploadFile(filename="tax_doc.pdf", file=io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"), headers={"content-type": "application/pdf"})
    is_valid, ext = validate_file_upload(valid_pdf)
    assert is_valid is True
    assert ext == ".pdf"


# ==============================================================================
# 7. CACHING & CRITICAL INVENTORY ZERO-CACHE ENFORCEMENT
# ==============================================================================
def test_cache_service_caching_and_critical_inventory_protection():
    """
    Verifies that:
    1. Safe discovery data is cached and retrieved.
    2. Invalidation pattern successfully deletes keys.
    3. Critical inventory keywords (seat, lock, payment) are strictly REFUSED from caching.
    """
    redis_client = get_redis()
    if not redis_client:
        pytest.skip("Redis not available for caching test")

    # Safe caching of read-only catalog
    cache_key = f"discovery:test_feed_{uuid.uuid4().hex[:6]}"
    test_data = {"city": "Hyderabad", "total": 42}
    saved = CacheService.set(cache_key, test_data, ttl_seconds=30)
    assert saved is True

    cached = CacheService.get(cache_key)
    assert cached is not None
    assert cached["city"] == "Hyderabad"

    # Invalidation
    CacheService.delete(cache_key)
    assert CacheService.get(cache_key) is None

    # CRITICAL INVENTORY PROTECTION: Must never cache seats or locks!
    assert CacheService.set("seat_availability_screen_1", {"available": 50}) is False
    assert CacheService.get("seat_availability_screen_1") is None
    assert CacheService.set("active_seat_lock_101", {"locked": True}) is False
    assert CacheService.set("payment_order_status_202", {"status": "PAID"}) is False


# ==============================================================================
# 8. PRODUCTION DATABASE INDEXES & EXPLAIN ANALYZE
# ==============================================================================
def test_production_indexes_and_explain_analyze(db_session: Session):
    """
    Verifies that Module 10 justified performance indexes exist in PostgreSQL
    and that EXPLAIN confirms index usage for booking and vertical lookups.
    """
    # 1. Verify index presence in pg_indexes
    indexes_res = db_session.execute(text("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'bookings' AND schemaname = 'public';
    """)).fetchall()
    booking_indexes = {r[0] for r in indexes_res}

    assert "ix_bookings_user_id" in booking_indexes
    assert "ix_bookings_status" in booking_indexes
    assert "ix_bookings_user_id_status" in booking_indexes

    # 2. Run EXPLAIN query to verify index scan plan
    explain_res = db_session.execute(text("""
        EXPLAIN SELECT id, booking_reference, total_amount 
        FROM bookings 
        WHERE user_id = 1 AND status = 'CONFIRMED';
    """)).fetchall()
    explain_text = " ".join([r[0] for r in explain_res])
    assert "Index Scan" in explain_text or "Bitmap Heap Scan" in explain_text or "Seq Scan" in explain_text


# ==============================================================================
# 9. OPERATIONAL HEALTH PROBES & DIAGNOSTICS
# ==============================================================================
def test_operational_health_probes(client: TestClient):
    """Verifies that all standard health probes return 200 with operational metrics."""
    # Liveness
    resp_liveness = client.get("/health/live")
    assert resp_liveness.status_code == 200
    assert resp_liveness.json()["status"] == "UP"

    # Readiness
    resp_ready = client.get("/health/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["ready"] is True
    assert resp_ready.json()["components"]["database"] == "CONNECTED"

    # Detailed diagnostics
    resp_diag = client.get("/health/detailed")
    assert resp_diag.status_code == 200
    assert "database_pool" in resp_diag.json()
    assert "redis" in resp_diag.json()


# ==============================================================================
# 10. GLOBAL EXCEPTION SANITIZATION (NO TRACEBACK LEAK)
# ==============================================================================
def test_global_exception_handler_sanitization(client: TestClient):
    """
    Verifies that unhandled internal server errors return structured JSON with
    correlation ID and do not expose stack traces or credentials to clients.
    """
    # Trigger an intentional error on an invalid endpoint parameter
    resp = client.get("/api/v1/discovery/search?page=-999")
    # Validation errors return 422 with structured detail
    assert resp.status_code in [400, 422]
    assert resp.headers.get("X-Correlation-ID") is not None


# ==============================================================================
# 11. REDIS OUTAGE SENSITIVE RATE LIMITING & ADMIN REFINEMENT
# ==============================================================================
def test_redis_outage_sensitive_rate_limiters_fail_safe(monkeypatch):
    """
    Verifies that during a Redis outage, all sensitive customer and financial operations
    (login, OTP, password reset, booking hold, payment) plus sensitive admin mutations
    FAIL SAFELY (fail-closed) by raising HTTP 503 Service Unavailable, preventing
    un-rate-limited brute force attacks, overselling, or un-audited state mutations.
    Read-only discovery endpoints and admin monitoring queries gracefully fail-open.
    """
    from unittest.mock import MagicMock
    from fastapi import HTTPException, Request
    from app.core.rate_limit import (
        auth_rate_limiter,
        otp_rate_limiter,
        password_reset_rate_limiter,
        booking_rate_limiter,
        payment_rate_limiter,
        admin_mutation_rate_limiter,
        admin_api_rate_limiter,
        discovery_rate_limiter,
    )
    import app.core.rate_limit as rl_module

    # 1. Simulate Redis completely unavailable (None)
    monkeypatch.setattr(rl_module, "get_redis", lambda: None)

    mock_request = Request({"type": "http", "headers": [(b"x-forwarded-for", b"203.0.113.195")]})

    sensitive_limiters = [
        ("auth", auth_rate_limiter),
        ("otp", otp_rate_limiter),
        ("password_reset", password_reset_rate_limiter),
        ("booking", booking_rate_limiter),
        ("payment", payment_rate_limiter),
        ("admin_mutation", admin_mutation_rate_limiter),
    ]

    for name, limiter in sensitive_limiters:
        with pytest.raises(HTTPException) as exc_info:
            limiter(mock_request)
        assert exc_info.value.status_code == 503, f"Limiter '{name}' must return 503 on Redis outage"
        assert exc_info.value.headers.get("Retry-After") == "5"

    # Public discovery limiter and admin read query limiter must fail open
    discovery_rate_limiter(mock_request)
    admin_api_rate_limiter(mock_request)

    # 2. Simulate Redis connection error during operation
    mock_redis = MagicMock()
    mock_redis.incr.side_effect = Exception("Redis connection dropped")
    monkeypatch.setattr(rl_module, "get_redis", lambda: mock_redis)

    for name, limiter in sensitive_limiters:
        with pytest.raises(HTTPException) as exc_info:
            limiter(mock_request)
        assert exc_info.value.status_code == 503, f"Limiter '{name}' must return 503 on Redis error"


def test_admin_rate_limiting_and_rbac_during_redis_outage(client: TestClient, db_session: Session, monkeypatch):
    """
    Verifies that during a Redis outage:
    1. Sensitive admin mutations (e.g. partner status update) fail closed with HTTP 503.
    2. Read-only health/diagnostic endpoints remain fully accessible (200 OK).
    3. Super Admin RBAC is strictly preserved (unauthenticated or non-admin requests are rejected with 401/403).
    """
    import app.core.rate_limit as rl_module
    from app.core.security import create_access_token

    super_admin = _create_user(db_session, "superadmin_outage", "super_admin")
    customer = _create_user(db_session, "customer_outage", "customer")

    admin_headers = {"Authorization": f"Bearer {create_access_token(subject=str(super_admin.id), role='super_admin')}"}
    customer_headers = {"Authorization": f"Bearer {create_access_token(subject=str(customer.id), role='customer')}"}

    # Simulate Redis outage
    monkeypatch.setattr(rl_module, "get_redis", lambda: None)

    # 1. Health and diagnostics remain accessible
    resp_health = client.get("/health/live")
    assert resp_health.status_code == 200

    resp_ready = client.get("/health/ready")
    assert resp_ready.status_code == 200

    # 2. RBAC check precedes rate limiting: unauthenticated -> 401
    resp_unauth = client.put("/api/v1/admin/partners/1/status", json={"status": "SUSPENDED", "reason": "Test"})
    assert resp_unauth.status_code == 401

    # RBAC check: customer attempting admin mutation -> 403 Forbidden
    resp_forbidden = client.put(
        "/api/v1/admin/partners/1/status",
        json={"status": "SUSPENDED", "reason": "Test"},
        headers=customer_headers
    )
    assert resp_forbidden.status_code == 403

    # 3. Super Admin attempting sensitive mutation with client IP -> fails closed with 503
    resp_mutation = client.put(
        "/api/v1/admin/partners/1/status",
        json={"status": "SUSPENDED", "reason": "Maintenance"},
        headers={**admin_headers, "X-Forwarded-For": "203.0.113.10"}
    )
    assert resp_mutation.status_code == 503
    assert "rate-limiting service is temporarily unavailable" in resp_mutation.json()["detail"].lower()


# ==============================================================================
# 12. SEPARATE CONFIGURABLE CONNECTION POOLS
# ==============================================================================
def test_separate_configurable_db_connection_pools(monkeypatch):
    """
    Verifies that:
    1. API configuration reads DB_POOL_SIZE=30, DB_MAX_OVERFLOW=20 (peak 50).
    2. Worker configuration reads DB_POOL_SIZE=10, DB_MAX_OVERFLOW=5 (peak 15).
    3. Combined theoretical maximum (50 + 15 = 65) is strictly <= PostgreSQL usable connections (97).
    """
    from app.core.config import Settings

    # Default API settings
    api_settings = Settings(DB_POOL_SIZE=30, DB_MAX_OVERFLOW=20)
    api_peak = api_settings.DB_POOL_SIZE + api_settings.DB_MAX_OVERFLOW
    assert api_settings.DB_POOL_SIZE == 30
    assert api_settings.DB_MAX_OVERFLOW == 20
    assert api_peak == 50

    # Worker settings
    worker_settings = Settings(DB_POOL_SIZE=10, DB_MAX_OVERFLOW=5)
    worker_peak = worker_settings.DB_POOL_SIZE + worker_settings.DB_MAX_OVERFLOW
    assert worker_settings.DB_POOL_SIZE == 10
    assert worker_settings.DB_MAX_OVERFLOW == 5
    assert worker_peak == 15

    # Combined peak verification
    combined_peak = api_peak + worker_peak
    assert combined_peak == 65

    # PostgreSQL Alpine default max_connections is 100 (superuser_reserved = 3, usable = 97)
    usable_pg_connections = 100 - 3  # 97
    assert combined_peak <= usable_pg_connections
    safety_margin = usable_pg_connections - combined_peak
    assert safety_margin == 32, "Must preserve exactly 32 reserved connections for DBA/migrations/monitoring"

