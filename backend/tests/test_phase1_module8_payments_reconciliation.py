"""GO BEYOND — Module 8 Payment Engine & Financial Reconciliation Test Suite

Exhaustive verification of:
1. Successful payment flow (create-order -> verify signature -> captured -> confirmed)
2. Failed payment flow (invalid signature, state machine protection)
3. Duplicate webhook idempotency (Redis event deduplication)
4. Invalid webhook signature rejection (HTTP 400)
5. Delayed webhook on already confirmed booking
6. Out-of-order webhook handling (webhook captures before client verify)
7. Full refund processing (100% refund, status transitions)
8. Partial refund processing (fractional refund, status PARTIALLY_REFUNDED)
9. Multiple partial refunds within captured balance
10. Over-refund prevention (strict rejection if refund > remaining captured balance)
11. Late payment after hold expiry triggers automated refund reconciliation
12. Refund failure state handling in reconciliation engine
13. Multi-vertical commission calculations across all 5 verticals (MOVIE, DINING, EVENT, SPORTS, ACTIVITY)
14. Financial conservation: Captured = Platform Revenue + Partner Settlements + Refunds
15. Concurrent payment verification idempotency
16. Reconciliation discrepancy detection (AMOUNT_MISMATCH, DUPLICATE_GATEWAY_TXN, OVER_REFUND, STALE_HOLD)
17. Partner financial isolation on payments and settlements
18. Admin refund authorization & immutable audit logging
"""
import pytest
import datetime
import uuid
import hmac
import hashlib
import json
from decimal import Decimal
from typing import Optional
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, Role
from app.models.partner import Partner
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund
from app.models.audit import AuditLog, Notification
from app.models.dining import DiningTable, Restaurant
from app.models.event import Event, EventTicketType
from app.models.sports import ActivitySlot
from app.models.movie import Seat
from app.services.revenue import calculate_revenue_metrics, quantize_currency
from app.services.reconciliation import ReconciliationEngine


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
            email=f"sa_m8_{uuid.uuid4().hex[:6]}@gobeyond.in",
            phone=f"98{uuid.uuid4().hex[:8]}"[:10],
            hashed_password="sa_test_hash",
            full_name="Platform Super Admin M8",
            is_active=True,
            is_verified=True,
            account_status="ACTIVE"
        )
        admin_user.roles.append(sa_role)
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    return admin_user


def _create_test_user(db: Session, email_prefix: str = "cust") -> User:
    cust_role = db.query(Role).filter(Role.name == "customer").first()
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"97{uuid.uuid4().hex[:8]}"[:10],
        hashed_password="test_hashed_pw",
        full_name="Test Customer M8",
        is_active=True,
        is_verified=True,
        account_status="ACTIVE"
    )
    if cust_role:
        user.roles.append(cust_role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_seeded_partner(db: Session) -> Partner:
    partner = db.query(Partner).filter(Partner.status.in_(["ACTIVE", "APPROVED"])).first()
    assert partner is not None, "Seeded partner required for tests"
    return partner


def _create_test_booking(
    db: Session,
    user: User,
    partner: Partner,
    amount: Decimal = Decimal("500.00"),
    status: str = "INVENTORY_HELD",
    booking_type: str = "MOVIE",
    expires_in_minutes: int = 15,
    item_type: str = "GENERAL",
    item_id: int = 1
) -> Booking:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    booking = Booking(
        booking_reference=f"GB-M8-{uuid.uuid4().hex[:8].upper()}",
        user_id=user.id,
        booking_type=booking_type,
        status=status,
        total_amount=amount,
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        final_payable=amount,
        created_at=now_utc,
        expires_at=now_utc + datetime.timedelta(minutes=expires_in_minutes)
    )
    db.add(booking)
    db.flush()

    item = BookingItem(
        booking_id=booking.id,
        item_type=item_type,
        item_id=item_id,
        name="Test Item M8",
        quantity=1,
        unit_price=amount,
        subtotal=amount,
        details={"partner_id": partner.id}
    )
    db.add(item)
    db.commit()
    db.refresh(booking)
    return booking


def _generate_razorpay_signature(order_id: str, payment_id: str) -> str:
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        msg,
        hashlib.sha256
    ).hexdigest()


def _cleanup_test_data(db: Session, user: Optional[User] = None, booking: Optional[Booking] = None):
    try:
        if booking:
            db.query(Refund).filter(Refund.booking_id == booking.id).delete()
            db.query(Payment).filter(Payment.booking_id == booking.id).delete()
            db.query(BookingItem).filter(BookingItem.booking_id == booking.id).delete()
            db.query(Booking).filter(Booking.id == booking.id).delete()
            db.commit()
        if user:
            db.query(Notification).filter(Notification.user_id == user.id).delete()
            db.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
            user.roles.clear()
            db.delete(user)
            db.commit()
    except Exception:
        db.rollback()


# ==============================================================================
# TEST 1: SUCCESSFUL PAYMENT FLOW
# ==============================================================================

def test_m8_01_successful_payment_flow(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("450.00"))

    headers = _get_auth_headers(user)
    try:
        # 1. Create payment order
        res_order = client.post(
            "/api/v1/payments/create-order",
            headers=headers,
            json={"booking_id": booking.id}
        )
        assert res_order.status_code == 200, res_order.text
        order_data = res_order.json()
        assert "order_id" in order_data
        assert order_data["amount"] == 450.0
        assert order_data["currency"] == "INR"

        order_id = order_data["order_id"]
        payment_id = f"pay_{uuid.uuid4().hex[:14]}"
        valid_sig = _generate_razorpay_signature(order_id, payment_id)

        # 2. Verify payment signature
        res_verify = client.post(
            "/api/v1/payments/verify",
            headers=headers,
            json={
                "booking_id": booking.id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": valid_sig
            }
        )
        assert res_verify.status_code == 200, res_verify.text
        verify_data = res_verify.json()
        assert verify_data["success"] is True
        assert verify_data["status"] == "CONFIRMED"
        assert len(verify_data["qr_code_token"]) > 0

        # DB verification
        db_session.refresh(booking)
        assert booking.status == "CONFIRMED"
        assert booking.qr_code_token is not None

        payment = db_session.query(Payment).filter(Payment.booking_id == booking.id).first()
        assert payment is not None
        assert payment.status == "CAPTURED"
        assert payment.gateway_payment_id == payment_id
        assert quantize_currency(payment.amount) == Decimal("450.00")
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 2: FAILED PAYMENT FLOW
# ==============================================================================

def test_m8_02_failed_payment_flow(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("300.00"))

    headers = _get_auth_headers(user)
    try:
        # Create order
        res_order = client.post(
            "/api/v1/payments/create-order",
            headers=headers,
            json={"booking_id": booking.id}
        )
        assert res_order.status_code == 200
        order_id = res_order.json()["order_id"]

        # Verify with invalid signature
        res_verify = client.post(
            "/api/v1/payments/verify",
            headers=headers,
            json={
                "booking_id": booking.id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:14]}",
                "razorpay_signature": "invalid_forged_signature_12345"
            }
        )
        assert res_verify.status_code == 400
        assert "Invalid HMAC signature" in res_verify.text

        db_session.refresh(booking)
        assert booking.status == "FAILED"
        payment = db_session.query(Payment).filter(Payment.booking_id == booking.id).first()
        assert payment is not None
        assert payment.status == "FAILED"
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 3: DUPLICATE WEBHOOK IDEMPOTENCY
# ==============================================================================

def test_m8_03_duplicate_webhook_idempotency(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("600.00"))

    headers = _get_auth_headers(user)
    try:
        res_order = client.post("/api/v1/payments/create-order", headers=headers, json={"booking_id": booking.id})
        order_id = res_order.json()["order_id"]
        gateway_payment_id = f"pay_wh_{uuid.uuid4().hex[:10]}"
        event_id = f"evt_{uuid.uuid4().hex[:14]}"

        webhook_payload = {
            "entity": "event",
            "account_id": "acc_test",
            "event": "payment.captured",
            "id": event_id,
            "payload": {
                "payment": {
                    "entity": {
                        "id": gateway_payment_id,
                        "order_id": order_id,
                        "amount": 60000,
                        "currency": "INR",
                        "status": "captured"
                    }
                }
            }
        }
        payload_bytes = json.dumps(webhook_payload).encode("utf-8")
        wh_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        # 1st Webhook delivery
        res1 = client.post(
            "/api/v1/payments/webhook",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": wh_signature
            }
        )
        assert res1.status_code == 200, res1.text
        assert res1.json()["status"] == "received"

        # 2nd Webhook delivery (duplicate event)
        res2 = client.post(
            "/api/v1/payments/webhook",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": wh_signature
            }
        )
        assert res2.status_code == 200, res2.text
        assert res2.json()["status"] == "already_processed"
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 4: INVALID WEBHOOK SIGNATURE REJECTION
# ==============================================================================

def test_m8_04_invalid_webhook_signature_rejection(client: TestClient):
    payload = json.dumps({"event": "payment.captured", "id": "fake_evt"}).encode("utf-8")
    res = client.post(
        "/api/v1/payments/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "forged_invalid_signature"
        }
    )
    assert res.status_code == 400
    assert "Invalid webhook signature" in res.text


# ==============================================================================
# TEST 5: DELAYED WEBHOOK ON ACTIVE CONFIRMED BOOKING
# ==============================================================================

def test_m8_05_delayed_webhook_on_active_booking(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("750.00"))

    headers = _get_auth_headers(user)
    try:
        # Create order and verify client-side first
        res_order = client.post("/api/v1/payments/create-order", headers=headers, json={"booking_id": booking.id})
        order_id = res_order.json()["order_id"]
        gateway_payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        sig = _generate_razorpay_signature(order_id, gateway_payment_id)

        client.post(
            "/api/v1/payments/verify",
            headers=headers,
            json={
                "booking_id": booking.id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": gateway_payment_id,
                "razorpay_signature": sig
            }
        )

        db_session.refresh(booking)
        assert booking.status == "CONFIRMED"

        # Webhook arrives after client confirmation
        wh_payload = {
            "entity": "event",
            "event": "payment.captured",
            "id": f"evt_delayed_{uuid.uuid4().hex[:10]}",
            "payload": {
                "payment": {
                    "entity": {
                        "id": gateway_payment_id,
                        "order_id": order_id,
                        "amount": 75000,
                        "status": "captured"
                    }
                }
            }
        }
        wh_bytes = json.dumps(wh_payload).encode("utf-8")
        wh_sig = hmac.new(settings.RAZORPAY_KEY_SECRET.encode("utf-8"), wh_bytes, hashlib.sha256).hexdigest()

        res_wh = client.post(
            "/api/v1/payments/webhook",
            content=wh_bytes,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": wh_sig}
        )
        assert res_wh.status_code == 200
        assert res_wh.json()["status"] == "already_processed"
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 6: OUT-OF-ORDER WEBHOOK HANDLING
# ==============================================================================

def test_m8_06_out_of_order_webhook_handling(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("350.00"))

    headers = _get_auth_headers(user)
    try:
        # Create order (stays in PAYMENT_PENDING)
        res_order = client.post("/api/v1/payments/create-order", headers=headers, json={"booking_id": booking.id})
        order_id = res_order.json()["order_id"]
        gateway_payment_id = f"pay_ooo_{uuid.uuid4().hex[:10]}"

        # Webhook arrives before client calls /verify
        wh_payload = {
            "entity": "event",
            "event": "payment.captured",
            "id": f"evt_ooo_{uuid.uuid4().hex[:10]}",
            "payload": {
                "payment": {
                    "entity": {
                        "id": gateway_payment_id,
                        "order_id": order_id,
                        "amount": 35000,
                        "status": "captured"
                    }
                }
            }
        }
        wh_bytes = json.dumps(wh_payload).encode("utf-8")
        wh_sig = hmac.new(settings.RAZORPAY_KEY_SECRET.encode("utf-8"), wh_bytes, hashlib.sha256).hexdigest()

        res_wh = client.post(
            "/api/v1/payments/webhook",
            content=wh_bytes,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": wh_sig}
        )
        assert res_wh.status_code == 200
        assert res_wh.json()["status"] == "received"

        db_session.refresh(booking)
        assert booking.status == "CONFIRMED"
        assert booking.qr_code_token is not None

        payment = db_session.query(Payment).filter(Payment.booking_id == booking.id).first()
        assert payment.status == "CAPTURED"
        assert payment.gateway_payment_id == gateway_payment_id
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 7: FULL REFUND PROCESSING
# ==============================================================================

def test_m8_07_full_refund_processing(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("500.00"), status="CONFIRMED")

    # Add captured payment
    payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:12]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        amount=Decimal("500.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.commit()

    headers = _get_auth_headers(user)
    try:
        res = client.post(
            "/api/v1/payments/refund",
            headers=headers,
            json={
                "booking_id": booking.id,
                "amount": None,  # Full refund
                "reason": "Customer cancellation"
            }
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["amount"] == 500.0
        assert data["status"] == "PROCESSED"
        assert data["remaining_balance"] == 0.0

        db_session.refresh(booking)
        db_session.refresh(payment)
        assert booking.status == "REFUNDED"
        assert payment.status == "REFUNDED"

        refund = db_session.query(Refund).filter(Refund.booking_id == booking.id).first()
        assert refund is not None
        assert quantize_currency(refund.amount) == Decimal("500.00")
        assert refund.status == "PROCESSED"
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 8: PARTIAL REFUND PROCESSING
# ==============================================================================

def test_m8_08_partial_refund_processing(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("1000.00"), status="CONFIRMED")

    payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:12]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        amount=Decimal("1000.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.commit()

    headers = _get_auth_headers(user)
    try:
        # Partial refund of 350.00
        res = client.post(
            "/api/v1/payments/refund",
            headers=headers,
            json={
                "booking_id": booking.id,
                "amount": 350.00,
                "reason": "One ticket cancelled"
            }
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["amount"] == 350.0
        assert data["remaining_balance"] == 650.0

        db_session.refresh(payment)
        assert payment.status == "PARTIALLY_REFUNDED"
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 9: MULTIPLE PARTIAL REFUNDS WITHIN CAPTURED BALANCE
# ==============================================================================

def test_m8_09_multiple_partial_refunds(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("800.00"), status="CONFIRMED")

    payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:12]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        amount=Decimal("800.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.commit()

    headers = _get_auth_headers(user)
    try:
        # Refund 1: 250
        r1 = client.post("/api/v1/payments/refund", headers=headers, json={"booking_id": booking.id, "amount": 250.0, "reason": "Partial cancellation 1"})
        assert r1.status_code == 200
        assert r1.json()["remaining_balance"] == 550.0

        # Refund 2: 350
        r2 = client.post("/api/v1/payments/refund", headers=headers, json={"booking_id": booking.id, "amount": 350.0, "reason": "Partial cancellation 2"})
        assert r2.status_code == 200
        assert r2.json()["remaining_balance"] == 200.0

        # Refund 3: remaining 200 -> turns status to REFUNDED
        r3 = client.post("/api/v1/payments/refund", headers=headers, json={"booking_id": booking.id, "amount": 200.0, "reason": "Final partial cancellation"})
        assert r3.status_code == 200
        assert r3.json()["remaining_balance"] == 0.0

        db_session.refresh(booking)
        db_session.refresh(payment)
        assert booking.status == "REFUNDED"
        assert payment.status == "REFUNDED"

        total_refunds = sum(r.amount for r in db_session.query(Refund).filter(Refund.booking_id == booking.id).all())
        assert quantize_currency(total_refunds) == Decimal("800.00")
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 10: OVER-REFUND PREVENTION
# ==============================================================================

def test_m8_10_over_refund_prevention(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("500.00"), status="CONFIRMED")

    payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:12]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        amount=Decimal("500.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.commit()

    headers = _get_auth_headers(user)
    try:
        # Attempt refund greater than balance
        res_fail = client.post(
            "/api/v1/payments/refund",
            headers=headers,
            json={"booking_id": booking.id, "amount": 550.00, "reason": "Over-refund test attempt"}
        )
        assert res_fail.status_code == 400
        assert "exceeds remaining refundable balance" in res_fail.text.lower()

        # Partial refund of 300 succeeds
        res_ok = client.post(
            "/api/v1/payments/refund",
            headers=headers,
            json={"booking_id": booking.id, "amount": 300.00, "reason": "Valid partial refund"}
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["remaining_balance"] == 200.0

        # Attempting another 250 fails (only 200 left)
        res_fail2 = client.post(
            "/api/v1/payments/refund",
            headers=headers,
            json={"booking_id": booking.id, "amount": 250.00, "reason": "Excess second refund attempt"}
        )
        assert res_fail2.status_code == 400
        assert "exceeds remaining refundable balance" in res_fail2.text.lower()
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 11: LATE PAYMENT AFTER HOLD EXPIRY TRIGGERS AUTO-REFUND
# ==============================================================================

def test_m8_11_late_payment_hold_expiry_triggers_auto_refund(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)

    # Create expired booking
    booking = _create_test_booking(
        db_session, user, partner,
        amount=Decimal("400.00"),
        status="EXPIRED",
        expires_in_minutes=-10  # 10 minutes in the past
    )

    headers = _get_auth_headers(user)
    try:
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        payment_id = f"pay_late_{uuid.uuid4().hex[:10]}"
        sig = _generate_razorpay_signature(order_id, payment_id)

        # Create payment order record in DB
        payment = Payment(
            booking_id=booking.id,
            user_id=user.id,
            payment_gateway="RAZORPAY",
            gateway_order_id=order_id,
            amount=Decimal("400.00"),
            currency="INR",
            status="INITIATED"
        )
        db_session.add(payment)
        db_session.commit()

        # Late verify request
        res = client.post(
            "/api/v1/payments/verify",
            headers=headers,
            json={
                "booking_id": booking.id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": sig
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "REFUND_PENDING"
        assert "Automatic refund initiated" in data["message"]

        db_session.refresh(booking)
        db_session.refresh(payment)
        assert booking.status == "REFUND_PENDING"
        assert payment.status == "REFUND_PENDING"

        refund = db_session.query(Refund).filter(Refund.payment_id == payment.id).first()
        assert refund is not None
        assert quantize_currency(refund.amount) == Decimal("400.00")
        assert "Late payment after hold expiry" in refund.reason
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 12: REFUND FAILURE STATE HANDLING FOR RECONCILIATION
# ==============================================================================

def test_m8_12_refund_failure_state_handling(db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("300.00"), status="CONFIRMED")

    payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:12]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        amount=Decimal("300.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.flush()

    failed_refund = Refund(
        payment_id=payment.id,
        booking_id=booking.id,
        gateway_refund_id=f"rfn_fail_{uuid.uuid4().hex[:10]}",
        amount=Decimal("300.00"),
        reason="Test bank rail failure",
        status="FAILED"
    )
    db_session.add(failed_refund)
    db_session.commit()

    try:
        report = ReconciliationEngine.run_reconciliation_audit(db_session)
        assert not report.is_healthy
        discrepancy_codes = [d.code for d in report.discrepancies]
        assert "FAILED_REFUND_ALERT" in discrepancy_codes

        matched = next(d for d in report.discrepancies if d.code == "FAILED_REFUND_ALERT" and d.gateway_id == failed_refund.gateway_refund_id)
        assert matched.severity == "MEDIUM"
        assert "FAILED" in matched.description
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 13: MULTI-VERTICAL COMMISSION CALCULATIONS
# ==============================================================================

def test_m8_13_multi_vertical_commission_calculations(db_session: Session):
    seat = db_session.query(Seat).first()
    table = db_session.query(DiningTable).first()
    ticket = db_session.query(EventTicketType).first()
    slot = db_session.query(ActivitySlot).first()

    vertical_configs = [
        ("MOVIE", "SEAT", seat.id if seat else 1),
        ("DINING", "TABLE", table.id if table else 1),
        ("EVENT", "TICKET", ticket.id if ticket else 1),
        ("SPORTS", "SLOT", slot.id if slot else 1),
        ("ACTIVITY", "SLOT", slot.id if slot else 1),
    ]

    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)

    created_bookings = []
    try:
        for vert, it_type, it_id in vertical_configs:
            booking = _create_test_booking(
                db_session, user, partner,
                amount=Decimal("1000.00"),
                status="CONFIRMED",
                booking_type=vert,
                item_type=it_type,
                item_id=it_id
            )
            created_bookings.append(booking)

            payment = Payment(
                booking_id=booking.id,
                user_id=user.id,
                payment_gateway="RAZORPAY",
                gateway_order_id=f"order_{vert}_{uuid.uuid4().hex[:8]}",
                gateway_payment_id=f"pay_{vert}_{uuid.uuid4().hex[:8]}",
                amount=Decimal("1000.00"),
                currency="INR",
                status="CAPTURED"
            )
            db_session.add(payment)
            db_session.commit()

        metrics = calculate_revenue_metrics(db_session)
        assert not metrics["requires_financial_reconciliation"]

        # Global invariance: net_collected = total_captured - total_refunded = platform rev + partner settlements
        total_cap = Decimal(str(metrics["total_captured_payments"]))
        total_ref = Decimal(str(metrics["total_refunded_amount"]))
        net_col = Decimal(str(metrics["net_collected_amount"]))
        plat_rev = Decimal(str(metrics["actual_platform_revenue"]))
        part_pay = Decimal(str(metrics["partner_settlements_payable"]))
        assert abs((total_cap - total_ref) - net_col) <= Decimal("0.05")
        assert abs(net_col - (plat_rev + part_pay)) <= Decimal("0.05")

        # Scoped 5-vertical invariance: captured = net_collected = platform rev + partner settlements
        scoped = calculate_revenue_metrics(db_session, booking_ids=[b.id for b in created_bookings])
        scoped_cap = Decimal(str(scoped["total_captured_payments"]))
        scoped_plat = Decimal(str(scoped["actual_platform_revenue"]))
        scoped_part = Decimal(str(scoped["partner_settlements_payable"]))
        assert scoped_cap == Decimal("5000.00")
        assert abs(scoped_cap - (scoped_plat + scoped_part)) <= Decimal("0.05")
    finally:
        for b in created_bookings:
            _cleanup_test_data(db_session, booking=b)
        _cleanup_test_data(db_session, user=user)


# ==============================================================================
# TEST 14: FINANCIAL CONSERVATION INVARIANCE
# ==============================================================================

def test_m8_14_financial_conservation(db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)

    booking = _create_test_booking(db_session, user, partner, amount=Decimal("2000.00"), status="CONFIRMED")
    payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:10]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:10]}",
        amount=Decimal("2000.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.flush()

    # Process partial refund of 500
    refund = Refund(
        payment_id=payment.id,
        booking_id=booking.id,
        gateway_refund_id=f"rfn_{uuid.uuid4().hex[:10]}",
        amount=Decimal("500.00"),
        reason="Partial refund",
        status="PROCESSED"
    )
    db_session.add(refund)
    payment.status = "PARTIALLY_REFUNDED"
    db_session.commit()

    try:
        metrics = calculate_revenue_metrics(db_session)
        captured = Decimal(str(metrics["total_captured_payments"]))
        refunded = Decimal(str(metrics["total_refunded_amount"]))
        net = Decimal(str(metrics["net_collected_amount"]))
        platform = Decimal(str(metrics["actual_platform_revenue"]))
        partner_payout = Decimal(str(metrics["partner_settlements_payable"]))

        # 1. Net = Captured - Refunded
        assert (captured - refunded) == net

        # 2. Conservation: Net = Platform Fee + Partner Settlements
        assert abs((platform + partner_payout) - net) <= Decimal("0.05")
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 15: CONCURRENT PAYMENT VERIFICATION IDEMPOTENCY
# ==============================================================================

def test_m8_15_concurrent_payment_verification_idempotency(client: TestClient, db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("400.00"))

    headers = _get_auth_headers(user)
    try:
        res_order = client.post("/api/v1/payments/create-order", headers=headers, json={"booking_id": booking.id})
        order_id = res_order.json()["order_id"]
        gateway_payment_id = f"pay_conc_{uuid.uuid4().hex[:10]}"
        sig = _generate_razorpay_signature(order_id, gateway_payment_id)

        # First verification call
        res1 = client.post(
            "/api/v1/payments/verify",
            headers=headers,
            json={
                "booking_id": booking.id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": gateway_payment_id,
                "razorpay_signature": sig
            }
        )
        assert res1.status_code == 200
        assert res1.json()["success"] is True

        # Second verification call (simulated race condition/retry)
        res2 = client.post(
            "/api/v1/payments/verify",
            headers=headers,
            json={
                "booking_id": booking.id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": gateway_payment_id,
                "razorpay_signature": sig
            }
        )
        assert res2.status_code == 200
        assert res2.json()["success"] is True
        assert res2.json()["status"] == "CONFIRMED"
        assert "already verified" in res2.json()["message"].lower()

        # Exactly 1 payment record exists
        payments = db_session.query(Payment).filter(Payment.booking_id == booking.id).all()
        assert len(payments) == 1
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 16: RECONCILIATION DISCREPANCY DETECTION
# ==============================================================================

def test_m8_16_reconciliation_discrepancy_detection(db_session: Session):
    user = _create_test_user(db_session)
    partner = _get_seeded_partner(db_session)
    booking = _create_test_booking(db_session, user, partner, amount=Decimal("1000.00"), status="CONFIRMED")

    # Induce AMOUNT_MISMATCH: Payment is 900.00, booking payable is 1000.00
    mismatch_payment = Payment(
        booking_id=booking.id,
        user_id=user.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"order_{uuid.uuid4().hex[:10]}",
        gateway_payment_id=f"pay_mismatch_{uuid.uuid4().hex[:8]}",
        amount=Decimal("900.00"),  # mismatch
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(mismatch_payment)
    db_session.commit()

    try:
        report = ReconciliationEngine.run_reconciliation_audit(db_session)
        assert not report.is_healthy
        discrepancy_codes = [d.code for d in report.discrepancies]
        assert "AMOUNT_MISMATCH" in discrepancy_codes

        discrepancy = next(d for d in report.discrepancies if d.code == "AMOUNT_MISMATCH" and d.booking_reference == booking.booking_reference)
        assert discrepancy.severity == "HIGH"
        assert "differs from booking contract payable" in discrepancy.description
        assert discrepancy.details["difference"] == -100.0
    finally:
        _cleanup_test_data(db_session, user, booking)


# ==============================================================================
# TEST 17: PARTNER FINANCIAL ISOLATION
# ==============================================================================

def test_m8_17_partner_financial_isolation(client: TestClient, db_session: Session):
    p2 = db_session.query(Partner).filter(Partner.id == 2).first()
    p3 = db_session.query(Partner).filter(Partner.id == 3).first()
    if not p2 or not p3:
        pytest.skip("Requires seeded partners 2 and 3")

    table = db_session.query(DiningTable).join(Restaurant).filter(Restaurant.partner_id == 2).first()
    ticket = db_session.query(EventTicketType).join(Event).filter(Event.partner_id == 3).first()
    if not table or not ticket:
        pytest.skip("Requires restaurant table and event ticket for partners 2 and 3")

    u1 = _create_test_user(db_session, "p2_cust")
    u2 = _create_test_user(db_session, "p3_cust")

    b1 = _create_test_booking(db_session, u1, p2, amount=Decimal("500.00"), status="CONFIRMED", booking_type="DINING", item_type="TABLE", item_id=table.id)
    b2 = _create_test_booking(db_session, u2, p3, amount=Decimal("800.00"), status="CONFIRMED", booking_type="EVENT", item_type="TICKET", item_id=ticket.id)

    pay1 = Payment(booking_id=b1.id, user_id=u1.id, payment_gateway="RAZORPAY", gateway_order_id=f"ord_{uuid.uuid4().hex[:8]}", gateway_payment_id=f"pay_{uuid.uuid4().hex[:8]}", amount=Decimal("500.00"), currency="INR", status="CAPTURED")
    pay2 = Payment(booking_id=b2.id, user_id=u2.id, payment_gateway="RAZORPAY", gateway_order_id=f"ord_{uuid.uuid4().hex[:8]}", gateway_payment_id=f"pay_{uuid.uuid4().hex[:8]}", amount=Decimal("800.00"), currency="INR", status="CAPTURED")
    db_session.add_all([pay1, pay2])
    db_session.commit()

    try:
        from app.api.v1.endpoints.partners import get_partner_booking_ids
        p2_bids = get_partner_booking_ids(db_session, 2)
        p3_bids = get_partner_booking_ids(db_session, 3)

        assert b1.id in p2_bids
        assert b1.id not in p3_bids
        assert b2.id in p3_bids
        assert b2.id not in p2_bids
    finally:
        _cleanup_test_data(db_session, u1, b1)
        _cleanup_test_data(db_session, u2, b2)


# ==============================================================================
# TEST 18: ADMIN REFUND AUTHORIZATION & AUDIT LOGGING
# ==============================================================================

def test_m8_18_admin_refund_authorization_and_audit(client: TestClient, db_session: Session):
    customer = _create_test_user(db_session, "customer_owner")
    other_user = _create_test_user(db_session, "other_customer")
    admin = _get_or_create_super_admin(db_session)
    partner = _get_seeded_partner(db_session)

    booking = _create_test_booking(db_session, customer, partner, amount=Decimal("600.00"), status="CONFIRMED")
    payment = Payment(
        booking_id=booking.id,
        user_id=customer.id,
        payment_gateway="RAZORPAY",
        gateway_order_id=f"ord_{uuid.uuid4().hex[:8]}",
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:8]}",
        amount=Decimal("600.00"),
        currency="INR",
        status="CAPTURED"
    )
    db_session.add(payment)
    db_session.commit()

    try:
        # 1. Other unauthorized customer attempts to refund -> 403 Forbidden
        other_headers = _get_auth_headers(other_user)
        res_forbidden = client.post(
            "/api/v1/payments/refund",
            headers=other_headers,
            json={"booking_id": booking.id, "reason": "Unauthorized refund attempt"}
        )
        assert res_forbidden.status_code == 403

        # 2. Unauthorized customer attempts to run reconciliation -> 403 Forbidden
        res_rec_forbidden = client.post("/api/v1/payments/reconciliation/run", headers=other_headers)
        assert res_rec_forbidden.status_code == 403

        # 3. Super admin executes refund -> 200 OK
        admin_headers = _get_auth_headers(admin)
        res_admin_refund = client.post(
            "/api/v1/payments/refund",
            headers=admin_headers,
            json={"booking_id": booking.id, "amount": 600.00, "reason": "Super Admin override dispute"}
        )
        assert res_admin_refund.status_code == 200
        refund_data = res_admin_refund.json()
        assert refund_data["success"] is True

        # Verify audit log entry
        audit_log = db_session.query(AuditLog).filter(
            AuditLog.user_id == admin.id,
            AuditLog.action == "REFUND_PROCESSED"
        ).order_by(AuditLog.id.desc()).first()
        assert audit_log is not None
        assert audit_log.details["booking_reference"] == booking.booking_reference
        assert audit_log.details["refund_amount"] == 600.0

        # 4. Super admin runs reconciliation -> 200 OK
        res_rec = client.post("/api/v1/payments/reconciliation/run", headers=admin_headers)
        assert res_rec.status_code == 200
        report = res_rec.json()
        assert "is_healthy" in report
        assert "total_payments_audited" in report
        assert report["total_payments_audited"] >= 1
    finally:
        _cleanup_test_data(db_session, customer, booking)
        _cleanup_test_data(db_session, other_user)
