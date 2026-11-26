import uuid
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.locks import lock_service, LockService
from app.core.security import create_access_token
from app.models.user import User, RefreshToken
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.dining import Restaurant, DiningTable, DiningReservation
from app.models.sports import Activity, ActivitySlot
from app.models.event import EventTicketType
from app.models.payment import Payment
from app.worker.tasks import expire_stale_bookings

client = TestClient(app)


# 1. Short-lived Access Token & Single-Use Refresh Token Rotation
def test_refresh_token_rotation_single_use():
    suffix = uuid.uuid4().hex[:6]
    email = f"rotate_{suffix}@gobeyond.com"
    phone = f"98{suffix[:8].ljust(8, '1')}"

    # Register user
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "phone": phone,
            "full_name": "Rotation Test User",
            "password": "Password@123",
            "role": "customer"
        }
    )
    assert reg_res.status_code == 201
    refresh_cookie = reg_res.cookies.get("gobeyond_refresh_token")
    csrf_cookie = reg_res.cookies.get("gobeyond_csrf_token")
    assert refresh_cookie is not None
    assert csrf_cookie is not None

    # First rotation: Single-use success
    refresh_res = client.post(
        "/api/v1/auth/refresh",
        cookies={"gobeyond_refresh_token": refresh_cookie, "gobeyond_csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": csrf_cookie}
    )
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    new_refresh_cookie = refresh_res.cookies.get("gobeyond_refresh_token")
    assert new_refresh_cookie is not None
    assert new_refresh_cookie != refresh_cookie


# 2. Refresh Token Reuse Detection & Token Family Revocation
def test_refresh_token_reuse_detection_revokes_family():
    suffix = uuid.uuid4().hex[:6]
    email = f"reuse_{suffix}@gobeyond.com"
    phone = f"97{suffix[:8].ljust(8, '2')}"

    # Register user
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "phone": phone,
            "full_name": "Reuse Test User",
            "password": "Password@123",
            "role": "customer"
        }
    )
    assert reg_res.status_code == 201
    token_1 = reg_res.cookies.get("gobeyond_refresh_token")
    csrf_token = reg_res.cookies.get("gobeyond_csrf_token")

    # Rotate once -> token_1 becomes revoked, token_2 is issued
    ref_1 = client.post(
        "/api/v1/auth/refresh",
        cookies={"gobeyond_refresh_token": token_1, "gobeyond_csrf_token": csrf_token},
        headers={"X-CSRF-Token": csrf_token}
    )
    assert ref_1.status_code == 200
    token_2 = ref_1.cookies.get("gobeyond_refresh_token")
    new_csrf = ref_1.cookies.get("gobeyond_csrf_token") or csrf_token

    # ATTACK / REPLAY: Malicious actor or leaked client attempts to present token_1 again!
    replay_res = client.post(
        "/api/v1/auth/refresh",
        cookies={"gobeyond_refresh_token": token_1, "gobeyond_csrf_token": new_csrf},
        headers={"X-CSRF-Token": new_csrf}
    )
    assert replay_res.status_code == 401
    assert "Token reuse detected" in replay_res.json()["detail"]

    # Now verify that even token_2 is invalidated because the ENTIRE token family was revoked!
    ref_2 = client.post(
        "/api/v1/auth/refresh",
        cookies={"gobeyond_refresh_token": token_2, "gobeyond_csrf_token": new_csrf},
        headers={"X-CSRF-Token": new_csrf}
    )
    assert ref_2.status_code == 401


# 3. CSRF Protection on Token Endpoints
def test_csrf_mismatch_rejected():
    suffix = uuid.uuid4().hex[:6]
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"csrf_{suffix}@gobeyond.com",
            "phone": f"96{suffix[:8].ljust(8, '3')}",
            "full_name": "CSRF User",
            "password": "Password@123",
            "role": "customer"
        }
    )
    refresh_cookie = reg_res.cookies.get("gobeyond_refresh_token")
    csrf_cookie = reg_res.cookies.get("gobeyond_csrf_token")

    # Present wrong CSRF token header
    res = client.post(
        "/api/v1/auth/refresh",
        cookies={"gobeyond_refresh_token": refresh_cookie, "gobeyond_csrf_token": csrf_cookie},
        headers={"X-CSRF-Token": "tampered_csrf_token_value"}
    )
    assert res.status_code == 403
    assert "CSRF" in res.json()["detail"]


# 4. Redis Failure Handling: Fail-Safe 503 Policy
def test_redis_failure_fails_safe_outside_test_mode(monkeypatch):
    """
    Verifies that when ENVIRONMENT is 'integration_test' (or 'production') and Redis is unavailable,
    lock acquisition fails safely with 503 Service Unavailable,
    preventing unsafe silent in-memory fallback.
    """
    test_svc = LockService()
    test_svc.redis_client = None  # simulate Redis unavailable

    # Outside local test mode
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "integration_test")
    monkeypatch.setattr(settings, "REDIS_REQUIRED_IN_PRODUCTION", True)
    monkeypatch.setattr(settings, "USE_MEMORY_LOCK_FALLBACK", False)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        test_svc.acquire_lock("test_key", "token123", expiry_seconds=30)
    assert exc_info.value.status_code == 503
    assert "unavailable" in exc_info.value.detail.lower()


# 5. Redis Lock Ownership Verification (Lua compare-and-delete)
def test_lock_release_verifies_ownership_token():
    key = f"test_ownership_{uuid.uuid4().hex[:6]}"
    token_owner = "owner_token_abc"
    token_intruder = "intruder_token_xyz"

    # Acquire lock with token_owner
    acquired = lock_service.acquire_lock(key, token_owner, expiry_seconds=60)
    assert acquired is True

    # Intruder attempts to release -> must fail
    released_by_intruder = lock_service.release_lock(key, token_intruder)
    assert released_by_intruder is False

    # Owner releases -> succeeds
    released_by_owner = lock_service.release_lock(key, token_owner)
    assert released_by_owner is True


# 6. Database Partial Unique Index on Active Seat Locks
def test_database_partial_unique_seat_lock():
    db: Session = SessionLocal()
    try:
        user = db.query(User).first()
        res_id = 999
        ident = "Seat_X99"
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

        # First active lock
        lock1 = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=res_id,
            identifier=ident,
            user_id=user.id,
            lock_token="tok1",
            expires_at=exp,
            is_released=False
        )
        db.add(lock1)
        db.commit()

        # Second active lock on exact same seat -> must raise IntegrityError
        lock2 = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=res_id,
            identifier=ident,
            user_id=user.id,
            lock_token="tok2",
            expires_at=exp,
            is_released=False
        )
        db.add(lock2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # Clean up lock1
        db.query(SeatLock).filter(SeatLock.id == lock1.id).delete()
        db.commit()
    finally:
        db.rollback()
        db.query(SeatLock).filter(
            SeatLock.resource_type == "MOVIE_SHOW",
            SeatLock.resource_id == res_id,
            SeatLock.identifier == ident
        ).delete()
        db.commit()
        db.close()


# 7. Dining Reservation Overlap Protection (Duration + Buffer)
def test_dining_reservation_overlap_prevention():
    db: Session = SessionLocal()
    other_tables = []
    res1 = None
    try:
        rest = db.query(Restaurant).filter(Restaurant.is_active == True).first()
        table = rest.tables[0]
        user = db.query(User).first()

        # Ensure a booking exists for foreign key
        booking = db.query(Booking).first()
        if not booking:
            booking = Booking(
                booking_reference=f"GB-TEST-{uuid.uuid4().hex[:6].upper()}",
                user_id=user.id,
                booking_type="DINING",
                total_amount=0.0,
                final_payable=0.0,
                status="CONFIRMED"
            )
            db.add(booking)
            db.commit()

        # Deactivate any other tables so table.id is the ONLY available table for this test
        other_tables = db.query(DiningTable).filter(
            DiningTable.restaurant_id == rest.id,
            DiningTable.id != table.id
        ).all()
        for t in other_tables:
            t.is_active = False
        db.commit()

        test_date = (datetime.date.today() + datetime.timedelta(days=120))
        start_time = datetime.time(19, 0)
        start_dt = datetime.datetime.combine(test_date, start_time)
        end_dt = start_dt + datetime.timedelta(minutes=105)

        # Existing confirmed reservation
        res1 = DiningReservation(
            restaurant_id=rest.id,
            table_id=table.id,
            user_id=user.id,
            booking_id=booking.id,
            reservation_date=test_date,
            reservation_time=start_time,
            start_datetime=start_dt,
            end_datetime=end_dt,
            duration_minutes=90,
            buffer_minutes=15,
            guest_count=table.capacity,
            status="CONFIRMED"
        )
        db.add(res1)
        db.commit()

        # Attempt to book an overlapping time (19:30, within the 19:00 - 20:45 window)
        token = create_access_token(subject=user.id, role="customer")
        overlap_res = client.post(
            "/api/v1/dining/reserve",
            json={
                "restaurant_id": rest.id,
                "reservation_date": test_date.isoformat(),
                "reservation_time": "19:30:00",
                "guest_count": table.capacity
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be rejected with 409 Conflict because the only table is reserved
        assert overlap_res.status_code == 409
        assert "reserved or locked" in overlap_res.json()["detail"]
    finally:
        if res1 and res1.id:
            db.query(DiningReservation).filter(DiningReservation.id == res1.id).delete()
        for t in other_tables:
            t.is_active = True
        db.commit()
        db.close()


# 8. Activity Slot Capacity Limits & Atomic Protection
def test_activity_slot_capacity_enforcement():
    db: Session = SessionLocal()
    try:
        slot = db.query(ActivitySlot).first()
        act = slot.activity
        user = db.query(User).first()
        token = create_access_token(subject=user.id, role="customer")

        # Attempt to book exceeding capacity
        excess_qty = (slot.capacity - slot.booked_count) + 50
        res = client.post(
            "/api/v1/bookings/",
            json={
                "booking_type": "ACTIVITY",
                "items": [{
                    "item_type": "SLOT",
                    "item_id": slot.id,
                    "name": f"{act.title} - Slot",
                    "quantity": excess_qty,
                    "unit_price": float(act.base_price),
                    "details": {}
                }]
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 409
        assert "capacity" in res.json()["detail"].lower()
    finally:
        db.close()


# 9. Late Payment Defense: Re-Assigned Inventory Triggers REFUND_PENDING
def test_late_payment_on_reassigned_inventory_triggers_refund():
    db: Session = SessionLocal()
    booking = None
    active_lock = None
    try:
        # Clean any stale lock from previous failed run
        db.query(SeatLock).filter(SeatLock.identifier == "seat_777").delete()
        db.commit()

        user_victim = db.query(User).filter(User.id == 2).first()
        user_new = db.query(User).filter(User.id == 1).first()

        # Create expired booking for victim
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        booking = Booking(
            booking_reference=f"GB-EXP-{uuid.uuid4().hex[:6].upper()}",
            user_id=user_victim.id,
            booking_type="MOVIE",
            total_amount=300.0,
            tax_amount=54.0,
            discount_amount=0.0,
            final_payable=354.0,
            status="PAYMENT_PENDING",
            expires_at=past_time
        )
        db.add(booking)
        db.flush()

        item = BookingItem(
            booking_id=booking.id,
            item_type="SEAT",
            item_id=777,
            name="Seat Reassigned",
            quantity=1,
            unit_price=300.0,
            subtotal=300.0,
            details={"show_id": 1}
        )
        db.add(item)

        # Inventory was re-assigned to user_new via an active lock!
        active_lock = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=1,
            identifier="seat_777",
            user_id=user_new.id,
            lock_token="new_customer_token",
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
            is_released=False
        )
        db.add(active_lock)
        db.commit()

        # Victim's late payment callback arrives
        victim_token = create_access_token(subject=user_victim.id, role="customer")
        pay_res = client.post(
            "/api/v1/payments/verify-signature",
            json={
                "booking_id": booking.id,
                "razorpay_order_id": f"order_{uuid.uuid4().hex[:8]}",
                "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:8]}",
                "razorpay_signature": "mock_valid_signature_sandbox"
            },
            headers={"Authorization": f"Bearer {victim_token}"}
        )
        assert pay_res.status_code == 200
        pay_data = pay_res.json()
        # Must NOT be CONFIRMED! Must be REFUND_PENDING!
        assert pay_data["success"] is False
        assert pay_data["status"] == "REFUND_PENDING"
        assert "Automatic refund initiated" in pay_data["message"]

        # Verify database record
        db.refresh(booking)
        assert booking.status == "REFUND_PENDING"

    finally:
        db.query(SeatLock).filter(SeatLock.identifier == "seat_777").delete()
        if booking and booking.id:
            db.query(BookingItem).filter(BookingItem.booking_id == booking.id).delete()
            db.query(Payment).filter(Payment.booking_id == booking.id).delete()
            db.query(Booking).filter(Booking.id == booking.id).delete()
        db.commit()
        db.close()


# 10. Background Worker Booking Expiration
@pytest.mark.asyncio
async def test_worker_expire_stale_bookings():
    db: Session = SessionLocal()
    try:
        user = db.query(User).first()
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=20)
        stale_booking = Booking(
            booking_reference=f"GB-WRK-{uuid.uuid4().hex[:6].upper()}",
            user_id=user.id,
            booking_type="MOVIE",
            total_amount=200.0,
            final_payable=236.0,
            status="PAYMENT_PENDING",
            expires_at=past_time
        )
        db.add(stale_booking)
        db.commit()

        # Run worker function
        expired = await expire_stale_bookings(ctx={})
        assert expired >= 1

        db.refresh(stale_booking)
        assert stale_booking.status == "EXPIRED"

        # Clean up
        db.query(Booking).filter(Booking.id == stale_booking.id).delete()
        db.commit()
    finally:
        db.close()


# 11. Exact JSON show_id Matching Prevents Substring False Positives
def test_exact_json_show_id_query_prevents_substring_false_positives():
    """
    Verifies that querying BookingItem.details['show_id'].as_integer() == show_id
    matches strictly and exactly, preventing substring false positives where
    show_id 1 could mistakenly match 12 or 123.
    """
    db: Session = SessionLocal()
    created_booking_ids = []
    try:
        user = db.query(User).first()
        test_shows = [1, 12, 123, 2]

        for s_id in test_shows:
            b = Booking(
                booking_reference=f"GB-TST-EXACT-{s_id}-{uuid.uuid4().hex[:4].upper()}",
                user_id=user.id,
                booking_type="MOVIE",
                total_amount=150.0,
                final_payable=177.0,
                status="CONFIRMED"
            )
            db.add(b)
            db.flush()
            created_booking_ids.append(b.id)

            item = BookingItem(
                booking_id=b.id,
                item_type="SEAT",
                item_id=88000 + s_id,
                name=f"Seat Test for show {s_id}",
                quantity=1,
                unit_price=150.0,
                subtotal=150.0,
                details={"show_id": s_id, "seat_code": f"A{s_id}"}
            )
            db.add(item)
        db.commit()

        # Query for show_id = 1 -> Must match ONLY item for show 1, NOT 12 or 123
        matched_1 = db.query(BookingItem.item_id).join(Booking).filter(
            Booking.id.in_(created_booking_ids),
            Booking.status == "CONFIRMED",
            Booking.booking_type == "MOVIE",
            BookingItem.details["show_id"].as_integer() == 1
        ).all()
        assert len(matched_1) == 1
        assert matched_1[0][0] == 88001

        # Query for show_id = 12 -> Must match ONLY item for show 12
        matched_12 = db.query(BookingItem.item_id).join(Booking).filter(
            Booking.id.in_(created_booking_ids),
            Booking.status == "CONFIRMED",
            Booking.booking_type == "MOVIE",
            BookingItem.details["show_id"].as_integer() == 12
        ).all()
        assert len(matched_12) == 1
        assert matched_12[0][0] == 88012

        # Query for show_id = 123 -> Must match ONLY item for show 123
        matched_123 = db.query(BookingItem.item_id).join(Booking).filter(
            Booking.id.in_(created_booking_ids),
            Booking.status == "CONFIRMED",
            Booking.booking_type == "MOVIE",
            BookingItem.details["show_id"].as_integer() == 123
        ).all()
        assert len(matched_123) == 1
        assert matched_123[0][0] == 88123

        # Query for non-existent show_id = 999 -> Must match nothing
        matched_none = db.query(BookingItem.item_id).join(Booking).filter(
            Booking.id.in_(created_booking_ids),
            Booking.status == "CONFIRMED",
            Booking.booking_type == "MOVIE",
            BookingItem.details["show_id"].as_integer() == 999
        ).all()
        assert len(matched_none) == 0

    finally:
        if created_booking_ids:
            db.query(BookingItem).filter(BookingItem.booking_id.in_(created_booking_ids)).delete(synchronize_session=False)
            db.query(Booking).filter(Booking.id.in_(created_booking_ids)).delete(synchronize_session=False)
            db.commit()
        db.close()
