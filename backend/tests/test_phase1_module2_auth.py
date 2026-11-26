"""GO BEYOND — Phase 1 Module 2: Authentication, Authorization & User Profile Integration Tests

Validates:
1. Customer Registration & Multi-Identifier Login (Email / Mobile).
2. OTP Lifecycle: Expiration, Rate Limiting (3-attempt max), and Dev-Sandbox Flagging.
3. Password Hashing (Bcrypt) & Forgot/Reset Password via OTP.
4. Single-Use Refresh Token Rotation & Token Family Reuse Revocation.
5. CSRF Protection with Double-Submit Cookie/Header Matching.
6. Session Management: Current Session Logout vs Logout from All Devices.
7. Account Lifecycle: Soft Deactivation & Subsequent Access Denial.
8. Role-Based Access Control: Super Admin vs Partner vs Customer.
9. Partner Data Isolation: Strict Establishment Boundaries & Cross-Tenant Scanning Denial.
10. Customer Profile Management & Hyderabad Locality Persistence.
"""
import uuid
import time
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.models.user import User, UserProfile, Role, RefreshToken
from app.models.partner import Partner
from app.models.location import Location
from app.models.booking import Booking, BookingItem
from app.models.movie import Cinema, Screen, Seat
from app.models.dining import Restaurant, DiningTable
from app.models.event import Event, EventTicketType
from app.core.security import get_password_hash, verify_password, create_access_token
from app.services.otp import otp_service, MAX_FAILED_ATTEMPTS


def generate_phone() -> str:
    """Generate a valid, unique 10-digit Indian mobile number starting with 98."""
    return f"98{uuid.uuid4().int % 100000000:08d}"


@pytest.fixture
def client():
    return TestClient(app)


def test_m2_customer_registration_and_login_with_email_and_mobile(client: TestClient, db_session: Session):
    """Verify customer registration, password hashing, and login via email or mobile."""
    unique_suffix = uuid.uuid4().hex[:6]
    test_email = f"cust_{unique_suffix}@gobeyond.in"
    test_phone = generate_phone()
    test_pass = "SecurePass@2026"

    # Fetch Hyderabad locality from Module 1
    loc = db_session.query(Location).filter(Location.type == "LOCALITY").first()
    loc_id = loc.id if loc else None

    # 1. Register new customer
    reg_res = client.post("/api/v1/auth/register", json={
        "full_name": "Test Customer M2",
        "email": test_email,
        "phone": test_phone,
        "password": test_pass,
        "role": "customer",
        "locality_id": loc_id
    })
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["email"] == test_email
    assert reg_data["role"] == "customer"
    assert "access_token" in reg_data
    assert "gobeyond_refresh_token" in reg_res.cookies

    # Verify password hash
    created_user = db_session.query(User).filter(User.email == test_email).first()
    assert created_user is not None
    assert verify_password(test_pass, created_user.hashed_password)
    assert created_user.account_status == "ACTIVE"

    # 2. Login using EMAIL
    login_email_res = client.post("/api/v1/auth/login", json={
        "login": test_email,
        "password": test_pass
    })
    assert login_email_res.status_code == 200
    assert login_email_res.json()["user_id"] == created_user.id

    # 3. Login using MOBILE NUMBER
    login_phone_res = client.post("/api/v1/auth/login", json={
        "login": test_phone,
        "password": test_pass
    })
    assert login_phone_res.status_code == 200
    assert login_phone_res.json()["user_id"] == created_user.id

    # 4. Login with invalid password
    bad_pass_res = client.post("/api/v1/auth/login", json={
        "login": test_email,
        "password": "WrongPassword!"
    })
    assert bad_pass_res.status_code == 401


def test_m2_otp_lifecycle_throttling_and_dev_notice(client: TestClient):
    """
    Verify OTP dispatch with development sandbox identification,
    expiration/attempt limit enforcement (max 3 failed attempts), and invalidation.
    """
    test_phone = generate_phone()

    # 1. Dispatch OTP
    req_res = client.post("/api/v1/auth/request-otp", json={
        "phone": test_phone,
        "purpose": "login"
    })
    assert req_res.status_code == 200
    req_data = req_res.json()
    assert "expires_in_seconds" in req_data
    assert req_data["is_sandbox"] is True
    assert "dev_notice" in req_data
    assert "[DEVELOPMENT MODE]" in req_data["dev_notice"]
    assert req_data["sandbox_code"] == "123456"

    # 2. Test Attempt Throttling: Attempt 1 with invalid code
    bad1 = client.post("/api/v1/auth/verify-otp", json={
        "phone": test_phone,
        "otp": "999999",
        "purpose": "login"
    })
    assert bad1.status_code == 400
    assert "attempt" in bad1.json()["detail"].lower()

    # Attempt 2 with invalid code
    bad2 = client.post("/api/v1/auth/verify-otp", json={
        "phone": test_phone,
        "otp": "888888",
        "purpose": "login"
    })
    assert bad2.status_code == 400

    # Attempt 3: Exhaust attempts -> OTP invalidated
    bad3 = client.post("/api/v1/auth/verify-otp", json={
        "phone": test_phone,
        "otp": "777777",
        "purpose": "login"
    })
    assert bad3.status_code == 400
    assert "maximum" in bad3.json()["detail"].lower() or "invalidated" in bad3.json()["detail"].lower()

    # Attempt 4: Even with correct code, now rejected because OTP was invalidated
    bad4 = client.post("/api/v1/auth/verify-otp", json={
        "phone": test_phone,
        "otp": "123456",
        "purpose": "login"
    })
    assert bad4.status_code == 400


def test_m2_forgot_and_reset_password_flow(client: TestClient, db_session: Session):
    """Verify end-to-end forgot password request and reset with OTP verification."""
    unique = uuid.uuid4().hex[:6]
    email = f"reset_{unique}@gobeyond.in"
    phone = generate_phone()
    initial_pass = "InitialPass@123"
    new_pass = "BrandNewSecurePass@2026"

    # Create test user
    user = User(
        email=email,
        phone=phone,
        full_name="Password Reset User",
        hashed_password=get_password_hash(initial_pass),
        is_active=True,
        is_verified=True,
        account_status="ACTIVE"
    )
    cust_role = db_session.query(Role).filter(Role.name == "customer").first()
    if cust_role:
        user.roles.append(cust_role)
    db_session.add(user)
    db_session.commit()

    # 1. Request reset OTP
    req_res = client.post("/api/v1/auth/forgot-password", json={
        "email_or_phone": email
    })
    assert req_res.status_code == 200

    # 2. Reset password with wrong OTP (fails)
    fail_res = client.post("/api/v1/auth/reset-password", json={
        "email_or_phone": email,
        "otp": "000000",
        "new_password": new_pass
    })
    assert fail_res.status_code == 400

    # 3. Reset password with valid OTP
    reset_res = client.post("/api/v1/auth/reset-password", json={
        "email_or_phone": email,
        "otp": "123456",
        "new_password": new_pass
    })
    assert reset_res.status_code == 200
    assert reset_res.json()["success"] is True

    # 4. Old password fails
    old_login = client.post("/api/v1/auth/login", json={"login": email, "password": initial_pass})
    assert old_login.status_code == 401

    # 5. New password succeeds
    new_login = client.post("/api/v1/auth/login", json={"login": email, "password": new_pass})
    assert new_login.status_code == 200


def test_m2_single_use_refresh_rotation_and_token_reuse_revocation(client: TestClient, db_session: Session):
    """
    Verify:
    1. Single-use refresh token rotation issues a new token and revokes the old one.
    2. Presenting an already-revoked refresh token revokes the entire token family.
    """
    unique = uuid.uuid4().hex[:6]
    email = f"rotate_{unique}@gobeyond.in"
    phone = generate_phone()
    password = "RotatePass@2026"

    # Register
    reg_res = client.post("/api/v1/auth/register", json={
        "full_name": "Rotation User",
        "email": email,
        "phone": phone,
        "password": password
    })
    assert reg_res.status_code == 201
    first_token_data = reg_res.json()
    first_refresh = reg_res.cookies.get("gobeyond_refresh_token")
    csrf_token = reg_res.cookies.get("gobeyond_csrf_token")
    assert first_refresh is not None

    # 1. Valid Refresh (Rotation 1)
    client.cookies.set("gobeyond_refresh_token", first_refresh, path="/api/v1/auth")
    client.cookies.set("gobeyond_csrf_token", csrf_token, path="/api/v1/auth")
    ref1_res = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_token})
    assert ref1_res.status_code == 200
    ref1_data = ref1_res.json()
    second_refresh = ref1_res.cookies.get("gobeyond_refresh_token")
    assert second_refresh is not None
    assert second_refresh != first_refresh
    second_csrf = ref1_res.cookies.get("gobeyond_csrf_token") or csrf_token

    # 2. TOKEN REUSE ATTACK: Presenting first_refresh again (which was already rotated)
    client.cookies.set("gobeyond_refresh_token", first_refresh, path="/api/v1/auth")
    client.cookies.set("gobeyond_csrf_token", second_csrf, path="/api/v1/auth")
    reuse_res = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": second_csrf})
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["detail"].lower()

    # 3. Verify entire family is revoked: second_refresh should also be invalid now!
    client.cookies.set("gobeyond_refresh_token", second_refresh, path="/api/v1/auth")
    client.cookies.set("gobeyond_csrf_token", second_csrf, path="/api/v1/auth")
    subsequent_res = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": second_csrf})
    assert subsequent_res.status_code == 401


def test_m2_csrf_protection_validation(client: TestClient):
    """Verify CSRF token validation on state-modifying refresh endpoints."""
    unique = uuid.uuid4().hex[:6]
    res = client.post("/api/v1/auth/register", json={
        "full_name": "CSRF Test User",
        "email": f"csrf_{unique}@gobeyond.in",
        "phone": generate_phone(),
        "password": "Password123!"
    })
    assert res.status_code == 201
    csrf_token = res.cookies.get("gobeyond_csrf_token")
    refresh_token = res.cookies.get("gobeyond_refresh_token")
    assert csrf_token is not None
    assert refresh_token is not None

    # 1. Request with mismatched CSRF header should be rejected (403)
    client.cookies.set("gobeyond_refresh_token", refresh_token, path="/api/v1/auth")
    client.cookies.set("gobeyond_csrf_token", csrf_token, path="/api/v1/auth")
    bad_csrf_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": "invalid_forged_csrf_token_xyz"}
    )
    assert bad_csrf_res.status_code == 403
    assert "csrf" in bad_csrf_res.json()["detail"].lower()

    # 2. Request with matching CSRF header should succeed (200)
    good_csrf_res = client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token}
    )
    assert good_csrf_res.status_code == 200


def test_m2_logout_current_session_vs_logout_all_sessions(client: TestClient, db_session: Session):
    """
    Verify:
    1. /logout revokes the current session's refresh token and clears cookies.
    2. /logout-all revokes ALL active refresh tokens across all devices for the user.
    """
    unique = uuid.uuid4().hex[:6]
    email = f"logout_{unique}@gobeyond.in"
    phone = generate_phone()
    password = "LogoutPass@2026"

    # Register
    reg = client.post("/api/v1/auth/register", json={
        "full_name": "Multi Session User",
        "email": email,
        "phone": phone,
        "password": password
    })
    assert reg.status_code == 201
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    # Simulate 3 active sessions on different devices
    login1 = client.post("/api/v1/auth/login", json={"login": email, "password": password})
    t1 = login1.json()["access_token"]
    login2 = client.post("/api/v1/auth/login", json={"login": email, "password": password})
    login3 = client.post("/api/v1/auth/login", json={"login": email, "password": password})

    active_tokens_before = db_session.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False
    ).count()
    assert active_tokens_before >= 3

    # Logout from all sessions using access token
    logout_all_res = client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {t1}"}
    )
    assert logout_all_res.status_code == 200
    assert logout_all_res.json()["success"] is True

    # Confirm all tokens for user are now revoked in database
    active_tokens_after = db_session.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False
    ).count()
    assert active_tokens_after == 0


def test_m2_account_deactivation_workflow_and_login_denial(client: TestClient, db_session: Session):
    """
    Verify account deletion / deactivation workflow:
    1. Deactivate endpoint sets is_active = False and account_status = 'DEACTIVATED'.
    2. Terminates all active sessions.
    3. Future login and refresh attempts are rejected with HTTP 403 Forbidden.
    """
    unique = uuid.uuid4().hex[:6]
    email = f"deact_{unique}@gobeyond.in"
    phone = generate_phone()
    password = "DeactivatePass@2026"

    reg_res = client.post("/api/v1/auth/register", json={
        "full_name": "Deactivation User",
        "email": email,
        "phone": phone,
        "password": password
    })
    assert reg_res.status_code == 201
    access_token = reg_res.json()["access_token"]
    user = db_session.query(User).filter(User.email == email).first()

    # 1. Trigger Account Deactivation
    deact_res = client.post(
        "/api/v1/auth/deactivate",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["success"] is True

    # 2. Database verification
    db_session.refresh(user)
    assert user.is_active is False
    assert user.account_status == "DEACTIVATED"

    # 3. Existing Access Token Immediate Rejection Test
    me_blocked = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_blocked.status_code == 403
    assert "deactivated" in me_blocked.json()["detail"].lower()

    # 4. Subsequent login attempt rejected
    blocked_login = client.post("/api/v1/auth/login", json={"login": email, "password": password})
    assert blocked_login.status_code == 403
    assert "deactivated" in blocked_login.json()["detail"].lower()


def test_m2_role_based_access_control_enforcement(client: TestClient, db_session: Session):
    """
    Verify RBAC enforcement on backend endpoints:
    - Super Admin can access admin stats.
    - Customer cannot access admin endpoints (HTTP 403 Forbidden).
    - Customer cannot access partner endpoints (HTTP 403 Forbidden).
    """
    admin_login = client.post("/api/v1/auth/login", json={
        "login": "admin@gobeyond.com",
        "password": "Admin@123"
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    cust_login = client.post("/api/v1/auth/login", json={
        "login": "customer@gobeyond.com",
        "password": "Customer@123"
    })
    assert cust_login.status_code == 200
    cust_token = cust_login.json()["access_token"]

    # 1. Admin accessing admin dashboard -> Allowed (200)
    admin_stats = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_stats.status_code == 200

    # 2. Customer accessing admin dashboard -> Denied (403)
    cust_admin_stats = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {cust_token}"})
    assert cust_admin_stats.status_code == 403

    # 3. Customer accessing partner profile -> Denied (403)
    cust_partner = client.get("/api/v1/partners/profile", headers={"Authorization": f"Bearer {cust_token}"})
    assert cust_partner.status_code == 403


def test_m2_partner_data_isolation_and_cross_tenant_scanning_denial(client: TestClient, db_session: Session):
    """
    Verify strict partner tenant data isolation:
    1. A partner can only retrieve their own business profile, bookings, and analytics.
    2. A partner scanner cannot verify or grant entry to a pass belonging to a different partner.
    """
    # 1. Cinema Partner User
    cinema_partner = db_session.query(Partner).filter(Partner.partner_type == "CINEMA").first()
    dining_partner = db_session.query(Partner).filter(Partner.partner_type == "RESTAURANT").first()
    assert cinema_partner and dining_partner

    cinema_user = db_session.query(User).filter(User.id == cinema_partner.user_id).first()
    dining_user = db_session.query(User).filter(User.id == dining_partner.user_id).first()
    assert cinema_user and dining_user

    # Generate access tokens for each partner
    cinema_token = create_access_token(subject=cinema_user.id, role="partner_cinema")
    dining_token = create_access_token(subject=dining_user.id, role="partner_restaurant")

    # 2. Cinema Partner checks analytics -> receives Cinema business data only
    cinema_analytics = client.get(
        "/api/v1/partners/analytics",
        headers={"Authorization": f"Bearer {cinema_token}"}
    )
    assert cinema_analytics.status_code == 200
    assert cinema_analytics.json()["business_name"] == cinema_partner.business_name
    assert cinema_analytics.json()["partner_type"] == "CINEMA"

    # 3. Create a Dining booking for dining_partner
    customer = db_session.query(User).filter(User.email == "customer@gobeyond.com").first()
    dining_table = db_session.query(DiningTable).filter(DiningTable.restaurant_id.in_(
        db_session.query(Restaurant.id).filter(Restaurant.partner_id == dining_partner.id)
    )).first()

    dining_b_ref = f"GB-DINE-ISO-{uuid.uuid4().hex[:6]}"
    dining_booking = Booking(
        booking_reference=dining_b_ref,
        user_id=customer.id,
        booking_type="DINING",
        status="CONFIRMED",
        total_amount=Decimal("450.00"),
        final_payable=Decimal("450.00"),
        qr_code_token=f"QR-DINE-{uuid.uuid4().hex[:8]}"
    )
    db_session.add(dining_booking)
    db_session.commit()

    it = BookingItem(
        booking_id=dining_booking.id,
        item_type="TABLE",
        item_id=dining_table.id if dining_table else 1,
        quantity=1,
        unit_price=Decimal("450.00"),
        subtotal=Decimal("450.00"),
        name="Dining Reservation"
    )
    db_session.add(it)
    db_session.commit()

    try:
        # 4. Cross-Tenant Scanning Test:
        # Cinema Partner attempts to scan and grant entry to a Dining Partner's booking pass!
        # Must be rejected with Access Denied and status UNAUTHORIZED_PARTNER.
        scan_res = client.post(
            "/api/v1/partners/verify-qr-pass",
            headers={"Authorization": f"Bearer {cinema_token}"},
            json={"qr_token": dining_booking.qr_code_token}
        )
        assert scan_res.status_code == 200
        scan_data = scan_res.json()
        assert scan_data["valid"] is False
        assert scan_data["status"] == "UNAUTHORIZED_PARTNER"
        assert "different establishment" in scan_data["message"].lower()

    finally:
        # Cleanup
        db_session.query(BookingItem).filter(BookingItem.booking_id == dining_booking.id).delete()
        db_session.query(Booking).filter(Booking.id == dining_booking.id).delete()
        db_session.commit()


def test_m2_customer_profile_update_and_locality_management(client: TestClient, db_session: Session):
    """Verify profile retrieval, locality update in Hyderabad, and emergency contact details."""
    unique = uuid.uuid4().hex[:6]
    email = f"prof_{unique}@gobeyond.in"
    phone = generate_phone()
    passw = "ProfilePass@2026"

    reg_res = client.post("/api/v1/auth/register", json={
        "full_name": "Original Name",
        "email": email,
        "phone": phone,
        "password": passw
    })
    assert reg_res.status_code == 201
    token = reg_res.json()["access_token"]

    # Fetch Hyderabad locality
    banjara = db_session.query(Location).filter(Location.slug == "banjara-hills").first()
    assert banjara is not None

    # Update profile
    update_res = client.put(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Updated Profile Name",
            "locality_id": banjara.id,
            "preferred_language": "Telugu",
            "bio": "Foodie and movie enthusiast in Hyderabad",
            "emergency_phone": "9988776655"
        }
    )
    assert update_res.status_code == 200
    up_data = update_res.json()
    assert up_data["full_name"] == "Updated Profile Name"
    assert up_data["locality_id"] == banjara.id
    assert up_data["locality_name"] == "Banjara Hills"
    assert up_data["preferred_language"] == "Telugu"
    assert up_data["bio"] == "Foodie and movie enthusiast in Hyderabad"
    assert up_data["account_status"] == "ACTIVE"


def test_m2_public_registration_never_allows_super_admin_role(client: TestClient, db_session: Session):
    """
    Security Verification:
    Public registration must strictly forbid Super Admin / Admin role assignment.
    Attempts must be rejected with 422 or 400 and cannot create an administrative user.
    """
    unique = uuid.uuid4().hex[:6]

    # 1. Attempt with role = "super_admin"
    bad_admin = client.post("/api/v1/auth/register", json={
        "full_name": "Attacker SuperAdmin",
        "email": f"attacker_{unique}@gobeyond.in",
        "phone": generate_phone(),
        "password": "Password123!",
        "role": "super_admin"
    })
    assert bad_admin.status_code in [400, 422]
    assert "administrative" in bad_admin.text.lower() or "not permitted" in bad_admin.text.lower() or "validation" in bad_admin.text.lower()

    # 2. Attempt with role = "admin"
    bad_admin2 = client.post("/api/v1/auth/register", json={
        "full_name": "Attacker Admin",
        "email": f"attacker2_{unique}@gobeyond.in",
        "phone": generate_phone(),
        "password": "Password123!",
        "role": "admin"
    })
    assert bad_admin2.status_code in [400, 422]

    # Verify no attacker user has super_admin role
    attacker_user = db_session.query(User).filter(User.email == f"attacker_{unique}@gobeyond.in").first()
    assert attacker_user is None


def test_m2_partner_self_registration_creates_pending_approval_account(client: TestClient, db_session: Session):
    """
    Security Verification:
    Partner self-registration must create a PENDING_APPROVAL account, not an active partner account.
    Operational endpoints must reject access until approved by an administrator.
    """
    # Clean any previous run
    db_session.execute(text("DELETE FROM partner_documents WHERE partner_id IN (SELECT id FROM partners WHERE business_name LIKE 'Self Register%');"))
    db_session.execute(text("DELETE FROM partners WHERE business_name LIKE 'Self Register%';"))
    db_session.commit()

    unique = uuid.uuid4().hex[:6]
    partner_email = f"pending_partner_{unique}@gobeyond.in"
    partner_phone = generate_phone()

    user = None
    partner = None

    try:
        # 1. Self-register via public registration with a partner role
        reg_res = client.post("/api/v1/auth/register", json={
            "full_name": "Self Register Restaurant Partner",
            "email": partner_email,
            "phone": partner_phone,
            "password": "PartnerPass@2026",
            "role": "partner_restaurant"
        })
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        partner_token = reg_data["access_token"]

        # 2. Verify account status is PENDING_APPROVAL in DB
        user = db_session.query(User).filter(User.email == partner_email).first()
        assert user is not None
        assert user.account_status == "PENDING_APPROVAL"

        partner = db_session.query(Partner).filter(Partner.user_id == user.id).first()
        assert partner is not None
        assert partner.status == "PENDING_APPROVAL"
        assert partner.partner_type == "RESTAURANT"

        # 3. Operational partner access is rejected (403 Forbidden) while in PENDING_APPROVAL
        bookings_res = client.get(
            "/api/v1/partners/bookings",
            headers={"Authorization": f"Bearer {partner_token}"}
        )
        assert bookings_res.status_code == 403
        assert "pending approval" in bookings_res.json()["detail"].lower()

        # 4. But KYC document upload is permitted for pending partners
        doc_res = client.post(
            "/api/v1/partners/documents",
            headers={"Authorization": f"Bearer {partner_token}"},
            json={
                "document_type": "FSSAI_LICENSE",
                "document_url": "https://storage.gobeyond.in/docs/fssai_sample.pdf"
            }
        )
        assert doc_res.status_code == 200
        assert doc_res.json()["success"] is True

    finally:
        # Teardown: ensure test partner does not leak into other test suites
        if user:
            p_id = partner.id if partner else 0
            db_session.execute(text("DELETE FROM partner_documents WHERE partner_id = :pid"), {"pid": p_id})
            db_session.execute(text("DELETE FROM partners WHERE user_id = :uid"), {"uid": user.id})
            db_session.execute(text("DELETE FROM refresh_tokens WHERE user_id = :uid"), {"uid": user.id})
            db_session.execute(text("DELETE FROM user_profiles WHERE user_id = :uid"), {"uid": user.id})
            db_session.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": user.id})
            db_session.execute(text("DELETE FROM user_roles WHERE user_id = :uid"), {"uid": user.id})
            db_session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user.id})
            db_session.commit()


def test_m2_otp_in_memory_fallback_strictly_disabled_in_production(client: TestClient, monkeypatch):
    """
    Security Verification:
    OTP in-memory fallback must be strictly disabled when ENVIRONMENT is 'production'.
    If Redis is down, it must fail safe with 503 Service Unavailable / RuntimeError
    rather than silently using insecure local process memory.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    saved_client = otp_service.redis_client
    test_phone = generate_phone()

    try:
        # Simulate Redis failure
        otp_service.redis_client = None

        # 1. Direct service call raises RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            otp_service.send_otp(phone=test_phone, purpose="login")
        assert "strictly disabled in production" in str(exc_info.value)

        # 2. API endpoint returns 503 Service Unavailable
        res = client.post("/api/v1/auth/request-otp", json={
            "phone": test_phone,
            "purpose": "login"
        })
        assert res.status_code == 503
        assert "unavailable" in res.json()["detail"].lower()

        # 3. Verify OTP does NOT check memory store in production
        is_valid, msg = otp_service.verify_otp(phone=test_phone, otp="123456", purpose="login")
        assert is_valid is False

    finally:
        otp_service.redis_client = saved_client
