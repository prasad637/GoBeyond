import uuid
import datetime
import concurrent.futures
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.core.locks import lock_service
from app.models.user import User, Role
from app.models.partner import Partner
from app.models.location import Location
from app.models.movie import Cinema, Screen, Seat, Movie, MovieShow
from app.models.dining import Restaurant, DiningTable, DiningReservation
from app.models.event import Event, EventTicketType
from app.models.sports import SportsVenue, Activity, ActivitySlot
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.payment import Payment, Refund
from app.services.booking import quantize_amount


@pytest.fixture(scope="function")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _get_or_create_customer_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.name == "customer").first()
    if not role:
        role = Role(name="customer", description="Standard customer role")
        db.add(role)
        db.commit()
        db.refresh(role)
    return role


def _get_or_create_partner(db: Session, p_type: str = "GENERIC") -> Partner:
    partner = db.query(Partner).filter(Partner.partner_type == p_type, Partner.status.in_(["ACTIVE", "APPROVED"])).first()
    if not partner:
        unique_id = uuid.uuid4().hex[:6]
        user = User(
            email=f"partner_{p_type.lower()}_{unique_id}@gobeyond.test",
            phone=f"91{uuid.uuid4().hex[:8]}"[:10],
            hashed_password="partner_pass_hash",
            full_name=f"Partner {p_type}",
            is_verified=True,
            account_status="ACTIVE"
        )
        db.add(user)
        db.flush()
        partner = Partner(
            user_id=user.id,
            business_name=f"GoBeyond Partner {p_type}",
            partner_type=p_type,
            contact_email=user.email,
            contact_phone=user.phone,
            status="APPROVED"
        )
        db.add(partner)
        db.commit()
        db.refresh(partner)
    return partner


def _create_50_test_users(db: Session, prefix: str):
    """
    Creates 50 distinct customer accounts with unique emails and JWT access tokens.
    """
    role = _get_or_create_customer_role(db)
    users_with_tokens = []
    for i in range(50):
        unique_email = f"conc_{prefix}_{i}_{uuid.uuid4().hex[:6]}@gobeyond.test"
        user = User(
            email=unique_email,
            phone=f"90{uuid.uuid4().hex[:8]}"[:10],
            hashed_password="conc_test_password_hash",
            full_name=f"Concurrency User {i}",
            is_verified=True,
            account_status="ACTIVE"
        )
        user.roles.append(role)
        db.add(user)
        db.flush()
        token = create_access_token(user.id, "customer")
        users_with_tokens.append((user.id, token))
    db.commit()
    return users_with_tokens


# ==============================================================================
# AUDIT TEST 1: VERIFY POSTGRESQL 16 AND REDIS 7 LIVE CONNECTIONS
# ==============================================================================
@pytest.mark.integration
def test_audit_01_verify_postgresql16_and_redis7_connections(db: Session):
    """
    Audit Requirement 1 & 2:
    Verify actual live connections to PostgreSQL 16 and Redis 7.
    """
    # 1. PostgreSQL 16 verification
    db_url = str(engine.url)
    assert "postgres" in db_url.lower() or "psycopg" in db_url.lower(), (
        f"PostgreSQL driver required, got: {db_url}"
    )

    version_row = db.execute(text("SELECT version();")).fetchone()
    version_str = version_row[0]
    print(f"\n[PostgreSQL Connection Verified]: {version_str}")
    assert "PostgreSQL 16" in version_str, f"Expected PostgreSQL 16, found: {version_str}"

    # 2. Redis 7 verification
    assert lock_service.redis_client is not None, "Redis client must be initialized"
    redis_ping = lock_service.redis_client.ping()
    assert redis_ping is True, "Redis ping failed"

    info = lock_service.redis_client.info("server")
    redis_version = info.get("redis_version", "unknown")
    print(f"[Redis Connection Verified]: Version {redis_version}")
    assert redis_version.startswith("7."), f"Expected Redis 7.x, found: {redis_version}"

    # 3. Fail-safe configuration verification
    assert settings.USE_MEMORY_LOCK_FALLBACK is False, "In-memory lock fallback must be disabled"
    assert settings.REDIS_REQUIRED_IN_PRODUCTION is True, "Redis must be mandatory in production"


# ==============================================================================
# AUDIT TEST 2: 50 SIMULTANEOUS REQUESTS FOR THE SAME MOVIE SEAT
# ==============================================================================
@pytest.mark.integration
def test_audit_02_concurrent_50_movie_seat_holds(db: Session):
    """
    Audit Requirement 3 & 4:
    Test 50 simultaneous requests for the exact same movie seat.
    Assert: Exactly 1 succeeds (201 Created), exactly 49 fail with 409 Conflict.
    Assert: Database records exactly 1 booking for this seat. No duplicate records.
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"mov_{prefix}")
    partner = _get_or_create_partner(db, "CINEMA")

    # Set up isolated Movie, Cinema, Screen, Seat, and Show
    loc = db.query(Location).filter(Location.slug == "banjara-hills").first() or db.query(Location).first()

    cinema = Cinema(
        partner_id=partner.id,
        location_id=loc.id,
        name=f"Audit Cine {prefix}",
        address="Road No 2 Banjara Hills",
        city="Hyderabad",
        is_active=True
    )
    db.add(cinema)
    db.flush()

    screen = Screen(cinema_id=cinema.id, name="Audit Screen 1", screen_type="IMAX", total_seats=1)
    db.add(screen)
    db.flush()

    seat = Seat(
        screen_id=screen.id,
        row_code="A",
        seat_number=1,
        tier="VIP",
        base_price=Decimal("350.00"),
        is_accessible=False
    )
    db.add(seat)
    db.flush()

    movie = Movie(
        title=f"Concurrency Blockbuster {prefix}",
        slug=f"conc-blockbuster-{prefix}",
        genre="Sci-Fi",
        duration_minutes=145,
        language="Telugu",
        censor_rating="UA",
        release_date=datetime.date.today(),
        rating=4.5,
        is_active=True
    )
    db.add(movie)
    db.flush()

    show = MovieShow(
        movie_id=movie.id,
        screen_id=screen.id,
        show_date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(18, 0),
        end_time=datetime.time(20, 30),
        price_multiplier=Decimal("1.00"),
        status="SCHEDULED"
    )
    db.add(show)
    db.commit()

    # Clear any previous redis key for this seat
    redis_lock_key = f"gobeyond:lock:show_{show.id}:seat_{seat.id}"
    lock_service.redis_client.delete(redis_lock_key)

    # 50 simultaneous requests for the exact same seat
    payload = {
        "booking_type": "MOVIE",
        "items": [
            {
                "item_type": "SEAT",
                "item_id": seat.id,
                "quantity": 1,
                "details": {
                    "show_id": show.id
                }
            }
        ]
    }

    def fire_seat_request(user_tuple):
        uid, token = user_tuple
        local_client = TestClient(app)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        res = local_client.post("/api/v1/bookings/initiate", json=payload, headers=headers)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(fire_seat_request, users_with_tokens))

    successes = [r for r in results if r[0] == 201]
    conflicts = [r for r in results if r[0] == 409]

    print(f"\n[50 Movie Seat Concurrency Results]: 201={len(successes)}, 409={len(conflicts)}")
    assert len(successes) == 1, f"Expected exactly 1 successful booking, got {len(successes)}"
    assert len(conflicts) == 49, f"Expected exactly 49 conflict responses, got {len(conflicts)}"

    # Database Verification: exactly 1 booking item created for this seat
    fresh_db = SessionLocal()
    seat_bookings = fresh_db.query(BookingItem).join(Booking).filter(
        Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING", "CONFIRMED"]),
        BookingItem.item_type == "SEAT",
        BookingItem.item_id == seat.id
    ).all()
    fresh_db.close()

    assert len(seat_bookings) == 1, (
        f"Database integrity violation: expected 1 booking for seat {seat.id}, found {len(seat_bookings)}"
    )


# ==============================================================================
# AUDIT TEST 3: 50 SIMULTANEOUS REQUESTS FOR THE SAME DINING TABLE
# ==============================================================================
@pytest.mark.integration
def test_audit_03_concurrent_50_dining_table_reservations(db: Session):
    """
    Audit Requirement 5:
    Test 50 simultaneous requests for the same dining table and overlapping time.
    Assert: Exactly 1 succeeds (201 Created), exactly 49 fail with 409 Conflict.
    Assert: Database records exactly 1 active reservation for this table and window.
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"din_{prefix}")
    partner = _get_or_create_partner(db, "RESTAURANT")

    loc = db.query(Location).filter(Location.slug == "jubilee-hills").first() or db.query(Location).first()
    restaurant = Restaurant(
        partner_id=partner.id,
        location_id=loc.id,
        name=f"Concurrency Bistro {prefix}",
        slug=f"conc-bistro-{prefix}",
        address="Jubilee Hills Checkpost",
        phone="9876543210",
        cuisines=["Multi-Cuisine"],
        is_active=True
    )
    db.add(restaurant)
    db.flush()

    table = DiningTable(
        restaurant_id=restaurant.id,
        table_number=f"T-CONC-{prefix}",
        capacity=4,
        zone="Indoor",
        is_active=True
    )
    db.add(table)
    db.commit()

    target_date = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    target_time = "20:00:00"

    # Clear redis lock key
    redis_lock_key = f"gobeyond:lock:dining_table_{table.id}:{target_date}:20_00"
    lock_service.redis_client.delete(redis_lock_key)

    payload = {
        "booking_type": "DINING",
        "items": [
            {
                "item_type": "TABLE",
                "item_id": table.id,
                "quantity": 2,
                "details": {
                    "restaurant_id": restaurant.id,
                    "reservation_date": target_date,
                    "reservation_time": target_time,
                    "guest_count": 2
                }
            }
        ]
    }

    def fire_dining_request(user_tuple):
        uid, token = user_tuple
        local_client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        res = local_client.post("/api/v1/bookings/initiate", json=payload, headers=headers)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(fire_dining_request, users_with_tokens))

    successes = [r for r in results if r[0] == 201]
    conflicts = [r for r in results if r[0] == 409]

    print(f"\n[50 Dining Table Concurrency Results]: 201={len(successes)}, 409={len(conflicts)}")
    assert len(successes) == 1, f"Expected exactly 1 dining reservation hold, got {len(successes)}"
    assert len(conflicts) == 49, f"Expected exactly 49 conflicts, got {len(conflicts)}"

    # Database Verification: exactly 1 booking for this table
    fresh_db = SessionLocal()
    table_bookings = fresh_db.query(BookingItem).join(Booking).filter(
        Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING", "CONFIRMED"]),
        BookingItem.item_type == "TABLE",
        BookingItem.item_id == table.id
    ).all()
    fresh_db.close()

    assert len(table_bookings) == 1, (
        f"Database integrity violation: expected 1 reservation for table {table.id}, found {len(table_bookings)}"
    )


# ==============================================================================
# AUDIT TEST 4: 50 SIMULTANEOUS REQUESTS FOR EVENT TICKETS (NO OVERSELLING)
# ==============================================================================
@pytest.mark.integration
def test_audit_04_concurrent_50_event_tickets_overselling_prevention(db: Session):
    """
    Audit Requirement 6 & 8:
    Test 50 simultaneous requests for event ticket inventory with only 5 tickets available.
    Assert: Exactly 5 succeed (201 Created), exactly 45 fail with 409 Conflict.
    Assert: Final available_quantity in PostgreSQL is exactly 0. Zero overselling!
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"eve_{prefix}")
    partner = _get_or_create_partner(db, "EVENT")

    loc = db.query(Location).filter(Location.slug == "gachibowli").first() or db.query(Location).first()
    event = Event(
        partner_id=partner.id,
        location_id=loc.id,
        title=f"Mega Concurrency Festival {prefix}",
        slug=f"mega-conc-fest-{prefix}",
        category="CONCERT",
        venue_name="Gachibowli Stadium",
        venue_address="Gachibowli Main Road",
        start_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        end_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7, hours=4),
        is_active=True
    )
    db.add(event)
    db.flush()

    ticket_type = EventTicketType(
        event_id=event.id,
        name="Silver VIP Pass",
        price=Decimal("1500.00"),
        total_quantity=5,
        available_quantity=5,
        max_per_booking=10
    )
    db.add(ticket_type)
    db.commit()

    # Clear redis mutex key
    lock_service.redis_client.delete(f"gobeyond:lock:event_ticket_{ticket_type.id}")

    payload = {
        "booking_type": "EVENT",
        "items": [
            {
                "item_type": "TICKET",
                "item_id": ticket_type.id,
                "quantity": 1,
                "details": {
                    "event_id": event.id
                }
            }
        ]
    }

    def fire_ticket_request(user_tuple):
        uid, token = user_tuple
        local_client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        res = local_client.post("/api/v1/bookings/initiate", json=payload, headers=headers)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(fire_ticket_request, users_with_tokens))

    successes = [r for r in results if r[0] == 201]
    conflicts = [r for r in results if r[0] == 409]

    print(f"\n[50 Event Ticket Concurrency Results]: 201={len(successes)}, 409={len(conflicts)}")
    assert len(successes) == 5, f"Expected exactly 5 bookings (pool=5), got {len(successes)}"
    assert len(conflicts) == 45, f"Expected exactly 45 conflicts, got {len(conflicts)}"

    # Database Verification: available_quantity must be strictly 0, never negative
    fresh_db = SessionLocal()
    refreshed_tt = fresh_db.query(EventTicketType).filter(EventTicketType.id == ticket_type.id).first()
    final_avail = refreshed_tt.available_quantity
    fresh_db.close()

    print(f"[Event Ticket Inventory Conservation]: Total=5, Booked=5, Available={final_avail}")
    assert final_avail == 0, f"Expected remaining available_quantity == 0, got {final_avail}"


# ==============================================================================
# AUDIT TEST 5: 50 SIMULTANEOUS REQUESTS FOR SPORTS/ACTIVITY SLOT (NO OVERSELLING)
# ==============================================================================
@pytest.mark.integration
def test_audit_05_concurrent_50_activity_slots_capacity_prevention(db: Session):
    """
    Audit Requirement 7 & 8:
    Test 50 simultaneous requests for an activity slot with capacity 5.
    Assert: Exactly 5 succeed (201 Created), exactly 45 fail with 409 Conflict.
    Assert: Final booked_count in PostgreSQL is exactly 5. Zero overselling!
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"act_{prefix}")
    partner = _get_or_create_partner(db, "SPORTS")

    loc = db.query(Location).filter(Location.slug == "madhapur").first() or db.query(Location).first()
    venue = SportsVenue(
        partner_id=partner.id,
        location_id=loc.id,
        name=f"Concurrency Turf {prefix}",
        sport_types=["Cricket", "Football"],
        address="Madhapur Metro Station",
        is_active=True
    )
    db.add(venue)
    db.flush()

    activity = Activity(
        partner_id=partner.id,
        location_id=loc.id,
        venue_id=venue.id,
        title=f"Night Football League {prefix}",
        slug=f"night-football-{prefix}",
        category="SPORTS",
        base_price=Decimal("400.00"),
        duration_minutes=60,
        is_active=True
    )
    db.add(activity)
    db.flush()

    slot = ActivitySlot(
        activity_id=activity.id,
        slot_date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(19, 0),
        end_time=datetime.time(20, 0),
        capacity=5,
        booked_count=0,
        is_available=True
    )
    db.add(slot)
    db.commit()

    # Clear redis mutex
    lock_service.redis_client.delete(f"gobeyond:lock:activity_slot_{slot.id}")

    payload = {
        "booking_type": "SPORTS",
        "items": [
            {
                "item_type": "SLOT",
                "item_id": slot.id,
                "quantity": 1,
                "details": {
                    "activity_id": activity.id
                }
            }
        ]
    }

    def fire_slot_request(user_tuple):
        uid, token = user_tuple
        local_client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        res = local_client.post("/api/v1/bookings/initiate", json=payload, headers=headers)
        return res.status_code, res.json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(fire_slot_request, users_with_tokens))

    successes = [r for r in results if r[0] == 201]
    conflicts = [r for r in results if r[0] == 409]

    print(f"\n[50 Activity Slot Concurrency Results]: 201={len(successes)}, 409={len(conflicts)}")
    assert len(successes) == 5, f"Expected exactly 5 slot bookings (capacity=5), got {len(successes)}"
    assert len(conflicts) == 45, f"Expected exactly 45 conflicts, got {len(conflicts)}"

    # Database Verification: booked_count must be strictly 5, never > 5
    fresh_db = SessionLocal()
    refreshed_slot = fresh_db.query(ActivitySlot).filter(ActivitySlot.id == slot.id).first()
    final_booked = refreshed_slot.booked_count
    fresh_db.close()

    print(f"[Activity Slot Capacity Conservation]: Capacity=5, Booked={final_booked}")
    assert final_booked == 5, f"Expected booked_count == 5, got {final_booked}"


# ==============================================================================
# AUDIT TEST 6: VERIFY ZERO OVERSELLING & ZERO DUPLICATE RESERVATIONS ACROSS VERTICALS
# ==============================================================================
@pytest.mark.integration
def test_audit_06_verify_zero_overselling_and_zero_duplicate_reservations(db: Session):
    """
    Audit Requirement 8:
    Verify that across all 4 concurrency tests, zero inventory was oversold
    and zero duplicate active reservations exist in PostgreSQL.
    """
    # 1. Check EventTicketTypes: no available_quantity < 0
    negative_tickets = db.query(EventTicketType).filter(
        EventTicketType.available_quantity < 0
    ).all()
    assert len(negative_tickets) == 0, f"Found negative ticket inventory: {negative_tickets}"

    # 2. Check ActivitySlots: no booked_count > capacity
    oversold_slots = db.query(ActivitySlot).filter(
        ActivitySlot.booked_count > ActivitySlot.capacity
    ).all()
    assert len(oversold_slots) == 0, f"Found oversold activity slots: {oversold_slots}"

    # 3. Check SeatLocks: no active duplicate locks for the same resource and identifier
    active_locks = db.execute(text("""
        SELECT resource_type, resource_id, identifier, COUNT(*)
        FROM seat_locks
        WHERE is_released = false AND expires_at > NOW()
        GROUP BY resource_type, resource_id, identifier
        HAVING COUNT(*) > 1;
    """)).fetchall()
    assert len(active_locks) == 0, f"Found duplicate active seat locks: {active_locks}"


# ==============================================================================
# AUDIT TEST 7: REDIS UNAVAILABLE BEHAVIOR - FAIL SAFE, NO MEMORY FALLBACK
# ==============================================================================
@pytest.mark.integration
def test_audit_07_redis_unavailable_fails_safely_no_memory_fallback(db: Session):
    """
    Audit Requirement 9:
    When Redis is unavailable or disconnected:
    - Booking MUST fail safely with HTTP 503 Service Unavailable.
    - MUST NOT fall back to in-memory locks in production/integration environments.
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"fail_{prefix}")
    uid, token = users_with_tokens[0]

    # Save real redis client
    real_redis = lock_service.redis_client
    try:
        # Simulate Redis outage
        lock_service.redis_client = None
        settings.USE_MEMORY_LOCK_FALLBACK = False

        # Attempt to acquire lock directly via lock_service
        with pytest.raises(Exception) as exc_info:
            lock_service.acquire_lock("test_fail_key", "test_token")

        assert "503" in str(exc_info.value), f"Expected HTTP 503 on Redis outage, got {exc_info.value}"

        # Verify that InMemoryLockManager was NOT populated
        assert len(lock_service.memory_manager.get_all_locked()) == 0, (
            "InMemoryLockManager must remain empty when fallback is disabled"
        )
    finally:
        # Restore real redis client
        lock_service.redis_client = real_redis


# ==============================================================================
# AUDIT TEST 8: ATOMIC LOCK RELEASE & LOCK OWNERSHIP VERIFICATION
# ==============================================================================
@pytest.mark.integration
def test_audit_08_atomic_lock_release_and_ownership_verification(db: Session):
    """
    Audit Requirement 10:
    Verify atomic compare-and-delete Lua script and lock ownership verification in Redis 7:
    - Client A acquires lock with Token A.
    - Client B attempts to release lock with Token B -> fails (returns False, Redis key untouched).
    - Client A releases lock with Token A -> succeeds (returns True, Redis key deleted).
    """
    test_key = f"audit_lock_{uuid.uuid4().hex[:8]}"
    token_a = f"token_a_{uuid.uuid4().hex[:8]}"
    token_b = f"token_b_{uuid.uuid4().hex[:8]}"

    # Client A acquires lock
    acquired = lock_service.acquire_lock(test_key, token_a, expiry_seconds=60)
    assert acquired is True, "Client A failed to acquire lock"
    assert lock_service.is_locked(test_key) is True, "Key should be locked"

    # Client B attempts to release Client A's lock with Token B
    released_by_b = lock_service.release_lock(test_key, token_b)
    assert released_by_b is False, "Client B must NOT be able to release Client A's lock"
    assert lock_service.is_locked(test_key) is True, "Key must remain locked after unauthorized release attempt"

    # Client A releases with authentic Token A
    released_by_a = lock_service.release_lock(test_key, token_a)
    assert released_by_a is True, "Client A should successfully release their own lock"
    assert lock_service.is_locked(test_key) is False, "Key should be deleted after authorized release"


# ==============================================================================
# AUDIT TEST 9: DUPLICATE PAYMENT WEBHOOKS IDEMPOTENCY
# ==============================================================================
@pytest.mark.integration
def test_audit_09_duplicate_payment_webhooks_idempotency(db: Session):
    """
    Audit Requirement 11:
    Test duplicate payment webhooks.
    Second callback must return 'already_processed' without creating duplicate payments or bookings.
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"whk_{prefix}")
    uid, token = users_with_tokens[0]

    booking = Booking(
        booking_reference=f"GB-EXP-2611-{prefix.upper()}",
        user_id=uid,
        booking_type="EVENT",
        total_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        discount_amount=Decimal("0.00"),
        final_payable=Decimal("1180.00"),
        status="PAYMENT_PENDING"
    )
    db.add(booking)
    db.flush()

    order_id = f"order_{prefix}_{uuid.uuid4().hex[:8]}"
    payment = Payment(
        booking_id=booking.id,
        user_id=uid,
        payment_gateway="RAZORPAY",
        gateway_order_id=order_id,
        amount=Decimal("1180.00"),
        currency="INR",
        status="INITIATED"
    )
    db.add(payment)
    db.commit()

    webhook_payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_{prefix}_123",
                    "order_id": order_id,
                    "amount": 118000,
                    "currency": "INR",
                    "status": "captured"
                }
            }
        }
    }

    local_client = TestClient(app)

    # 1. First webhook delivery
    res1 = local_client.post("/api/v1/payments/webhook", json=webhook_payload)
    assert res1.status_code == 200
    assert res1.json().get("status") == "received"

    # Verify booking confirmed in DB
    db.refresh(booking)
    db.refresh(payment)
    assert booking.status == "CONFIRMED"
    assert payment.status == "CAPTURED"

    # 2. Duplicate webhook delivery
    res2 = local_client.post("/api/v1/payments/webhook", json=webhook_payload)
    assert res2.status_code == 200
    assert res2.json().get("status") == "already_processed", (
        f"Expected 'already_processed', got {res2.json()}"
    )

    # Verify no duplicate payment records created
    payment_count = db.query(Payment).filter(Payment.gateway_order_id == order_id).count()
    assert payment_count == 1, f"Expected 1 payment record, found {payment_count}"


# ==============================================================================
# AUDIT TEST 10: LATE PAYMENT AFTER INVENTORY HOLD EXPIRY & REASSIGNMENT
# ==============================================================================
@pytest.mark.integration
def test_audit_10_late_payment_after_hold_expiry_and_reassignment(db: Session):
    """
    Audit Requirement 11:
    Test late payment after inventory hold expiration and reassignment.
    When payment arrives after hold expired, system MUST transition booking to REFUND_PENDING
    and create an automated Refund record for financial reconciliation.
    """
    prefix = uuid.uuid4().hex[:6]
    users_with_tokens = _create_50_test_users(db, f"late_{prefix}")
    uid_a, token_a = users_with_tokens[0]

    # Create an EXPIRED booking for User A
    booking = Booking(
        booking_reference=f"GB-MOV-2611-{prefix.upper()}",
        user_id=uid_a,
        booking_type="MOVIE",
        total_amount=Decimal("350.00"),
        tax_amount=Decimal("63.00"),
        discount_amount=Decimal("0.00"),
        final_payable=Decimal("413.00"),
        status="EXPIRED",  # Hold expired
        expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
    )
    db.add(booking)
    db.flush()

    order_id = f"order_late_{prefix}"
    payment = Payment(
        booking_id=booking.id,
        user_id=uid_a,
        payment_gateway="RAZORPAY",
        gateway_order_id=order_id,
        amount=Decimal("413.00"),
        currency="INR",
        status="INITIATED"
    )
    db.add(payment)
    db.commit()

    # User A's late payment callback arrives
    local_client = TestClient(app)
    headers = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}
    verify_payload = {
        "booking_id": booking.id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": f"pay_late_{prefix}",
        "razorpay_signature": "mock_sig_sandbox"
    }

    res = local_client.post("/api/v1/payments/verify", json=verify_payload, headers=headers)
    assert res.status_code == 200

    # Verify that booking was NOT confirmed; instead transitioned to REFUND_PENDING
    db.refresh(booking)
    assert booking.status == "REFUND_PENDING", (
        f"Expected booking to be REFUND_PENDING due to late hold expiration, got {booking.status}"
    )

    # Verify automated Refund record was created for financial reconciliation
    refund = db.query(Refund).filter(Refund.booking_id == booking.id).first()
    assert refund is not None, "Automated Refund record was not created for late payment"
    assert refund.status == "INITIATED"
    assert quantize_amount(refund.amount) == Decimal("413.00")
    print(f"\n[Late Payment Reconciliation Verified]: Refund {refund.gateway_refund_id} created for ₹{refund.amount}")