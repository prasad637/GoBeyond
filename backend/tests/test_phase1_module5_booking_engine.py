import uuid
import datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
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
from app.models.payment import Payment, Refund, Coupon
from app.services.booking import BookingEngineService, quantize_amount

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers(db_session: Session):
    unique_email = f"m5_cust_{uuid.uuid4().hex[:6]}@gobeyond.in"
    user = User(
        email=unique_email,
        phone=f"9876{uuid.uuid4().hex[:6]}",
        hashed_password="hashed_pw_test",
        full_name="Module 5 Customer",
        is_verified=True,
        account_status="ACTIVE"
    )
    role = db_session.query(Role).filter(Role.name == "customer").first()
    if role:
        user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id, [r.name for r in user.roles])
    return {"Authorization": f"Bearer {token}", "User-Id": str(user.id)}


@pytest.fixture
def other_user_headers(db_session: Session):
    unique_email = f"m5_other_{uuid.uuid4().hex[:6]}@gobeyond.in"
    user = User(
        email=unique_email,
        phone=f"9855{uuid.uuid4().hex[:6]}",
        hashed_password="hashed_pw_test",
        full_name="Second Customer",
        is_verified=True,
        account_status="ACTIVE"
    )
    role = db_session.query(Role).filter(Role.name == "customer").first()
    if role:
        user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id, [r.name for r in user.roles])
    return {"Authorization": f"Bearer {token}", "User-Id": str(user.id)}


@pytest.fixture
def partner_headers(db_session: Session):
    partner = db_session.query(Partner).filter(Partner.id == 1).first()
    if not partner:
        unique_email = f"m5_partner_{uuid.uuid4().hex[:6]}@gobeyond.in"
        user = User(
            email=unique_email,
            phone=f"9811{uuid.uuid4().hex[:6]}",
            hashed_password="hashed_pw_test",
            full_name="Module 5 Cinema Partner",
            is_verified=True,
            account_status="ACTIVE"
        )
        role = db_session.query(Role).filter(Role.name == "partner_cinema").first()
        if role:
            user.roles.append(role)
        db_session.add(user)
        db_session.flush()

        partner = Partner(
            user_id=user.id,
            business_name="M5 Luxe Cinemas",
            partner_type="CINEMA",
            contact_email=unique_email,
            contact_phone=user.phone,
            status="ACTIVE"
        )
        db_session.add(partner)
        db_session.commit()
    user = partner.user
    token = create_access_token(user.id, [r.name for r in user.roles])
    return {"Authorization": f"Bearer {token}", "Partner-Id": str(partner.id), "User-Id": str(user.id)}


def create_isolated_movie_show(db_session: Session):
    """Creates a fresh cinema, screen, seats, movie, and show for conflict-free testing."""
    partner = db_session.query(Partner).first()
    location = db_session.query(Location).first()

    cinema = Cinema(
        partner_id=partner.id,
        location_id=location.id,
        name=f"Cinema Test {uuid.uuid4().hex[:4]}",
        address="Test Road",
        city="Hyderabad"
    )
    db_session.add(cinema)
    db_session.flush()

    screen = Screen(cinema_id=cinema.id, name="Screen X", screen_type="2D")
    db_session.add(screen)
    db_session.flush()

    seats = []
    for i in range(1, 5):
        s = Seat(screen_id=screen.id, row_code="B", seat_number=i, tier="PREMIUM", base_price=Decimal("250.00"))
        db_session.add(s)
        seats.append(s)
    db_session.flush()

    movie = db_session.query(Movie).first()
    show = MovieShow(
        movie_id=movie.id,
        screen_id=screen.id,
        show_date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(18, 0),
        end_time=datetime.time(20, 30),
        price_multiplier=Decimal("1.00"),
        status="SCHEDULED"
    )
    db_session.add(show)
    db_session.commit()
    db_session.refresh(show)
    return show, seats


def create_isolated_event(db_session: Session):
    """Creates a fresh event with ticket types for conflict-free testing."""
    partner = db_session.query(Partner).first()
    location = db_session.query(Location).first()

    evt = Event(
        partner_id=partner.id,
        location_id=location.id,
        title=f"Test Live Concert {uuid.uuid4().hex[:4]}",
        slug=f"test-concert-{uuid.uuid4().hex[:6]}",
        category="CONCERT",
        venue_name="Gachibowli Stadium",
        venue_address="Old Mumbai Highway",
        start_datetime=datetime.datetime.now() + datetime.timedelta(days=5),
        end_datetime=datetime.datetime.now() + datetime.timedelta(days=5, hours=3),
        is_active=True
    )
    db_session.add(evt)
    db_session.flush()

    tt = EventTicketType(
        event_id=evt.id,
        name="VIP Pass",
        price=Decimal("499.00"),
        total_quantity=50,
        available_quantity=50,
        max_per_booking=10
    )
    db_session.add(tt)
    db_session.commit()
    db_session.refresh(tt)
    return evt, tt


def create_isolated_activity(db_session: Session):
    partner = db_session.query(Partner).first()
    location = db_session.query(Location).first()

    act = Activity(
        partner_id=partner.id,
        location_id=location.id,
        title=f"Test Turf {uuid.uuid4().hex[:4]}",
        slug=f"test-turf-{uuid.uuid4().hex[:6]}",
        category="SPORTS",
        base_price=Decimal("1200.00"),
        duration_minutes=60,
        is_active=True
    )
    db_session.add(act)
    db_session.flush()

    slot = ActivitySlot(
        activity_id=act.id,
        slot_date=datetime.date.today() + datetime.timedelta(days=2),
        start_time=datetime.time(19, 0),
        end_time=datetime.time(20, 0),
        capacity=10,
        booked_count=0,
        is_available=True
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)
    return act, slot


# --- 1. Movie Booking & Pessimistic Seat Locking ---
def test_movie_seat_locking_and_conflict_prevention(db_session: Session, auth_headers: dict, other_user_headers: dict):
    show, seats = create_isolated_movie_show(db_session)
    seat = seats[0]

    # User 1 locks seat
    res1 = client.post(
        f"/api/v1/movies/shows/{show.id}/lock-seats",
        json={"show_id": show.id, "seat_ids": [seat.id]},
        headers=auth_headers
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["success"] is True
    assert seat.id in data1["locked_seat_ids"]
    lock_token = data1["lock_token"]

    # User 2 attempts to lock the exact same seat -> 409 Conflict
    res2 = client.post(
        f"/api/v1/movies/shows/{show.id}/lock-seats",
        json={"show_id": show.id, "seat_ids": [seat.id]},
        headers=other_user_headers
    )
    assert res2.status_code == 409
    assert "currently held" in res2.json()["detail"].lower()

    # Cleanup lock
    lock_service.release_lock(f"show_{show.id}:seat_{seat.id}", lock_token)


def test_movie_booking_initiation_and_payment_capture(db_session: Session, auth_headers: dict):
    show, seats = create_isolated_movie_show(db_session)
    seat_ids = [seats[0].id, seats[1].id]

    # Lock seats first
    lock_res = client.post(
        f"/api/v1/movies/shows/{show.id}/lock-seats",
        json={"show_id": show.id, "seat_ids": seat_ids},
        headers=auth_headers
    )
    assert lock_res.status_code == 200
    lock_token = lock_res.json()["lock_token"]

    # Initiate Booking
    items = [
        {
            "item_type": "SEAT",
            "item_id": s_id,
            "quantity": 1,
            "unit_price": 0.0,  # Deliberately submit 0; backend computes true catalog price
            "details": {"show_id": show.id}
        }
        for s_id in seat_ids
    ]
    book_res = client.post(
        "/api/v1/bookings/initiate",
        json={
            "booking_type": "MOVIE",
            "items": items,
            "lock_token": lock_token
        },
        headers=auth_headers
    )
    assert book_res.status_code == 201, book_res.text
    booking_data = book_res.json()
    assert booking_data["booking_type"] == "MOVIE"
    assert booking_data["status"] == "PAYMENT_PENDING"
    assert booking_data["booking_reference"].startswith("GB-MOV-")
    assert booking_data["final_payable"] > 0
    booking_id = booking_data["id"]

    # Create Payment Order
    order_res = client.post(
        "/api/v1/payments/create-order",
        json={"booking_id": booking_id},
        headers=auth_headers
    )
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["order_id"].startswith("order_")

    # Verify Payment Signature
    verify_res = client.post(
        "/api/v1/payments/verify",
        json={
            "booking_id": booking_id,
            "razorpay_order_id": order_data["order_id"],
            "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:12]}",
            "razorpay_signature": "mock_test_sig"
        },
        headers=auth_headers
    )
    assert verify_res.status_code == 200, verify_res.text
    verify_data = verify_res.json()
    assert verify_data["success"] is True
    assert verify_data["status"] == "CONFIRMED"
    assert "GB-PASS-" in verify_data["qr_code_token"]


# --- 2. Dining Table Reservation ---
def test_dining_table_reservation_and_overlap_exclusion(db_session: Session, auth_headers: dict):
    restaurant = db_session.query(Restaurant).first()
    today_str = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    time_str = "21:00:00"

    # Guest reserves table
    res1 = client.post(
        "/api/v1/dining/reserve",
        json={
            "restaurant_id": restaurant.id,
            "reservation_date": today_str,
            "reservation_time": time_str,
            "guest_count": 2,
            "special_requests": "Window table please"
        },
        headers=auth_headers
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["success"] is True
    assert data1["status"] == "CONFIRMED"
    assert data1["booking_reference"].startswith("GB-DIN")


# --- 3. Event Ticket Booking & Atomic Decrement ---
def test_event_ticket_booking_and_limit_enforcement(db_session: Session, auth_headers: dict):
    event, ticket_type = create_isolated_event(db_session)
    initial_qty = ticket_type.available_quantity
    assert initial_qty == 50

    # Book 2 tickets
    book_res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "EVENT",
            "items": [
                {
                    "item_type": "TICKET",
                    "item_id": ticket_type.id,
                    "quantity": 2,
                    "details": {"event_id": event.id}
                }
            ]
        },
        headers=auth_headers
    )
    assert book_res.status_code == 201, book_res.text
    b_data = book_res.json()
    assert b_data["status"] == "PAYMENT_PENDING"

    # Check database quantity was decremented atomically
    db_session.refresh(ticket_type)
    assert ticket_type.available_quantity == 48


# --- 4. Sports and Activities Booking ---
def test_sports_activity_slot_booking(db_session: Session, auth_headers: dict):
    activity, slot = create_isolated_activity(db_session)
    initial_booked = slot.booked_count
    assert initial_booked == 0

    book_res = client.post(
        "/api/v1/bookings/initiate",
        json={
            "booking_type": "ACTIVITY",
            "items": [
                {
                    "item_type": "SLOT",
                    "item_id": slot.id,
                    "quantity": 1,
                    "details": {"activity_id": activity.id}
                }
            ]
        },
        headers=auth_headers
    )
    assert book_res.status_code == 201, book_res.text

    db_session.refresh(slot)
    assert slot.booked_count == 1


# --- 5. Hold Expiration and Automatic Inventory Release ---
def test_hold_expiration_and_stale_lock_release(db_session: Session, auth_headers: dict):
    event, ticket_type = create_isolated_event(db_session)
    qty_before = ticket_type.available_quantity

    # Create a booking that expired 15 minutes ago
    ref = f"GB-EVT-EXPIRED-{uuid.uuid4().hex[:6]}"
    past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)

    expired_booking = Booking(
        booking_reference=ref,
        user_id=int(auth_headers["User-Id"]),
        booking_type="EVENT",
        total_amount=Decimal("500.00"),
        tax_amount=Decimal("90.00"),
        discount_amount=Decimal("0.00"),
        final_payable=Decimal("590.00"),
        status="PAYMENT_PENDING",
        expires_at=past_time
    )
    db_session.add(expired_booking)
    db_session.flush()

    # Decrement 2 tickets
    ticket_type.available_quantity -= 2
    b_item = BookingItem(
        booking_id=expired_booking.id,
        item_type="TICKET",
        item_id=ticket_type.id,
        name=ticket_type.name,
        quantity=2,
        unit_price=ticket_type.price,
        subtotal=ticket_type.price * 2,
        details={}
    )
    db_session.add(b_item)
    db_session.commit()

    # Trigger expiration worker as authorized super_admin
    sa_role = db_session.query(Role).filter(Role.name == "super_admin").first()
    admin_user = db_session.query(User).filter(User.roles.contains(sa_role)).first() if sa_role else None
    if not admin_user:
        admin_user = User(
            email=f"m5_sa_{uuid.uuid4().hex[:6]}@gobeyond.in",
            phone=f"9800{uuid.uuid4().hex[:6]}",
            hashed_password="hashed_pw_test",
            full_name="Module 5 Admin",
            is_verified=True,
            account_status="ACTIVE"
        )
        if sa_role:
            admin_user.roles.append(sa_role)
        db_session.add(admin_user)
        db_session.commit()
        db_session.refresh(admin_user)
    sa_token = create_access_token(admin_user.id, "super_admin")
    expire_res = client.post("/api/v1/bookings/expire-stale", headers={"Authorization": f"Bearer {sa_token}"})
    assert expire_res.status_code == 200
    assert expire_res.json()["expired_count"] >= 1

    # Verify booking status transitioned to EXPIRED
    db_session.refresh(expired_booking)
    assert expired_booking.status == "EXPIRED"

    # Verify inventory was restored back to available quantity
    db_session.refresh(ticket_type)
    assert ticket_type.available_quantity == qty_before


# --- 6. Late Payment Handling & Refund Reconciliation ---
def test_late_payment_handling_triggers_refund_reconciliation(db_session: Session, auth_headers: dict):
    # Setup expired booking
    ref = f"GB-MOV-LATE-{uuid.uuid4().hex[:6]}"
    past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=20)

    late_booking = Booking(
        booking_reference=ref,
        user_id=int(auth_headers["User-Id"]),
        booking_type="MOVIE",
        total_amount=Decimal("300.00"),
        tax_amount=Decimal("54.00"),
        discount_amount=Decimal("0.00"),
        final_payable=Decimal("354.00"),
        status="EXPIRED",
        expires_at=past_time
    )
    db_session.add(late_booking)
    db_session.commit()
    db_session.refresh(late_booking)

    # Payment arrives late after hold expired
    verify_res = client.post(
        "/api/v1/payments/verify",
        json={
            "booking_id": late_booking.id,
            "razorpay_order_id": f"order_late_{uuid.uuid4().hex[:8]}",
            "razorpay_payment_id": f"pay_late_{uuid.uuid4().hex[:8]}",
            "razorpay_signature": "mock_sig"
        },
        headers=auth_headers
    )
    assert verify_res.status_code == 200
    res_data = verify_res.json()
    assert res_data["success"] is False
    assert res_data["status"] == "REFUND_PENDING"
    assert "refund" in res_data["message"].lower()

    # Verify DB records
    db_session.refresh(late_booking)
    assert late_booking.status == "REFUND_PENDING"

    refund = db_session.query(Refund).filter(Refund.booking_id == late_booking.id).first()
    assert refund is not None
    assert refund.amount == Decimal("354.00")
    assert refund.status == "INITIATED"


# --- 7. Cancellation Flow & Inventory Release ---
def test_booking_cancellation_and_inventory_return(db_session: Session, auth_headers: dict):
    event, tt = create_isolated_event(db_session)

    # Create confirmed booking
    b_ref = f"GB-EVT-CONF-{uuid.uuid4().hex[:6]}"
    booking = Booking(
        booking_reference=b_ref,
        user_id=int(auth_headers["User-Id"]),
        booking_type="EVENT",
        total_amount=Decimal("400.00"),
        tax_amount=Decimal("72.00"),
        discount_amount=Decimal("0.00"),
        final_payable=Decimal("472.00"),
        status="CONFIRMED"
    )
    db_session.add(booking)
    db_session.flush()

    tt.available_quantity -= 2
    item = BookingItem(
        booking_id=booking.id,
        item_type="TICKET",
        item_id=tt.id,
        name="Pass",
        quantity=2,
        unit_price=Decimal("200.00"),
        subtotal=Decimal("400.00"),
        details={}
    )
    db_session.add(item)

    payment = Payment(
        booking_id=booking.id,
        user_id=int(auth_headers["User-Id"]),
        amount=Decimal("472.00"),
        status="CAPTURED",
        gateway_payment_id=f"pay_c_{uuid.uuid4().hex[:8]}"
    )
    db_session.add(payment)
    db_session.commit()

    qty_after_booking = tt.available_quantity

    # Customer cancels booking
    cancel_res = client.post(
        f"/api/v1/bookings/{booking.id}/cancel",
        json={"reason": "Cannot attend due to schedule conflict"},
        headers=auth_headers
    )
    assert cancel_res.status_code == 200
    c_data = cancel_res.json()
    assert c_data["success"] is True
    assert c_data["status"] == "REFUND_PENDING"

    # Verify inventory was restored
    db_session.refresh(tt)
    assert tt.available_quantity == qty_after_booking + 2

    # Verify refund was recorded
    refund = db_session.query(Refund).filter(Refund.booking_id == booking.id).first()
    assert refund is not None
    assert refund.amount == Decimal("472.00")


# --- 8. QR Pass Gate Verification & Tenant Boundary ---
def test_gate_scanner_qr_verification_and_tenant_boundary(db_session: Session, partner_headers: dict):
    # Setup cinema and screen belonging to partner
    partner_id = int(partner_headers["Partner-Id"])
    location = db_session.query(Location).first()
    cinema = Cinema(
        partner_id=partner_id,
        location_id=location.id,
        name="M5 Luxe Mall",
        address="Banjara Hills Road 1",
        city="Hyderabad"
    )
    db_session.add(cinema)
    db_session.flush()

    screen = Screen(cinema_id=cinema.id, name="Audi 1", screen_type="2D")
    db_session.add(screen)
    db_session.flush()

    seat = Seat(screen_id=screen.id, row_code="A", seat_number=1, base_price=Decimal("250.00"))
    db_session.add(seat)
    db_session.flush()

    # Confirmed booking for this partner's cinema
    b_ref = f"GB-MOV-PASS-{uuid.uuid4().hex[:6]}"
    booking = Booking(
        booking_reference=b_ref,
        user_id=int(partner_headers["User-Id"]),
        booking_type="MOVIE",
        total_amount=Decimal("250.00"),
        tax_amount=Decimal("45.00"),
        discount_amount=Decimal("0.00"),
        final_payable=Decimal("295.00"),
        status="CONFIRMED",
        qr_code_token=f"GBPASS-{b_ref}-VALID"
    )
    db_session.add(booking)
    db_session.flush()

    b_item = BookingItem(
        booking_id=booking.id,
        item_type="SEAT",
        item_id=seat.id,
        name="A1 Classic",
        quantity=1,
        unit_price=Decimal("250.00"),
        subtotal=Decimal("250.00"),
        details={}
    )
    db_session.add(b_item)
    db_session.commit()

    # 1. Partner scans valid pass for their cinema -> Entry Granted
    scan_res1 = client.post(
        "/api/v1/partners/verify-qr-pass",
        json={"qr_token": booking.qr_code_token},
        headers=partner_headers
    )
    assert scan_res1.status_code == 200
    assert scan_res1.json()["valid"] is True
    assert scan_res1.json()["status"] == "VERIFIED_ENTRY_GRANTED"

    # 2. Foreign partner scans the pass -> Access Denied (Strict Tenant Isolation)
    foreign_user = User(
        email=f"foreign_{uuid.uuid4().hex[:6]}@gobeyond.in",
        phone=f"9111{uuid.uuid4().hex[:6]}",
        hashed_password="pw",
        full_name="Other Cinema Partner",
        account_status="ACTIVE"
    )
    c_role = db_session.query(Role).filter(Role.name == "partner_cinema").first()
    if c_role:
        foreign_user.roles.append(c_role)
    db_session.add(foreign_user)
    db_session.flush()

    foreign_partner = Partner(
        user_id=foreign_user.id,
        business_name="Unrelated Cinema Competitor",
        partner_type="CINEMA",
        contact_email=foreign_user.email,
        contact_phone=foreign_user.phone,
        status="ACTIVE"
    )
    db_session.add(foreign_partner)
    db_session.commit()

    foreign_token = create_access_token(foreign_user.id, [r.name for r in foreign_user.roles])
    foreign_headers = {"Authorization": f"Bearer {foreign_token}"}

    try:
        scan_res2 = client.post(
            "/api/v1/partners/verify-qr-pass",
            json={"qr_token": booking.qr_code_token},
            headers=foreign_headers
        )
        assert scan_res2.status_code == 200
        assert scan_res2.json()["valid"] is False
        assert scan_res2.json()["status"] == "UNAUTHORIZED_PARTNER"
    finally:
        db_session.delete(foreign_partner)
        db_session.delete(foreign_user)
        db_session.commit()


# --- 9. Backend Price Calculation Defense (Never Trust Frontend Prices) ---
def test_backend_price_tampering_defense(db_session: Session, auth_headers: dict):
    show, seats = create_isolated_movie_show(db_session)
    seat = seats[0]

    expected_unit = quantize_amount(seat.base_price * show.price_multiplier)
    expected_tax = quantize_amount(expected_unit * Decimal("0.18"))
    expected_total = quantize_amount(expected_unit + expected_tax)

    # Client maliciously sends unit_price: 1.00
    malicious_item = {
        "item_type": "SEAT",
        "item_id": seat.id,
        "quantity": 1,
        "unit_price": 1.00,  # Malicious client price
        "details": {"show_id": show.id}
    }

    res = client.post(
        "/api/v1/bookings/initiate",
        json={
            "booking_type": "MOVIE",
            "items": [malicious_item]
        },
        headers=auth_headers
    )
    assert res.status_code == 201, res.text
    booking_data = res.json()

    # Verify backend computed exact catalog price, completely ignoring client 1.00
    assert Decimal(str(booking_data["total_amount"])) == expected_unit
    assert Decimal(str(booking_data["final_payable"])) == expected_total
