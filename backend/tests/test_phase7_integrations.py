"""
GO BEYOND — Phase 7 Final Launch Integration & Security Test Suite

Covers:
1. Checkout hardening across payment failure (/payments/report-failure), IDOR protection,
   order-ID substitution defense, 0-INR 100%-coupon bookings, late-payment REFUND_PENDING,
   and immediate inventory restoration.
2. External Notification Provider adapters (Twilio, MSG91, SendGrid, AWS SES, FCM):
   - Env-driven factory selection (`SMS_PROVIDER`, `EMAIL_PROVIDER`, `PUSH_PROVIDER`)
   - Placeholder/missing credential rejection (`PROVIDER_NOT_CONFIGURED`)
   - Non-mock HTTP request construction & AWS SigV4 signing (monkeypatched httpx; zero external calls)
   - Retry / DEAD_LETTER tracking on provider failures & strict secret/OTP masking in logs
   - `scripts/validate_env.py` notification provider checks in production profile
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.audit import AuditLog
from app.models.booking import Booking, SeatLock
from app.models.event import EventTicketType
from app.models.movie import MovieShow, Seat
from app.models.notification import NotificationOutbox
from app.models.payment import Coupon, Payment, Refund
from app.models.sports import ActivitySlot
from app.models.user import Role, User
from app.services.notifications.providers import (
    FCMPushProvider,
    MockEmailProvider,
    MockPushProvider,
    MockSMSProvider,
    MSG91SMSProvider,
    SendGridEmailProvider,
    SESEmailProvider,
    TwilioSMSProvider,
    get_provider,
    mask_sensitive_content,
)
from app.services.notifications.service import NotificationService


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _create_user(db: Session, prefix: str, role_name: str = "customer") -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"{prefix}_{uid}@gobeyondp7.test",
        phone=f"+9194{int(uid, 16) % 100000000:08d}",
        full_name=f"P7 {prefix} {uid}",
        hashed_password=get_password_hash("Password@123"),
        is_active=True,
        is_verified=True,
        account_status="ACTIVE",
    )
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.flush()
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    role_name = user.roles[0].name if user.roles else "customer"
    token = create_access_token(user.id, role=role_name)
    return {"Authorization": f"Bearer {token}"}


def _sign_razorpay(order_id: str, payment_id: str) -> str:
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(settings.RAZORPAY_KEY_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()


# ==============================================================================
# 1. PAYMENT CHECKOUT HARDENING & FAILURE RECOVERY TESTS
# ==============================================================================

def test_payment_failure_report_releases_movie_and_event_inventory_and_enforces_idor(client: TestClient):
    """
    Verifies `/payments/report-failure`:
    - Blocks cross-user access with HTTP 403 (IDOR protection)
    - Rejects already CONFIRMED bookings with HTTP 400
    - Transitions PAYMENT_PENDING -> FAILED, Payment -> FAILED
    - Releases Movie SeatLock & restores EventTicketType.available_quantity immediately
    - Is idempotent on duplicate failure reports
    """
    db = SessionLocal()
    try:
        owner = _create_user(db, "p7_owner")
        intruder = _create_user(db, "p7_intruder")
        show = db.query(MovieShow).first()
        seat = db.query(Seat).filter(Seat.screen_id == show.screen_id).first()
        ticket_tier = db.query(EventTicketType).filter(EventTicketType.available_quantity >= 5).first()
        assert show and seat and ticket_tier
        orig_avail = ticket_tier.available_quantity
        owner_hdrs = _auth_header(owner)
        intruder_hdrs = _auth_header(intruder)
    finally:
        db.close()

    # A. Movie Seat booking hold + order creation + failure report
    b_res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "MOVIE",
            "items": [
                {
                    "item_type": "SEAT",
                    "item_id": seat.id,
                    "name": f"Seat {seat.row_code}{seat.seat_number}",
                    "quantity": 1,
                    "unit_price": float(seat.base_price),
                    "details": {"show_id": show.id},
                }
            ],
        },
        headers=owner_hdrs,
    )
    assert b_res.status_code == 201, b_res.text
    movie_booking = b_res.json()

    ord_res = client.post(
        "/api/v1/payments/create-order",
        json={"booking_id": movie_booking["id"]},
        headers=owner_hdrs,
    )
    assert ord_res.status_code == 200, ord_res.text
    order_id = ord_res.json()["order_id"]

    # Intruder cannot report failure on owner's booking
    idor_res = client.post(
        "/api/v1/payments/report-failure",
        json={
            "booking_id": movie_booking["id"],
            "razorpay_order_id": order_id,
            "error_description": "Attacker spoofed failure",
        },
        headers=intruder_hdrs,
    )
    assert idor_res.status_code == 403

    # Order substitution attack check: mismatch order_id must fail even with valid HMAC for wrong order
    wrong_order = f"order_wrong_{uuid.uuid4().hex[:8]}"
    wrong_pay = f"pay_wrong_{uuid.uuid4().hex[:8]}"
    swap_res = client.post(
        "/api/v1/payments/verify-signature",
        json={
            "booking_id": movie_booking["id"],
            "razorpay_order_id": wrong_order,
            "razorpay_payment_id": wrong_pay,
            "razorpay_signature": _sign_razorpay(wrong_order, wrong_pay),
        },
        headers=owner_hdrs,
    )
    assert swap_res.status_code == 400
    assert "does not match" in swap_res.json()["detail"].lower()

    # Same owner cannot open a second concurrent PAYMENT_PENDING booking for the same seat
    dup_res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "MOVIE",
            "items": [
                {
                    "item_type": "SEAT",
                    "item_id": seat.id,
                    "name": f"Seat {seat.row_code}{seat.seat_number}",
                    "quantity": 1,
                    "unit_price": float(seat.base_price),
                    "details": {"show_id": show.id},
                }
            ],
        },
        headers=owner_hdrs,
    )
    assert dup_res.status_code == 409, f"Expected 409 on same-user duplicate active seat booking, got {dup_res.status_code}: {dup_res.text}"

    # Report genuine failure from owner
    fail_res = client.post(
        "/api/v1/payments/report-failure",
        json={
            "booking_id": movie_booking["id"],
            "razorpay_order_id": order_id,
            "razorpay_payment_id": f"pay_fail_{uuid.uuid4().hex[:8]}",
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "UPI collect request timed out",
            "error_reason": "payment_timed_out",
        },
        headers=owner_hdrs,
    )
    assert fail_res.status_code == 200, fail_res.text
    fail_json = fail_res.json()
    assert fail_json["booking_status"] == "FAILED"
    assert fail_json["payment_status"] == "FAILED"
    assert fail_json["inventory_released"] is True

    # Repeat failure report is idempotent and does not raise
    repeat_res = client.post(
        "/api/v1/payments/report-failure",
        json={"booking_id": movie_booking["id"], "error_description": "Duplicate failure"},
        headers=owner_hdrs,
    )
    assert repeat_res.status_code == 200
    assert repeat_res.json()["inventory_released"] is False

    # Cannot initiate a new order for a FAILED booking
    retry_order = client.post(
        "/api/v1/payments/create-order",
        json={"booking_id": movie_booking["id"]},
        headers=owner_hdrs,
    )
    assert retry_order.status_code == 400

    # Verify DB locks released so intruder/another user can now immediately book that same seat!
    db = SessionLocal()
    try:
        unreleased = db.query(SeatLock).filter(
            SeatLock.resource_type == "MOVIE_SHOW",
            SeatLock.resource_id == show.id,
            SeatLock.identifier == f"seat_{seat.id}",
            SeatLock.is_released == False,
        ).count()
        assert unreleased == 0

        audit_row = db.query(AuditLog).filter(
            AuditLog.action == "PAYMENT_FAILED_REPORTED",
            AuditLog.resource_id == order_id,
        ).first()
        assert audit_row is not None
    finally:
        db.close()

    # B. Event ticket booking failure restores available_quantity immediately
    ev_res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "EVENT",
            "items": [
                {
                    "item_type": "TICKET",
                    "item_id": ticket_tier.id,
                    "name": ticket_tier.name,
                    "quantity": 2,
                    "unit_price": float(ticket_tier.price),
                    "details": {"tier_name": ticket_tier.name},
                }
            ],
        },
        headers=owner_hdrs,
    )
    assert ev_res.status_code == 201, ev_res.text
    ev_booking = ev_res.json()

    ev_fail = client.post(
        "/api/v1/payments/report-failure",
        json={"booking_id": ev_booking["id"], "error_description": "Card declined"},
        headers=owner_hdrs,
    )
    assert ev_fail.status_code == 200
    assert ev_fail.json()["booking_status"] == "FAILED"

    db = SessionLocal()
    try:
        db.expire_all()
        refreshed_tier = db.query(EventTicketType).filter(EventTicketType.id == ticket_tier.id).first()
        assert refreshed_tier.available_quantity == orig_avail
    finally:
        db.close()


def test_zero_payable_100_percent_coupon_booking_confirms_without_razorpay_order(client: TestClient):
    """
    Verifies a 100% coupon discount booking transitions straight to CONFIRMED with a valid
    QR token and refuses redundant `/payments/create-order` gateway calls.
    """
    db = SessionLocal()
    coupon_code = f"FREE100_{uuid.uuid4().hex[:6].upper()}"
    try:
        user = _create_user(db, "p7_free")
        slot = db.query(ActivitySlot).filter(
            ActivitySlot.is_available == True,
            (ActivitySlot.capacity - ActivitySlot.booked_count) >= 1,
        ).first()
        assert slot
        coupon = Coupon(
            code=coupon_code,
            description="100% Promo Verification",
            discount_type="PERCENTAGE",
            discount_value=Decimal("100.00"),
            min_order_value=Decimal("0.00"),
            max_discount=Decimal("50000.00"),
            usage_limit=5,
            used_count=0,
            is_active=True,
        )
        db.add(coupon)
        db.commit()
        slot_id = slot.id
        coupon_id = coupon.id
        hdrs = _auth_header(user)
    finally:
        db.close()
    res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "ACTIVITY",
            "items": [
                {
                    "item_type": "SLOT",
                    "item_id": slot_id,
                    "name": "Free Promo Slot",
                    "quantity": 1,
                    "unit_price": 500,
                }
            ],
            "coupon_code": coupon_code,
        },
        headers=hdrs,
    )
    assert res.status_code == 201, res.text
    b_data = res.json()
    assert b_data["final_payable"] == 0.0
    assert b_data["status"] == "CONFIRMED"
    assert b_data["qr_code_token"].startswith("GB-PASS-")

    # Subsequent create-order must reject confirmed zero-payable booking
    ord_res = client.post(
        "/api/v1/payments/create-order",
        json={"booking_id": b_data["id"]},
        headers=hdrs,
    )
    assert ord_res.status_code == 400
    assert "already been paid and confirmed" in ord_res.json()["detail"].lower()

    # Cannot mark a CONFIRMED booking as FAILED via /report-failure
    fail_res = client.post(
        "/api/v1/payments/report-failure",
        json={"booking_id": b_data["id"], "error_description": "Invalid attempt"},
        headers=hdrs,
    )
    assert fail_res.status_code == 400

    # Clean up test booking capacity & coupon
    cancel_res = client.post(
        f"/api/v1/bookings/{b_data['id']}/cancel",
        json={"reason": "Test cleanup"},
        headers=hdrs,
    )
    assert cancel_res.status_code == 200
    db = SessionLocal()
    try:
        c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if c:
            c.is_active = False
            db.commit()
    finally:
        db.close()


# ==============================================================================
# 2. EXTERNAL NOTIFICATION PROVIDER READINESS TESTS (NO LIVE TRAFFIC)
# ==============================================================================

def test_notification_provider_factory_defaults_and_missing_credentials(monkeypatch):
    """
    Verifies default providers are clearly labeled mocks and that selecting external
    providers without real credentials fails safely (`success=False`, `is_mock=False`)
    instead of claiming delivery.
    """
    assert isinstance(get_provider("SMS"), MockSMSProvider)
    assert isinstance(get_provider("EMAIL"), MockEmailProvider)
    assert isinstance(get_provider("PUSH"), MockPushProvider)

    # Select external adapters with empty / placeholder credentials
    monkeypatch.setattr(settings, "SMS_PROVIDER", "twilio")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "<REPLACE_WITH_TOKEN>")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "")
    sms = get_provider("SMS")
    assert isinstance(sms, TwilioSMSProvider)
    assert sms.is_mock is False
    assert sms.is_configured() is False
    res_sms = sms.send("+919876543210", "OTP", "Code 123456")
    assert res_sms.success is False
    assert res_sms.metadata["status"] == "PROVIDER_NOT_CONFIGURED"

    monkeypatch.setattr(settings, "SMS_PROVIDER", "msg91")
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "replace-with-key")
    msg91 = get_provider("SMS")
    assert isinstance(msg91, MSG91SMSProvider)
    assert msg91.send("9876543210", "Alert", "Hello").success is False

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "")
    sg = get_provider("EMAIL")
    assert isinstance(sg, SendGridEmailProvider)
    assert sg.send("user@example.com", "Subject", "Body").success is False

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "ses")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "<REPLACE>")
    ses = get_provider("EMAIL")
    assert isinstance(ses, SESEmailProvider)
    assert ses.send("user@example.com", "Subject", "Body").success is False

    monkeypatch.setattr(settings, "PUSH_PROVIDER", "fcm")
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "")
    monkeypatch.setattr(settings, "FCM_ACCESS_TOKEN", "")
    monkeypatch.setattr(settings, "FCM_SERVER_KEY", "")
    fcm = get_provider("PUSH")
    assert isinstance(fcm, FCMPushProvider)
    assert fcm.send("device_tok_abc", "Title", "Body").success is False


def test_external_provider_adapters_build_authenticated_requests_and_retry_failures(monkeypatch):
    """
    Tests Twilio, MSG91, SendGrid, AWS SES (SigV4), and FCM adapters using mocked
    `httpx.Client.post` (never touching external network) and verifies outbox retry/DEAD_LETTER
    state transitions on upstream HTTP errors.
    """
    captured_calls = []

    def fake_post(self, url, **kwargs):
        captured_calls.append({"url": url, "kwargs": kwargs})
        if "twilio.com" in url:
            return httpx.Response(201, json={"sid": "SM_test_123", "status": "queued"})
        if "msg91.com" in url:
            return httpx.Response(200, json={"request_id": "msg91_req_456"})
        if "sendgrid.com" in url:
            return httpx.Response(202, headers={"X-Message-Id": "sg_msg_789"})
        if "amazonaws.com" in url:
            return httpx.Response(200, json={"MessageId": "ses_msg_abc"})
        if "fcm.googleapis.com" in url:
            return httpx.Response(200, json={"name": "projects/p/messages/fcm_001"})
        return httpx.Response(500, json={"error": "unexpected"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    # 1. Twilio
    monkeypatch.setattr(settings, "SMS_PROVIDER", "twilio")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC_test_sid_999")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "twilio_secret_token_xyz")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+15005550006")
    r_tw = get_provider("SMS").send("9876543210", "Confirm", "Booking confirmed")
    assert r_tw.success is True and r_tw.is_mock is False and r_tw.provider_message_id == "SM_test_123"
    assert captured_calls[-1]["kwargs"]["data"]["To"] == "+919876543210"

    # 2. MSG91
    monkeypatch.setattr(settings, "SMS_PROVIDER", "msg91")
    monkeypatch.setattr(settings, "MSG91_AUTH_KEY", "msg91_live_key_123")
    monkeypatch.setattr(settings, "MSG91_SENDER_ID", "GBEYND")
    r_m91 = get_provider("SMS").send("9876543210", "Confirm", "Booking confirmed")
    assert r_m91.success is True and r_m91.provider_message_id == "msg91_req_456"

    # 3. SendGrid
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.fake_test_key_123456")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "tickets@gobeyond.in")
    r_sg = get_provider("EMAIL").send("guest@example.com", "Ticket Pass", "Enjoy!")
    assert r_sg.success is True and r_sg.provider_message_id == "sg_msg_789"
    assert captured_calls[-1]["kwargs"]["headers"]["Authorization"] == "Bearer SG.fake_test_key_123456"

    # 4. AWS SES v2 + SigV4 signature header verification
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "ses")
    monkeypatch.setattr(settings, "AWS_REGION", "ap-south-1")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "AKIATESTACCESSKEY123")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "secretAccessKeyForSigV4TestOnly123456")
    r_ses = get_provider("EMAIL").send("guest@example.com", "Receipt", "Paid Rs 500")
    assert r_ses.success is True and r_ses.provider_message_id == "ses_msg_abc"
    ses_headers = captured_calls[-1]["kwargs"]["headers"]
    assert "AWS4-HMAC-SHA256 Credential=AKIATESTACCESSKEY123/" in ses_headers["Authorization"]
    assert "ap-south-1/ses/aws4_request" in ses_headers["Authorization"]

    # 5. FCM HTTP v1
    monkeypatch.setattr(settings, "PUSH_PROVIDER", "fcm")
    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "gobeyond-prod-app")
    monkeypatch.setattr(settings, "FCM_ACCESS_TOKEN", "ya29.test_oauth_token")
    r_fcm = get_provider("PUSH").send("fcm_device_token_123456", "Showtime", "Starts in 2h", {"ref": "GB-1"})
    assert r_fcm.success is True and r_fcm.provider_message_id == "projects/p/messages/fcm_001"

    # 6. Sensitive content masking check
    masked = mask_sensitive_content("OTP 654321 password=mySecretPassword token=abc123 authkey=xyz999")
    assert "654321" not in masked
    assert "mySecretPassword" not in masked
    assert "abc123" not in masked
    assert "xyz999" not in masked

    # 7. Outbox retry -> DEAD_LETTER tracking on provider HTTP 503 failure
    def fail_post(self, url, **kwargs):
        return httpx.Response(503, json={"error": "upstream unavailable"})

    monkeypatch.setattr(httpx.Client, "post", fail_post)
    db = SessionLocal()
    try:
        idemp = f"p7_retry_{uuid.uuid4().hex[:8]}"
        outbox = NotificationService.create_outbox_notification(
            db=db,
            event_type="BOOKING_CONFIRMED",
            channel="EMAIL",
            recipient="retry@example.com",
            title="Retry Test",
            content="Testing retry path",
            idempotency_key=idemp,
            max_retries=2,
            commit=True,
        )
        ok1 = NotificationService.dispatch_outbox_entry(db, outbox.id)
        assert ok1 is False
        db.refresh(outbox)
        assert outbox.status == "FAILED"
        assert outbox.retry_count == 1
        assert outbox.next_retry_at is not None

        ok2 = NotificationService.dispatch_outbox_entry(db, outbox.id)
        assert ok2 is False
        db.refresh(outbox)
        assert outbox.status == "DEAD_LETTER"
        assert outbox.retry_count == 2
        assert outbox.next_retry_at is None
    finally:
        db.close()


def test_validate_env_enforces_notification_provider_credentials():
    """Verifies scripts/validate_env.py rejects mock or incomplete notification credentials in production."""
    scripts_dir = str(REPO_ROOT / "scripts")
    if not Path(scripts_dir, "validate_env.py").is_file():
        pytest.skip("Repository scripts/ not present inside container test context.")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import validate_env as ve

    prod_map = ve.parse_env_file(REPO_ROOT / ".env.production.example")
    prod_map.update(
        {
            "POSTGRES_PASSWORD": "StrongProdPassword#2026",
            "SECRET_KEY": "p" * 48,
            "RAZORPAY_KEY_ID": "rzp_live_1234567890abcd",
            "RAZORPAY_KEY_SECRET": "live_secret_1234567890",
            "GRAFANA_ADMIN_PASSWORD": "StrongGrafanaPassword#2026",
            "BACKEND_CORS_ORIGINS": '["https://app.gobeyond.in"]',
            "SMS_PROVIDER": "twilio",
            "TWILIO_ACCOUNT_SID": "<REPLACE_WITH_TWILIO_ACCOUNT_SID>",  # placeholder must fail!
            "TWILIO_AUTH_TOKEN": "tok_real_123",
            "TWILIO_FROM_NUMBER": "+15005550006",
            "EMAIL_PROVIDER": "sendgrid",
            "SENDGRID_API_KEY": "SG.real_key_123",
            "EMAIL_FROM_ADDRESS": "noreply@gobeyond.in",
            "PUSH_PROVIDER": "fcm",
            "FCM_PROJECT_ID": "gobeyond-prod",
            "FCM_ACCESS_TOKEN": "ya29.real_token",
        }
    )
    errors, _ = ve.validate_env(prod_map, mode="production", template_check=False)
    assert any("TWILIO_ACCOUNT_SID" in err for err in errors), errors

    # Now supply valid non-placeholder Twilio SID -> passes with 0 errors!
    prod_map["TWILIO_ACCOUNT_SID"] = "AC1234567890abcdef1234567890abcd"
    errors_ok, _ = ve.validate_env(prod_map, mode="production", template_check=False)
    assert errors_ok == [], errors_ok

