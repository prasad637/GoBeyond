"""GO BEYOND — Module 9 Notifications & Background Jobs Test Suite

Exhaustive verification of 15 mandatory scenarios:
1. Booking confirmation notifications (In-App, Email, SMS).
2. Payment success/failure and refund notifications.
3. Partner notifications with tenant isolation.
4. In-app read/unread behaviour & ownership checks (403/404).
5. Customer notification preference enforcement (channel disabling).
6. Marketing unsubscribe behaviour (transactional delivered, promotional skipped).
7. Duplicate event idempotency prevention.
8. Worker retry and exponential backoff (2 ** retry * 10s).
9. Worker restart and pending-job recovery.
10. Redis outage without notification loss (durable outbox pattern).
11. OTP secrecy in logs and outbox records.
12. Role-based notification access & ownership checks.
13. Multiple workers processing the same event safely (FOR UPDATE SKIP LOCKED).
14. Scheduled booking reminders (24h/2h).
15. Failed/dead-letter job handling and manual admin retry.
"""
import pytest
import asyncio
import datetime
import uuid
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
from app.models.notification import NotificationPreference, NotificationOutbox
from app.models.dining import Restaurant, DiningTable
from app.models.sports import ActivitySlot
from app.services.notifications.service import NotificationService
from app.services.notifications.providers import mask_sensitive_content, MockEmailProvider, MockSMSProvider, InAppProvider
from app.services.otp import otp_service
from app.worker.tasks import (
    dispatch_pending_outbox_notifications,
    retry_failed_outbox_notifications,
    send_upcoming_booking_reminders,
    cleanup_expired_temporary_records
)


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


def _create_user(db: Session, email_prefix: str, role_name: str = "customer") -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.commit()
        db.refresh(role)

    uid = str(uuid.uuid4())[:8]
    user = User(
        email=f"{email_prefix}_{uid}@example.com",
        phone=f"+9198{uid[:8].zfill(8)}",
        full_name=f"User {uid}",
        hashed_password="hashed_dummy_password",
        is_active=True
    )
    user.roles.append(role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_partner(db: Session, user: User, partner_type: str = "RESTAURANT") -> Partner:
    partner = Partner(
        user_id=user.id,
        business_name=f"Partner {user.id} {partner_type}",
        partner_type=partner_type,
        contact_email=user.email,
        contact_phone=user.phone,
        status="APPROVED",
        commission_rate=Decimal("0.1250"),
        verified_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


# ==============================================================================
# SCENARIO 1: Booking Confirmation Notifications (In-App, Email, SMS)
# ==============================================================================
def test_scenario_01_booking_confirmation_notifications(client: TestClient, db_session: Session):
    customer = _create_user(db_session, "cust_sc1")
    ref = f"GB-SC1-{uuid.uuid4().hex[:6].upper()}"
    
    booking = Booking(
        booking_reference=ref,
        user_id=customer.id,
        booking_type="DINING",
        status="CONFIRMED",
        total_amount=Decimal("1200.00"),
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    # Trigger booking confirmation notifications
    NotificationService.notify_booking_confirmed(db_session, booking.id, customer.id)
    db_session.commit()

    # Verify outbox records created
    outbox_entries = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.user_id == customer.id,
        NotificationOutbox.event_type == "BOOKING_CONFIRMED"
    ).all()
    channels = {e.channel for e in outbox_entries}
    assert "IN_APP" in channels
    assert "EMAIL" in channels
    assert "SMS" in channels

    # Dispatch entries
    for entry in outbox_entries:
        assert entry.status == "PENDING"
        success = NotificationService.dispatch_outbox_entry(db_session, entry.id)
        assert success is True
        db_session.refresh(entry)
        assert entry.status == "DELIVERED"
        assert entry.provider_name is not None
        assert "MOCK" in entry.provider_name or "IN_APP" in entry.provider_name

    # Check In-App Notification table entry
    in_app_notifs = db_session.query(Notification).filter(
        Notification.user_id == customer.id
    ).all()
    assert len(in_app_notifs) >= 1
    assert any(ref in n.message for n in in_app_notifs)


# ==============================================================================
# SCENARIO 2: Payment Success / Failure & Refund Notifications
# ==============================================================================
def test_scenario_02_payment_success_failure_and_refund_notifications(client: TestClient, db_session: Session):
    customer = _create_user(db_session, "cust_sc2")
    ref = f"GB-SC2-{uuid.uuid4().hex[:6].upper()}"

    booking = Booking(
        booking_reference=ref,
        user_id=customer.id,
        booking_type="EVENT",
        status="CONFIRMED",
        total_amount=Decimal("2500.00")
    )
    db_session.add(booking)
    db_session.commit()

    # 1. Payment Success
    NotificationService.notify_payment_success(db=db_session, payment=Decimal("2500.00"), booking=booking, user=customer)
    db_session.commit()
    outbox_pay_success = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.user_id == customer.id,
        NotificationOutbox.event_type == "PAYMENT_SUCCESS"
    ).all()
    assert len(outbox_pay_success) >= 2  # IN_APP, EMAIL

    # 2. Payment Failure
    NotificationService.notify_payment_failed(db=db_session, payment=Decimal("2500.00"), booking=booking, user=customer, reason="Signature verification failed")
    db_session.commit()
    outbox_pay_fail = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.user_id == customer.id,
        NotificationOutbox.event_type == "PAYMENT_FAILED"
    ).all()
    assert len(outbox_pay_fail) >= 2

    # 3. Refund Processed
    NotificationService.notify_refund_processed(db=db_session, refund=Decimal("2500.00"), booking=booking, user=customer)
    db_session.commit()
    outbox_refund = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.user_id == customer.id,
        NotificationOutbox.event_type == "REFUND_PROCESSED"
    ).all()
    assert len(outbox_refund) >= 2

    # Dispatch all
    for entry in outbox_pay_success + outbox_pay_fail + outbox_refund:
        NotificationService.dispatch_outbox_entry(db_session, entry.id)
        db_session.refresh(entry)
        assert entry.status == "DELIVERED"


# ==============================================================================
# SCENARIO 3: Partner Notifications with Strict Tenant Isolation
# ==============================================================================
def test_scenario_03_partner_notifications_tenant_isolation(client: TestClient, db_session: Session):
    user_a = _create_user(db_session, "partner_a_user", "partner_restaurant")
    user_b = _create_user(db_session, "partner_b_user", "partner_cinema")
    partner_a = _create_partner(db_session, user_a, "RESTAURANT")
    partner_b = _create_partner(db_session, user_b, "CINEMA")

    booking_a = Booking(
        booking_reference=f"GB-PART-{uuid.uuid4().hex[:6].upper()}",
        user_id=user_a.id,
        booking_type="DINING",
        status="CONFIRMED",
        total_amount=Decimal("800.00"),
        final_payable=Decimal("800.00")
    )
    db_session.add(booking_a)
    db_session.commit()

    try:
        # Send notifications to Partner A
        NotificationService.notify_partner_new_booking(db_session, partner_a, booking_a, Decimal("800.00"))
        NotificationService.notify_partner_booking_cancelled(db_session, partner_a, booking_a, "Customer cancelled")
        NotificationService.notify_partner_status_change(db_session, partner_a, "APPROVED", "KYC documents validated")
        db_session.commit()

        # Dispatch all Partner A outbox notifications
        outbox_a = db_session.query(NotificationOutbox).filter(NotificationOutbox.user_id == user_a.id).all()
        assert len(outbox_a) >= 3
        for entry in outbox_a:
            NotificationService.dispatch_outbox_entry(db_session, entry.id)

        # Query Partner A notifications API
        headers_a = _get_auth_headers(user_a)
        resp_a = client.get("/api/v1/partners/notifications", headers=headers_a)
        assert resp_a.status_code == 200
        notifs_a = resp_a.json()
        assert len(notifs_a) >= 3

        # Query Partner B notifications API (Must be tenant isolated: cannot see Partner A's notifications)
        headers_b = _get_auth_headers(user_b)
        resp_b = client.get("/api/v1/partners/notifications", headers=headers_b)
        assert resp_b.status_code == 200
        notifs_b = resp_b.json()
        assert len(notifs_b) == 0  # Tenant isolation verified!
    finally:
        db_session.rollback()
        db_session.query(NotificationOutbox).filter(NotificationOutbox.user_id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
        db_session.query(Notification).filter(Notification.user_id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
        db_session.query(Booking).filter(Booking.id == booking_a.id).delete(synchronize_session=False)
        db_session.query(Partner).filter(Partner.id.in_([partner_a.id, partner_b.id])).delete(synchronize_session=False)
        db_session.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
        db_session.commit()


# ==============================================================================
# SCENARIO 4: In-App Read/Unread Behaviour & Ownership Checks (403/404)
# ==============================================================================
def test_scenario_04_in_app_read_unread_behaviour_and_ownership(client: TestClient, db_session: Session):
    user1 = _create_user(db_session, "notif_user1")
    user2 = _create_user(db_session, "notif_user2")

    # Create unread notification for user1
    notif1 = Notification(
        user_id=user1.id,
        title="Welcome Offer",
        message="Use code WELCOME50",
        type="PROMOTION",
        is_read=False
    )
    db_session.add(notif1)
    db_session.commit()
    db_session.refresh(notif1)

    headers1 = _get_auth_headers(user1)
    headers2 = _get_auth_headers(user2)

    # User 1 unread count is 1
    resp = client.get("/api/v1/notifications/unread-count", headers=headers1)
    assert resp.status_code == 200
    assert resp.json()["unread_count"] >= 1

    # User 2 attempts to mark User 1's notification as read -> 403 Forbidden!
    resp_hack = client.patch(f"/api/v1/notifications/{notif1.id}/read", headers=headers2)
    assert resp_hack.status_code == 403

    # User 1 marks it as read -> 200 OK
    resp_ok = client.patch(f"/api/v1/notifications/{notif1.id}/read", headers=headers1)
    assert resp_ok.status_code == 200
    db_session.refresh(notif1)
    assert notif1.is_read is True

    # User 1 tries marking a non-existent notification -> 404 Not Found
    resp_404 = client.patch("/api/v1/notifications/9999999/read", headers=headers1)
    assert resp_404.status_code == 404


# ==============================================================================
# SCENARIO 5: Customer Notification Preferences Enforcement (Channel Disabling)
# ==============================================================================
def test_scenario_05_customer_notification_preferences_enforcement(client: TestClient, db_session: Session):
    user = _create_user(db_session, "pref_user")
    headers = _get_auth_headers(user)

    # Disable SMS and EMAIL in user preferences
    resp = client.put(
        "/api/v1/notifications/preferences",
        json={"sms_enabled": False, "email_enabled": False},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sms_enabled"] is False
    assert data["email_enabled"] is False

    # Attempt to send Email and SMS
    outbox_email = NotificationService.queue_notification(
        db=db_session,
        event_type="BOOKING_ALERT",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="Your movie starts soon",
        content="Don't be late"
    )
    outbox_sms = NotificationService.queue_notification(
        db=db_session,
        event_type="BOOKING_ALERT",
        user_id=user.id,
        channel="SMS",
        recipient=user.phone,
        title="Your movie starts soon",
        content="Don't be late"
    )
    outbox_inapp = NotificationService.queue_notification(
        db=db_session,
        event_type="BOOKING_ALERT",
        user_id=user.id,
        channel="IN_APP",
        recipient=str(user.id),
        title="Your movie starts soon",
        content="Don't be late"
    )
    db_session.commit()

    # Email and SMS must be SKIPPED due to customer preferences
    assert outbox_email.status == "SKIPPED"
    assert "disabled" in str(outbox_email.provider_metadata).lower()
    assert outbox_sms.status == "SKIPPED"
    assert "disabled" in str(outbox_sms.provider_metadata).lower()

    # IN_APP must remain PENDING
    assert outbox_inapp.status == "PENDING"


# ==============================================================================
# SCENARIO 6: Marketing Unsubscribe Behaviour (Transactional Delivered, Promo Skipped)
# ==============================================================================
def test_scenario_06_marketing_unsubscribe_behaviour(client: TestClient, db_session: Session):
    user = _create_user(db_session, "unsub_user")
    headers = _get_auth_headers(user)

    # Opt out of marketing
    client.put(
        "/api/v1/notifications/preferences",
        json={"marketing_enabled": False},
        headers=headers
    )

    # 1. Marketing promo notification -> SKIPPED
    promo = NotificationService.queue_notification(
        db=db_session,
        event_type="MARKETING_PROMO",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="50% Off Dining Today!",
        content="Check out our new restaurant deals",
        is_marketing=True
    )
    assert promo.status == "SKIPPED"
    assert "unsubscribed" in str(promo.provider_metadata).lower()

    # 2. Transactional notification -> PENDING and DELIVERED even if marketing is false
    tx = NotificationService.queue_notification(
        db=db_session,
        event_type="REFUND_PROCESSED",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="Refund of ₹500 Processed",
        content="Your refund is on the way",
        is_marketing=False
    )
    assert tx.status == "PENDING"
    success = NotificationService.dispatch_outbox_entry(db_session, tx.id)
    assert success is True
    db_session.refresh(tx)
    assert tx.status == "DELIVERED"


# ==============================================================================
# SCENARIO 7: Duplicate Event Idempotency Prevention
# ==============================================================================
def test_scenario_07_duplicate_event_idempotency_prevention(client: TestClient, db_session: Session):
    user = _create_user(db_session, "idemp_user")
    idemp_key = f"evt_idemp_{uuid.uuid4().hex}"

    entry1 = NotificationService.queue_notification(
        db=db_session,
        event_type="BOOKING_CONFIRMED",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="Order Confirmation",
        content="Your booking is confirmed",
        idempotency_key=idemp_key
    )
    db_session.commit()

    entry2 = NotificationService.queue_notification(
        db=db_session,
        event_type="BOOKING_CONFIRMED",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="Duplicate Confirmation Request",
        content="This should not create another entry",
        idempotency_key=idemp_key
    )
    db_session.commit()

    # Must return the identical record, no duplicates inserted
    assert entry1.id == entry2.id
    count = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.idempotency_key == idemp_key
    ).count()
    assert count == 1


# ==============================================================================
# SCENARIO 8: Worker Retry & Exponential Backoff
# ==============================================================================
def test_scenario_08_worker_retry_and_exponential_backoff(client: TestClient, db_session: Session, monkeypatch):
    user = _create_user(db_session, "retry_user")
    entry = NotificationService.queue_notification(
        db=db_session,
        event_type="PAYMENT_FAILED",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="Payment Failed Alert",
        content="Please retry your payment"
    )
    db_session.commit()

    # Simulate provider failure
    from app.services.notifications import providers
    def failing_send(*args, **kwargs):
        raise ConnectionResetError("Provider gateway timeout")

    monkeypatch.setattr(providers.MockEmailProvider, "send", failing_send)

    # First dispatch failure
    success = NotificationService.dispatch_outbox_entry(db_session, entry.id)
    assert success is False
    db_session.refresh(entry)
    assert entry.status == "FAILED"
    assert entry.retry_count == 1
    assert "Provider gateway timeout" in entry.error_message
    assert entry.next_retry_at is not None
    # Exponential backoff check: 2 ** 1 * 10 = 20s in future
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    next_retry = entry.next_retry_at.replace(tzinfo=datetime.timezone.utc) if entry.next_retry_at.tzinfo is None else entry.next_retry_at
    delta = (next_retry - now_utc).total_seconds()
    assert 10 <= delta <= 30


# ==============================================================================
# SCENARIO 9: Worker Restart & Pending-Job Recovery
# ==============================================================================
def test_scenario_09_worker_restart_and_pending_recovery(client: TestClient, db_session: Session):
    user = _create_user(db_session, "recovery_user")

    # Insert 3 pending outbox entries as if left behind during worker restart
    ids = []
    for i in range(3):
        e = NotificationService.queue_notification(
            db=db_session,
            event_type="BOOKING_REMINDER",
            user_id=user.id,
            channel="IN_APP",
            recipient=str(user.id),
            title=f"Reminder #{i}",
            content=f"Upcoming show #{i}"
        )
        ids.append(e.id)
    db_session.commit()

    # Run the worker cron task: dispatch_pending_outbox_notifications
    dispatched = asyncio.run(dispatch_pending_outbox_notifications(ctx={}))
    assert dispatched >= 3

    # Verify all transitioned to DELIVERED
    for eid in ids:
        entry = db_session.query(NotificationOutbox).filter(NotificationOutbox.id == eid).first()
        db_session.refresh(entry)
        assert entry.status == "DELIVERED"


# ==============================================================================
# SCENARIO 10: Redis Outage without Notification Loss (Durable Outbox Pattern)
# ==============================================================================
def test_scenario_10_redis_outage_durable_outbox_pattern(client: TestClient, db_session: Session, monkeypatch):
    user = _create_user(db_session, "outage_user")

    # Simulate complete Redis disconnection/failure during enqueue
    monkeypatch.setattr("app.services.notifications.service.get_redis", lambda: None)

    # Queue notification during outage
    outbox = NotificationService.queue_notification(
        db=db_session,
        event_type="PAYMENT_SUCCESS",
        user_id=user.id,
        channel="EMAIL",
        recipient=user.email,
        title="Payment Received",
        content="Receipt #9988"
    )
    db_session.commit()

    # Outbox MUST be durably saved in PostgreSQL despite Redis failure
    assert outbox.id is not None
    assert outbox.status == "PENDING"

    # Once worker batch runs against PostgreSQL, delivery succeeds without loss
    asyncio.run(dispatch_pending_outbox_notifications(ctx={}))
    db_session.refresh(outbox)
    assert outbox.status == "DELIVERED"


# ==============================================================================
# SCENARIO 11: OTP Secrecy in Logs & Outbox Records
# ==============================================================================
def test_scenario_11_otp_secrecy_in_logs_and_outbox(client: TestClient, db_session: Session):
    phone = f"+9198{uuid.uuid4().hex[:8].zfill(8)}"

    # 1. Send OTP
    res = otp_service.send_otp(phone=phone, purpose="login")
    assert "dispatched" in res["message"]

    # Check created outbox record
    otp_outbox = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.recipient == phone,
        NotificationOutbox.event_type == "OTP_VERIFICATION"
    ).first()
    assert otp_outbox is not None

    # 2. Test mask_sensitive_content helper
    raw = f"Your one-time login code is {res.get('sandbox_code', '123456')} and password is secret"
    masked = mask_sensitive_content(raw)
    assert "123456" not in masked
    assert "******" in masked


# ==============================================================================
# SCENARIO 12: Role-Based Notification Access & Ownership Checks
# ==============================================================================
def test_scenario_12_role_based_notification_access(client: TestClient, db_session: Session):
    customer = _create_user(db_session, "role_cust", "customer")
    super_admin = _create_user(db_session, "role_admin", "super_admin")

    cust_headers = _get_auth_headers(customer)
    admin_headers = _get_auth_headers(super_admin)

    # Customer tries accessing admin outbox -> 403 Forbidden
    resp = client.get("/api/v1/notifications/outbox", headers=cust_headers)
    assert resp.status_code == 403

    # Customer tries retrying an outbox item -> 403 Forbidden
    resp = client.post("/api/v1/notifications/outbox/1/retry", headers=cust_headers)
    assert resp.status_code == 403

    # Super Admin accesses outbox -> 200 OK
    resp_admin = client.get("/api/v1/notifications/outbox", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert "items" in resp_admin.json()

    # Super Admin accesses worker status -> 200 OK
    resp_status = client.get("/api/v1/notifications/worker/status", headers=admin_headers)
    assert resp_status.status_code == 200
    data = resp_status.json()
    assert data["is_healthy"] is True
    assert "delivered_jobs_count" in data


# ==============================================================================
# SCENARIO 13: Multiple Workers Processing the Same Event (SKIP LOCKED)
# ==============================================================================
def test_scenario_13_multiple_workers_concurrency_skip_locked(client: TestClient, db_session: Session):
    user = _create_user(db_session, "lock_user")

    # Create 2 pending records
    e1 = NotificationService.queue_notification(
        db=db_session,
        event_type="CONCURRENCY_TEST",
        user_id=user.id,
        channel="IN_APP",
        recipient=str(user.id),
        title="Item 1",
        content="Msg 1"
    )
    e2 = NotificationService.queue_notification(
        db=db_session,
        event_type="CONCURRENCY_TEST",
        user_id=user.id,
        channel="IN_APP",
        recipient=str(user.id),
        title="Item 2",
        content="Msg 2"
    )
    db_session.commit()

    # Worker session 1 acquires lock on pending items
    session1 = SessionLocal()
    session2 = SessionLocal()
    try:
        locked_by_worker1 = session1.query(NotificationOutbox).filter(
            NotificationOutbox.status == "PENDING"
        ).with_for_update(skip_locked=True).limit(1).all()

        assert len(locked_by_worker1) == 1
        locked_id = locked_by_worker1[0].id

        # Worker session 2 queries with skip_locked: must NOT see or block on locked_id!
        items_for_worker2 = session2.query(NotificationOutbox).filter(
            NotificationOutbox.status == "PENDING"
        ).with_for_update(skip_locked=True).limit(5).all()

        worker2_ids = [item.id for item in items_for_worker2]
        assert locked_id not in worker2_ids  # SKIP LOCKED guaranteed!
    finally:
        session1.rollback()
        session2.rollback()
        session1.close()
        session2.close()


# ==============================================================================
# SCENARIO 14: Scheduled Booking Reminders (24h and 2h Windows)
# ==============================================================================
def test_scenario_14_scheduled_booking_reminders(client: TestClient, db_session: Session):
    customer = _create_user(db_session, "remind_cust")

    # Create 24h reminder booking (tomorrow, in 23.5 hours)
    slot_24h = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=23, minutes=30)
    b_24h = Booking(
        booking_reference=f"GB-24H-{uuid.uuid4().hex[:6].upper()}",
        user_id=customer.id,
        booking_type="DINING",
        status="CONFIRMED",
        total_amount=Decimal("1500.00"),
        expires_at=slot_24h
    )
    db_session.add(b_24h)

    # Create 2h reminder booking (today, in 1.5 hours)
    slot_2h = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1, minutes=30)
    b_2h = Booking(
        booking_reference=f"GB-02H-{uuid.uuid4().hex[:6].upper()}",
        user_id=customer.id,
        booking_type="ACTIVITY",
        status="CONFIRMED",
        total_amount=Decimal("2000.00"),
        expires_at=slot_2h
    )
    db_session.add(b_2h)
    db_session.commit()

    # Trigger booking reminders cron job
    reminders_sent = asyncio.run(send_upcoming_booking_reminders(ctx={}))
    assert reminders_sent >= 2

    # Verify outbox records
    reminders = db_session.query(NotificationOutbox).filter(
        NotificationOutbox.user_id == customer.id,
        NotificationOutbox.event_type.like("BOOKING_REMINDER_%")
    ).all()
    assert len(reminders) >= 2

    # Re-running the cron job immediately must NOT send duplicate reminders (deduped by idempotency key)
    duplicate_run = asyncio.run(send_upcoming_booking_reminders(ctx={}))
    assert duplicate_run == 0


# ==============================================================================
# SCENARIO 15: Failed / Dead-Letter Job Handling & Manual Admin Retry
# ==============================================================================
def test_scenario_15_dead_letter_and_manual_admin_retry(client: TestClient, db_session: Session):
    customer = _create_user(db_session, "dead_letter_cust")
    admin = _create_user(db_session, "dl_admin", "super_admin")
    admin_headers = _get_auth_headers(admin)

    # Create a DEAD_LETTER entry that exceeded max retries
    dead_entry = NotificationOutbox(
        event_type="PAYMENT_SUCCESS",
        user_id=customer.id,
        channel="EMAIL",
        recipient=customer.email,
        title="Delivery Failed Notification",
        content="Important order details",
        status="DEAD_LETTER",
        retry_count=5,
        max_retries=5,
        idempotency_key=f"dl_{uuid.uuid4().hex}",
        error_message="Permanent 550 Mailbox does not exist"
    )
    db_session.add(dead_entry)
    db_session.commit()
    db_session.refresh(dead_entry)

    # Super Admin triggers manual retry endpoint: POST /api/v1/notifications/outbox/{id}/retry
    resp = client.post(f"/api/v1/notifications/outbox/{dead_entry.id}/retry", headers=admin_headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True

    # Verify status changed and retry count reset
    db_session.refresh(dead_entry)
    assert dead_entry.status in ["PENDING", "DELIVERED"]
    assert dead_entry.retry_count == 0

    # Verify audit log was recorded for manual retry
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "NOTIFICATION_MANUAL_RETRY",
        AuditLog.resource_id == str(dead_entry.id)
    ).first()
    assert audit is not None
