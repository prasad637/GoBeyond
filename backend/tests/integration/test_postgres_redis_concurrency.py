import concurrent.futures
import uuid
import datetime
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.locks import lock_service
from app.models.user import User
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.dining import Restaurant, DiningTable, DiningReservation
from app.models.sports import Activity, ActivitySlot
from app.models.event import EventTicketType, Event


@pytest.mark.integration
def test_real_redis_distributed_locking_concurrency():
    """
    Simulates 20 concurrent threads attempting to acquire the exact same inventory lock key
    against a live Redis 7 instance.
    Verifies that Redis distributed locking is strictly pessimistic:
    Exactly 1 thread acquires the lock, and 19 threads fail.
    Verifies that the key exists in Redis with an active TTL.
    """
    key = f"perf_seat_show1_{uuid.uuid4().hex[:6]}"
    tokens = [str(uuid.uuid4()) for _ in range(20)]
    ttl = 45

    def worker_acquire(token):
        return lock_service.acquire_lock(key, token, expiry_seconds=ttl)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(worker_acquire, tokens))

    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert failure_count == 19, f"Expected 19 failures, got {failure_count}"

    # Verify key in real Redis
    redis_key = f"gobeyond:lock:{key}"
    assert lock_service.redis_client.exists(redis_key) == 1
    key_ttl = lock_service.redis_client.ttl(redis_key)
    assert 0 < key_ttl <= ttl

    # Clean up
    winning_token = tokens[results.index(True)]
    released = lock_service.release_lock(key, winning_token)
    assert released is True
    assert lock_service.redis_client.exists(redis_key) == 0


@pytest.mark.integration
def test_real_redis_atomic_lua_lock_release():
    """
    Verifies atomic Lua compare-and-delete behavior against real Redis 7:
    Releasing a lock with a non-matching ownership token fails (returns False and preserves key).
    Releasing with the matching ownership token succeeds (returns True and deletes key).
    """
    key = f"lua_test_key_{uuid.uuid4().hex[:6]}"
    owner_token = f"token_owner_{uuid.uuid4().hex[:8]}"
    intruder_token = f"token_intruder_{uuid.uuid4().hex[:8]}"

    # 1. Acquire lock
    acquired = lock_service.acquire_lock(key, owner_token, expiry_seconds=60)
    assert acquired is True

    # 2. Intruder attempts to release -> must fail
    released_intruder = lock_service.release_lock(key, intruder_token)
    assert released_intruder is False

    # Key must still exist in Redis holding owner's token
    redis_key = f"gobeyond:lock:{key}"
    assert lock_service.redis_client.get(redis_key) == owner_token

    # 3. Legitimate owner releases -> must succeed
    released_owner = lock_service.release_lock(key, owner_token)
    assert released_owner is True

    # Key must now be deleted
    assert lock_service.redis_client.exists(redis_key) == 0


@pytest.mark.integration
def test_real_postgres_duplicate_active_seat_locks():
    """
    Verifies PostgreSQL partial unique index `uq_active_resource_lock` where is_released = false.
    Two active locks for the same seat/show cannot coexist in the database.
    Once the first lock is marked released (is_released = true), a new active lock can be created.
    """
    db1: Session = SessionLocal()
    db2: Session = SessionLocal()
    try:
        user1 = db1.query(User).first()
        user2 = db2.query(User).order_by(User.id.desc()).first()

        res_id = 8888
        ident = f"seat_test_{uuid.uuid4().hex[:5]}"
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)

        # 1. User 1 acquires active seat lock
        lock1 = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=res_id,
            identifier=ident,
            user_id=user1.id,
            lock_token="token_user1",
            expires_at=exp,
            is_released=False
        )
        db1.add(lock1)
        db1.commit()

        # 2. User 2 concurrently attempts to acquire the exact same active seat lock
        lock2 = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=res_id,
            identifier=ident,
            user_id=user2.id,
            lock_token="token_user2",
            expires_at=exp,
            is_released=False
        )
        db2.add(lock2)

        # Must raise IntegrityError due to partial unique index uq_active_resource_lock
        with pytest.raises(IntegrityError) as exc_info:
            db2.commit()
        assert "uq_active_resource_lock" in str(exc_info.value).lower()
        db2.rollback()

        # 3. User 1 releases lock
        lock1.is_released = True
        db1.commit()

        # 4. Now User 2 can acquire the lock because previous lock is released
        lock2_retry = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=res_id,
            identifier=ident,
            user_id=user2.id,
            lock_token="token_user2_retry",
            expires_at=exp,
            is_released=False
        )
        db2.add(lock2_retry)
        db2.commit()
        assert lock2_retry.id is not None

        # Clean up
        db2.query(SeatLock).filter(SeatLock.identifier == ident).delete()
        db2.commit()
    finally:
        db1.close()
        db2.close()


@pytest.mark.integration
def test_real_postgres_dining_reservation_overlapping_intervals_exclusion():
    """
    Verifies PostgreSQL GiST exclusion constraint `exclude_overlapping_dining_reservations`:
    Prevents overlapping reservations on the same physical table for active statuses (PENDING, CONFIRMED, SEATED).
    Verifies that non-overlapping adjacent reservations and cancelled reservations succeed.
    """
    db1: Session = SessionLocal()
    db2: Session = SessionLocal()
    try:
        rest = db1.query(Restaurant).filter(Restaurant.is_active == True).first()
        table = rest.tables[0]
        user1 = db1.query(User).first()
        user2 = db2.query(User).order_by(User.id.desc()).first()

        booking1 = Booking(
            booking_reference=f"GB-TEST-{uuid.uuid4().hex[:6].upper()}",
            user_id=user1.id,
            booking_type="DINING",
            total_amount=0.0,
            final_payable=0.0,
            status="CONFIRMED"
        )
        db1.add(booking1)
        db1.commit()

        booking2 = Booking(
            booking_reference=f"GB-TEST-{uuid.uuid4().hex[:6].upper()}",
            user_id=user2.id,
            booking_type="DINING",
            total_amount=0.0,
            final_payable=0.0,
            status="CONFIRMED"
        )
        db2.add(booking2)
        db2.commit()

        res_date = datetime.date.today() + datetime.timedelta(days=180)
        start1 = datetime.datetime.combine(res_date, datetime.time(19, 0))
        end1 = start1 + datetime.timedelta(minutes=105)  # 19:00 - 20:45

        # 1. First confirmed reservation (19:00 - 20:45)
        res1 = DiningReservation(
            restaurant_id=rest.id,
            table_id=table.id,
            user_id=user1.id,
            booking_id=booking1.id,
            reservation_date=res_date,
            reservation_time=datetime.time(19, 0),
            start_datetime=start1,
            end_datetime=end1,
            duration_minutes=90,
            buffer_minutes=15,
            guest_count=2,
            status="CONFIRMED"
        )
        db1.add(res1)
        db1.commit()

        # 2. Overlapping reservation attempt on same table (19:45 - 21:30)
        start2 = datetime.datetime.combine(res_date, datetime.time(19, 45))
        end2 = start2 + datetime.timedelta(minutes=105)
        res2_overlap = DiningReservation(
            restaurant_id=rest.id,
            table_id=table.id,
            user_id=user2.id,
            booking_id=booking2.id,
            reservation_date=res_date,
            reservation_time=datetime.time(19, 45),
            start_datetime=start2,
            end_datetime=end2,
            duration_minutes=90,
            buffer_minutes=15,
            guest_count=2,
            status="CONFIRMED"
        )
        db2.add(res2_overlap)

        # Must raise IntegrityError from GiST exclusion constraint
        with pytest.raises(IntegrityError) as exc_info:
            db2.commit()
        assert "exclude_overlapping_dining_reservations" in str(exc_info.value).lower() or "exclusion" in str(exc_info.value).lower()
        db2.rollback()

        # 3. Non-overlapping reservation on same table (21:00 - 22:45) -> Must succeed!
        start3 = datetime.datetime.combine(res_date, datetime.time(21, 0))
        end3 = start3 + datetime.timedelta(minutes=105)
        res3_adjacent = DiningReservation(
            restaurant_id=rest.id,
            table_id=table.id,
            user_id=user2.id,
            booking_id=booking2.id,
            reservation_date=res_date,
            reservation_time=datetime.time(21, 0),
            start_datetime=start3,
            end_datetime=end3,
            duration_minutes=90,
            buffer_minutes=15,
            guest_count=2,
            status="CONFIRMED"
        )
        db2.add(res3_adjacent)
        db2.commit()
        assert res3_adjacent.id is not None

        # 4. Overlapping reservation with CANCELLED status -> Must succeed because exclusion predicate excludes CANCELLED
        res4_cancelled = DiningReservation(
            restaurant_id=rest.id,
            table_id=table.id,
            user_id=user2.id,
            booking_id=booking2.id,
            reservation_date=res_date,
            reservation_time=datetime.time(19, 30),
            start_datetime=datetime.datetime.combine(res_date, datetime.time(19, 30)),
            end_datetime=datetime.datetime.combine(res_date, datetime.time(20, 30)),
            duration_minutes=60,
            buffer_minutes=0,
            guest_count=2,
            status="CANCELLED"
        )
        db2.add(res4_cancelled)
        db2.commit()
        assert res4_cancelled.id is not None

        # Clean up
        db2.query(DiningReservation).filter(DiningReservation.id.in_([res1.id, res3_adjacent.id, res4_cancelled.id])).delete(synchronize_session=False)
        db2.query(Booking).filter(Booking.id.in_([booking1.id, booking2.id])).delete(synchronize_session=False)
        db2.commit()
    finally:
        db1.close()
        db2.close()


@pytest.mark.integration
def test_real_postgres_ticket_inventory_limits():
    """
    Verifies PostgreSQL check constraint `chk_ticket_quantity_valid`:
    Enforces `available_quantity >= 0 AND available_quantity <= total_quantity` directly in database engine.
    """
    db: Session = SessionLocal()
    try:
        ticket = db.query(EventTicketType).first()
        orig_avail = ticket.available_quantity
        orig_total = ticket.total_quantity

        # Attempt to set negative quantity -> Check violation
        with pytest.raises(IntegrityError) as exc_info:
            db.execute(
                text("UPDATE event_ticket_types SET available_quantity = -1 WHERE id = :id"),
                {"id": ticket.id}
            )
            db.commit()
        assert "chk_ticket_quantity_valid" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()
        db.rollback()

        # Attempt to set available_quantity > total_quantity -> Check violation
        with pytest.raises(IntegrityError) as exc_info2:
            db.execute(
                text("UPDATE event_ticket_types SET available_quantity = :exceed WHERE id = :id"),
                {"exceed": orig_total + 10, "id": ticket.id}
            )
            db.commit()
        assert "chk_ticket_quantity_valid" in str(exc_info2.value).lower() or "check" in str(exc_info2.value).lower()
        db.rollback()
    finally:
        db.close()


@pytest.mark.integration
def test_real_postgres_activity_slot_capacity_limits():
    """
    Verifies PostgreSQL check constraint `chk_slot_capacity_valid`:
    Enforces `booked_count <= capacity AND booked_count >= 0` directly in database engine.
    """
    db: Session = SessionLocal()
    try:
        slot = db.query(ActivitySlot).first()
        slot_cap = slot.capacity

        # Attempt to set booked_count > capacity -> Check violation
        with pytest.raises(IntegrityError) as exc_info:
            db.execute(
                text("UPDATE activity_slots SET booked_count = :overflow WHERE id = :id"),
                {"overflow": slot_cap + 1, "id": slot.id}
            )
            db.commit()
        assert "chk_slot_capacity_valid" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()
        db.rollback()

        # Attempt to set negative booked_count -> Check violation
        with pytest.raises(IntegrityError) as exc_info2:
            db.execute(
                text("UPDATE activity_slots SET booked_count = -1 WHERE id = :id"),
                {"id": slot.id}
            )
            db.commit()
        assert "chk_slot_capacity_valid" in str(exc_info2.value).lower() or "check" in str(exc_info2.value).lower()
        db.rollback()
    finally:
        db.close()

