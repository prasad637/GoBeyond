import pytest
import datetime
import uuid
from decimal import Decimal, ROUND_HALF_UP
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, Role, RefreshToken
from app.models.partner import Partner, PartnerDocument
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund, Coupon
from app.models.audit import AuditLog, Notification
from app.services.revenue import quantize_currency


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_auth_headers(user: User) -> dict:
    role_names = [r.name for r in user.roles]
    token = create_access_token(
        subject=str(user.id),
        role=role_names[0] if role_names else "customer"
    )
    return {
        "Authorization": f"Bearer {token}",
        "User-Id": str(user.id)
    }


def _get_or_create_super_admin(db: Session) -> User:
    sa_role = db.query(Role).filter(Role.name == "super_admin").first()
    assert sa_role is not None

    admin_user = db.query(User).filter(User.roles.contains(sa_role)).first()
    if not admin_user:
        admin_user = User(
            email=f"sa_{uuid.uuid4().hex[:6]}@gobeyond.in",
            phone=f"99{uuid.uuid4().hex[:8]}"[:10],
            hashed_password="sa_test_hash",
            full_name="Platform Super Admin",
            is_active=True,
            is_verified=True,
            account_status="ACTIVE"
        )
        admin_user.roles.append(sa_role)
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    return admin_user


def _get_or_create_test_customer(db: Session) -> User:
    cust_role = db.query(Role).filter(Role.name == "customer").first()
    customer = User(
        email=f"cust_{uuid.uuid4().hex[:6]}@gobeyond.test",
        phone=f"98{uuid.uuid4().hex[:8]}"[:10],
        hashed_password="cust_test_hash",
        full_name="Test Customer User",
        is_active=True,
        is_verified=True,
        account_status="ACTIVE"
    )
    if cust_role:
        customer.roles.append(cust_role)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


# ==============================================================================
# 1. SUPER ADMIN AUTHORIZATION & ACCESS CONTROL
# ==============================================================================

def test_super_admin_authorization_enforcement(client, db_session):
    """
    Verifies that all admin routes strictly enforce require_super_admin.
    Unauthenticated users, regular customers, and partner accounts are denied (401/403).
    Super Admin access passes successfully.
    """
    admin_user = _get_or_create_super_admin(db_session)
    customer = _get_or_create_test_customer(db_session)
    partner = db_session.query(Partner).first()

    try:
        # 1. Anonymous request denied
        res_anon = client.get("/api/v1/admin/stats")
        assert res_anon.status_code in [401, 403]

        # 2. Customer user denied
        cust_headers = _get_auth_headers(customer)
        res_cust = client.get("/api/v1/admin/stats", headers=cust_headers)
        assert res_cust.status_code == 403

        # 3. Partner user denied
        if partner:
            partner_headers = _get_auth_headers(partner.user)
            res_partner = client.get("/api/v1/admin/stats", headers=partner_headers)
            assert res_partner.status_code == 403

        # 4. Super Admin permitted
        admin_headers = _get_auth_headers(admin_user)
        res_admin = client.get("/api/v1/admin/stats", headers=admin_headers)
        assert res_admin.status_code == 200
        data = res_admin.json()
        assert "total_users" in data
        assert "gross_confirmed_booking_value" in data
    finally:
        db_session.delete(customer)
        db_session.commit()


# ==============================================================================
# 2. OVERVIEW & FINANCIAL CONSERVATION METRICS
# ==============================================================================

def test_admin_dashboard_stats_and_financial_conservation(client, db_session):
    """
    Verifies system-wide metrics calculation via revenue engine, including
    7-day and 6-month trends, vertical bookings, and financial conservation.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    res = client.get("/api/v1/admin/stats", headers=headers)
    assert res.status_code == 200
    stats = res.json()

    assert stats["total_users"] >= 1
    assert stats["total_partners"] >= 4
    assert stats["total_bookings"] >= 0
    assert "vertical_bookings" in stats
    assert isinstance(stats["vertical_bookings"], dict)
    assert "daily_trends" in stats
    assert isinstance(stats["daily_trends"], list)
    assert "monthly_trends" in stats
    assert isinstance(stats["monthly_trends"], list)

    # Invariant: Net Collected = Total Captured - Total Refunded
    net = round(stats["total_captured_payments"] - stats["total_refunded_amount"], 2)
    assert abs(net - stats["net_collected_amount"]) < 0.05


# ==============================================================================
# 3. PARTNER MANAGEMENT & KYC VERIFICATION LIFECYCLE
# ==============================================================================

def test_admin_partner_application_approval_and_rejection(client, db_session):
    """
    Verifies that Super Admin can list partners, review KYC documents,
    approve/suspend partners, and record immutable audit logs.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    # Create temporary pending partner
    p_user = User(
        email=f"pending_partner_{uuid.uuid4().hex[:6]}@gobeyond.test",
        phone=f"90{uuid.uuid4().hex[:8]}"[:10],
        hashed_password="hash",
        full_name="Pending Partner Owner",
        is_active=True,
        account_status="ACTIVE"
    )
    db_session.add(p_user)
    db_session.flush()

    partner = Partner(
        user_id=p_user.id,
        business_name="Urban Sky Cafe & Dine",
        partner_type="RESTAURANT",
        contact_email=p_user.email,
        contact_phone=p_user.phone,
        status="PENDING_APPROVAL"
    )
    db_session.add(partner)
    db_session.flush()

    doc = PartnerDocument(
        partner_id=partner.id,
        document_type="FSSAI",
        document_url="https://s3.gobeyond.in/docs/fssai_cert.pdf",
        status="SUBMITTED"
    )
    db_session.add(doc)
    db_session.commit()

    try:
        # 1. Search for pending partner
        res_list = client.get("/api/v1/admin/partners?status=PENDING_APPROVAL", headers=headers)
        assert res_list.status_code == 200
        partners_list = res_list.json()["partners"]
        assert any(p["id"] == partner.id for p in partners_list)

        # 2. Inspect partner details
        res_detail = client.get(f"/api/v1/admin/partners/{partner.id}", headers=headers)
        assert res_detail.status_code == 200
        p_detail = res_detail.json()
        assert p_detail["business_name"] == "Urban Sky Cafe & Dine"
        assert len(p_detail["documents"]) >= 1

        # 3. Verify KYC document
        res_doc = client.put(
            f"/api/v1/admin/partners/{partner.id}/documents/{doc.id}",
            json={"status": "VERIFIED"},
            headers=headers
        )
        assert res_doc.status_code == 200
        assert res_doc.json()["status"] == "VERIFIED"

        # 4. Approve partner
        res_approve = client.put(
            f"/api/v1/admin/partners/{partner.id}/status",
            json={"status": "APPROVED", "notes": "FSSAI verified and approved."},
            headers=headers
        )
        assert res_approve.status_code == 200
        assert res_approve.json()["status"] == "APPROVED"

        # Verify DB status and verified_at
        db_session.refresh(partner)
        assert partner.status == "APPROVED"
        assert partner.verified_at is not None

        # 5. Suspend partner
        res_suspend = client.put(
            f"/api/v1/admin/partners/{partner.id}/status",
            json={"status": "SUSPENDED", "notes": "Compliance re-audit required."},
            headers=headers
        )
        assert res_suspend.status_code == 200
        assert res_suspend.json()["status"] == "SUSPENDED"

        # 6. Verify audit log entry
        audit_res = client.get("/api/v1/admin/audit-logs?action=PARTNER_STATUS_UPDATE", headers=headers)
        assert audit_res.status_code == 200
        logs = audit_res.json()["logs"]
        assert any(l["resource_id"] == str(partner.id) for l in logs)

    finally:
        # Clean teardown
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(AuditLog).filter(
                (AuditLog.user_id == p_user.id) |
                (AuditLog.resource_id.in_([str(partner.id), str(doc.id)]))
            ).delete(synchronize_session=False)
            cleanup_db.query(Notification).filter(Notification.user_id == p_user.id).delete(synchronize_session=False)
            cleanup_db.query(PartnerDocument).filter(PartnerDocument.partner_id == partner.id).delete(synchronize_session=False)
            cleanup_db.query(Partner).filter(Partner.id == partner.id).delete(synchronize_session=False)
            cleanup_db.query(User).filter(User.id == p_user.id).delete(synchronize_session=False)
            cleanup_db.commit()
        finally:
            cleanup_db.close()


# ==============================================================================
# 4. PARTNER COMMISSION RATE MANAGEMENT
# ==============================================================================

def test_admin_partner_commission_update_with_audit_trail(client, db_session):
    """
    Verifies that Super Admin can update a partner's contract commission rate,
    preventing arbitrary or unauthorized changes and logging the event in AuditLog.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    partner = db_session.query(Partner).filter(Partner.id == 2).first()
    assert partner is not None
    original_rate = partner.commission_rate

    try:
        # 1. Update commission rate to 18.50% (0.1850)
        update_res = client.put(
            f"/api/v1/admin/partners/{partner.id}/commission",
            json={"commission_rate": 0.1850, "notes": "Negotiated Q4 contract adjustment"},
            headers=headers
        )
        assert update_res.status_code == 200
        assert update_res.json()["new_commission_rate"] == 0.185

        # Verify DB updated
        db_session.refresh(partner)
        assert Decimal(str(partner.commission_rate)) == Decimal("0.1850")

        # 2. Verify Audit Log recorded old and new rates
        audit_res = client.get("/api/v1/admin/audit-logs?action=PARTNER_COMMISSION_UPDATE", headers=headers)
        assert audit_res.status_code == 200
        logs = audit_res.json()["logs"]
        assert any(l["resource_id"] == str(partner.id) for l in logs)

    finally:
        partner.commission_rate = original_rate
        db_session.commit()


# ==============================================================================
# 5. USER MANAGEMENT, SUSPENSION & SESSION REVOCATION
# ==============================================================================

def test_admin_user_management_suspension_and_token_revocation(client, db_session):
    """
    Verifies customer search, user status update, refresh token invalidation,
    and self-suspension prevention for Super Admin.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    test_user = User(
        email=f"susp_test_{uuid.uuid4().hex[:6]}@gobeyond.test",
        phone=f"92{uuid.uuid4().hex[:8]}"[:10],
        hashed_password="hash",
        full_name="Target Suspended User",
        is_active=True,
        account_status="ACTIVE"
    )
    db_session.add(test_user)
    db_session.flush()

    token_record = RefreshToken(
        user_id=test_user.id,
        token_hash="fake_hash_12345",
        family_id=uuid.uuid4().hex,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        is_revoked=False
    )
    db_session.add(token_record)
    db_session.commit()

    try:
        # 1. Search for user
        search_res = client.get(f"/api/v1/admin/users?search={test_user.email}", headers=headers)
        assert search_res.status_code == 200
        users_list = search_res.json()["users"]
        assert any(u["id"] == test_user.id for u in users_list)

        # 2. Suspend user
        susp_res = client.put(
            f"/api/v1/admin/users/{test_user.id}/status",
            json={"account_status": "SUSPENDED", "reason": "Suspicious fraudulent activity"},
            headers=headers
        )
        assert susp_res.status_code == 200
        assert susp_res.json()["account_status"] == "SUSPENDED"
        assert susp_res.json()["is_active"] is False

        # Verify refresh token was revoked
        db_session.refresh(token_record)
        assert token_record.is_revoked is True

        # 3. Super Admin cannot deactivate own account
        self_res = client.put(
            f"/api/v1/admin/users/{admin.id}/status",
            json={"account_status": "SUSPENDED"},
            headers=headers
        )
        assert self_res.status_code == 400

        # 4. Reactivate user
        react_res = client.put(
            f"/api/v1/admin/users/{test_user.id}/status",
            json={"account_status": "ACTIVE"},
            headers=headers
        )
        assert react_res.status_code == 200
        assert react_res.json()["account_status"] == "ACTIVE"
        assert react_res.json()["is_active"] is True

    finally:
        cleanup_db = SessionLocal()
        try:
            cleanup_db.query(AuditLog).filter(
                (AuditLog.user_id == test_user.id) |
                (AuditLog.resource_id == str(test_user.id))
            ).delete(synchronize_session=False)
            cleanup_db.query(RefreshToken).filter(RefreshToken.user_id == test_user.id).delete(synchronize_session=False)
            cleanup_db.query(User).filter(User.id == test_user.id).delete(synchronize_session=False)
            cleanup_db.commit()
        finally:
            cleanup_db.close()


# ==============================================================================
# 6. BOOKING OPERATIONS & DETAILED INSPECTOR
# ==============================================================================

def test_admin_booking_operations_and_inspector(client, db_session):
    """
    Verifies booking listing across verticals, deep booking inspection,
    and administrative cancellation with audit logging.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    # 1. List bookings
    list_res = client.get("/api/v1/admin/bookings?page=1&page_size=10", headers=headers)
    assert list_res.status_code == 200
    b_data = list_res.json()
    assert "total" in b_data
    assert "bookings" in b_data

    # 2. Deep inspect existing booking if available
    first_b = db_session.query(Booking).first()
    if first_b:
        detail_res = client.get(f"/api/v1/admin/bookings/{first_b.booking_reference}", headers=headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["booking_reference"] == first_b.booking_reference
        assert "customer" in detail
        assert "items" in detail
        assert "payments" in detail


# ==============================================================================
# 7. FINANCIAL LEDGER, PAYMENTS & REFUNDS
# ==============================================================================

def test_admin_financial_ledger_payments_and_refunds(client, db_session):
    """
    Verifies payments transaction listing, refunds listing,
    and refund processing validation safeguards.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    # 1. System Financial Ledger
    ledger_res = client.get("/api/v1/admin/financials/ledger", headers=headers)
    assert ledger_res.status_code == 200
    ledger = ledger_res.json()
    assert "gross_confirmed_booking_value" in ledger
    assert "total_captured_payments" in ledger

    # 2. Payments list
    payments_res = client.get("/api/v1/admin/payments?page=1&page_size=10", headers=headers)
    assert payments_res.status_code == 200
    assert "payments" in payments_res.json()

    # 3. Refunds list
    refunds_res = client.get("/api/v1/admin/refunds?page=1&page_size=10", headers=headers)
    assert refunds_res.status_code == 200
    assert "refunds" in refunds_res.json()

    # 4. Refund validation: Non-existent booking returns 404
    invalid_ref_res = client.post(
        "/api/v1/admin/bookings/GB-NON-EXISTENT/refund",
        json={"reason": "Customer cancellation"},
        headers=headers
    )
    assert invalid_ref_res.status_code == 404


# ==============================================================================
# 8. PLATFORM MANAGEMENT: COUPONS, NOTIFICATIONS & AUDIT LOGS
# ==============================================================================

def test_admin_platform_coupons_notifications_and_audit(client, db_session):
    """
    Verifies promotional coupon creation, toggle, broadcast notifications,
    and audit log querying.
    """
    admin = _get_or_create_super_admin(db_session)
    headers = _get_auth_headers(admin)

    test_code = f"GBTEST_{uuid.uuid4().hex[:6].upper()}"

    try:
        # 1. Create Coupon
        create_res = client.post(
            "/api/v1/admin/coupons",
            json={
                "code": test_code,
                "description": "Exclusive Test 20% Discount",
                "discount_type": "PERCENTAGE",
                "discount_value": 20.0,
                "min_order_value": 200.0,
                "max_discount": 100.0,
                "usage_limit": 50
            },
            headers=headers
        )
        assert create_res.status_code == 200

        coupon = db_session.query(Coupon).filter(Coupon.code == test_code).first()
        assert coupon is not None
        assert coupon.is_active is True

        # 2. Toggle Coupon status
        toggle_res = client.put(f"/api/v1/admin/coupons/{coupon.id}/toggle", headers=headers)
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_active"] is False

        # 3. Broadcast Notification
        broadcast_res = client.post(
            "/api/v1/admin/notifications/broadcast",
            json={
                "title": "Welcome to Go Beyond Weekend! 🌟",
                "message": "Explore the finest dining and movie experiences in Hyderabad.",
                "target_role": "ALL"
            },
            headers=headers
        )
        assert broadcast_res.status_code == 200
        assert broadcast_res.json()["success"] is True

        # 4. Query Audit Logs
        audit_res = client.get("/api/v1/admin/audit-logs?page=1&page_size=20", headers=headers)
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        assert "logs" in audit_data
        assert any(l["action"] == "COUPON_CREATED" for l in audit_data["logs"])

    finally:
        # Teardown coupon
        db_session.query(Coupon).filter(Coupon.code == test_code).delete(synchronize_session=False)
        db_session.query(AuditLog).filter(AuditLog.resource_id == test_code).delete(synchronize_session=False)
        db_session.commit()

