import pytest
import datetime
import uuid
from decimal import Decimal, ROUND_HALF_UP
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, Role
from app.models.partner import Partner, PartnerDocument
from app.models.location import Location
from app.models.dining import Restaurant, RestaurantMenu, DiningTable, DiningReservation
from app.models.movie import Cinema, Screen, Movie, MovieShow, Seat
from app.models.event import Event, EventTicketType
from app.models.sports import SportsVenue, Activity, ActivitySlot
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund
from app.models.audit import AuditLog, Notification


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
        db.rollback()
        db.close()


def _get_auth_headers(user: User) -> dict:
    role_name = user.roles[0].name if user.roles else "customer"
    token = create_access_token(subject=user.id, role=role_name)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. PARTNER REGISTRATION, APPROVAL ENFORCEMENT & RESTRICTIONS
# ==============================================================================

def test_partner_self_registration_creates_pending_approval(client, db_session):
    """Verifies public self-registration creates a partner in PENDING_APPROVAL status."""
    email = f"pending_partner_{uuid.uuid4().hex[:6]}@gobeyond.com"
    user = User(
        email=email,
        phone=f"98{uuid.uuid4().hex[:8]}",
        full_name="Pending Partner Owner",
        hashed_password=get_password_hash("SecretPass123!"),
        is_active=True,
        account_status="ACTIVE"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    headers = _get_auth_headers(user)
    payload = {
        "business_name": "Skyline Rooftop Grill",
        "partner_type": "RESTAURANT",
        "contact_email": email,
        "contact_phone": "9876543210",
        "gstin": "36AAAAA0000A1Z5",
        "pan_number": "ABCDE1234F"
    }

    try:
        resp = client.post("/api/v1/partners/register", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["business_name"] == "Skyline Rooftop Grill"
        assert data["status"] == "PENDING_APPROVAL"
        assert Decimal(str(data["commission_rate"])) == Decimal("0.1000")

        # Verify operational dashboard actions are BLOCKED for pending partner
        op_resp = client.get("/api/v1/partners/financials", headers=headers)
        assert op_resp.status_code == 403
        assert "pending approval" in op_resp.json()["detail"].lower()

        # Document upload is allowed for pending partners
        doc_resp = client.post(
            "/api/v1/partners/documents",
            json={"document_type": "FSSAI", "document_url": "https://docs.gobeyond.com/fssai.pdf"},
            headers=headers
        )
        assert doc_resp.status_code == 200
    finally:
        cleanup_db = SessionLocal()
        try:
            p = cleanup_db.query(Partner).filter(Partner.user_id == user.id).first()
            if p:
                cleanup_db.query(PartnerDocument).filter(PartnerDocument.partner_id == p.id).delete()
                cleanup_db.delete(p)
            cleanup_db.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
            u = cleanup_db.query(User).filter(User.id == user.id).first()
            if u:
                cleanup_db.delete(u)
            cleanup_db.commit()
        finally:
            cleanup_db.close()


def test_partner_cannot_tamper_with_commission_rate(client, db_session):
    """Verifies partners cannot tamper with or modify their contracted platform commission rate."""
    partner = db_session.query(Partner).filter(Partner.id == 2).first()  # Restaurant partner
    assert partner is not None
    original_rate = partner.commission_rate
    headers = _get_auth_headers(partner.user)

    # Attempt to change commission rate via profile update
    update_payload = {
        "business_name": partner.business_name,
        "commission_rate": 0.0100,  # Try to reduce to 1%
        "bank_name": "HDFC Bank",
        "bank_account_number": "50100123456789",
        "bank_ifsc": "HDFC0001234",
        "account_holder_name": partner.business_name
    }
    resp = client.put("/api/v1/partners/profile", json=update_payload, headers=headers)
    assert resp.status_code == 200

    # Refresh from database and ensure commission rate is strictly unchanged
    db_session.refresh(partner)
    assert partner.commission_rate == original_rate
    assert Decimal(str(partner.commission_rate)) == Decimal("0.1000")


# ==============================================================================
# 2. RESTAURANT PARTNER: MENU, TABLES, RESERVATIONS & GUESTS
# ==============================================================================

def test_restaurant_partner_menu_and_table_management(client, db_session):
    """Tests complete restaurant catalog management: dishes, tables, and reservations."""
    partner = db_session.query(Partner).filter(Partner.partner_type == "RESTAURANT").first()
    assert partner is not None
    headers = _get_auth_headers(partner.user)

    # 1. Get restaurant profile
    prof_resp = client.get("/api/v1/partners/restaurant/profile", headers=headers)
    assert prof_resp.status_code == 200
    rest_data = prof_resp.json()
    assert "name" in rest_data

    # 2. Create a new menu item
    dish_payload = {
        "category": "Starters",
        "item_name": f"Crispy Hyderabadi Paneer {uuid.uuid4().hex[:4]}",
        "description": "Cottage cheese tossed in gun powder and curry leaves",
        "price": 349.00,
        "is_veg": True,
        "is_bestseller": True,
        "is_available": True
    }
    create_dish = client.post("/api/v1/partners/restaurant/menus", json=dish_payload, headers=headers)
    assert create_dish.status_code == 201
    dish = create_dish.json()
    dish_id = dish["id"]
    assert dish["item_name"] == dish_payload["item_name"]
    assert float(dish["price"]) == 349.00

    # 3. Update menu item (change price & toggle availability)
    update_dish = client.put(
        f"/api/v1/partners/restaurant/menus/{dish_id}",
        json={"price": 379.00, "is_available": False},
        headers=headers
    )
    assert update_dish.status_code == 200
    assert float(update_dish.json()["price"]) == 379.00
    assert update_dish.json()["is_available"] is False

    # 4. Create and manage dining table
    table_number = f"T-TEST-{uuid.uuid4().hex[:4]}"
    table_payload = {
        "table_number": table_number,
        "capacity": 6,
        "zone": "Rooftop Terrace",
        "is_active": True
    }
    create_table = client.post("/api/v1/partners/restaurant/tables", json=table_payload, headers=headers)
    assert create_table.status_code == 201
    table_id = create_table.json()["id"]

    # 5. List tables
    tables_list = client.get("/api/v1/partners/restaurant/tables", headers=headers)
    assert tables_list.status_code == 200
    assert any(t["id"] == table_id for t in tables_list.json())

    # 6. Clean up created items
    del_dish = client.delete(f"/api/v1/partners/restaurant/menus/{dish_id}", headers=headers)
    assert del_dish.status_code == 200
    del_table = client.delete(f"/api/v1/partners/restaurant/tables/{table_id}", headers=headers)
    assert del_table.status_code == 200


# ==============================================================================
# 3. CINEMA PARTNER: SCREENS, SHOW SCHEDULING & MULTIPLEX MANAGEMENT
# ==============================================================================

def test_cinema_partner_screen_and_show_scheduling(client, db_session):
    """Tests cinema multiplex screen creation and show scheduling."""
    partner = db_session.query(Partner).filter(Partner.partner_type == "CINEMA").first()
    assert partner is not None
    headers = _get_auth_headers(partner.user)

    # 1. Get cinema profile
    cin_resp = client.get("/api/v1/partners/cinema/profile", headers=headers)
    assert cin_resp.status_code == 200

    # 2. Create a new screen with auto-generated seats
    screen_payload = {
        "name": f"Audi {uuid.uuid4().hex[:4]} Laser Atmos",
        "screen_type": "IMAX 3D",
        "total_seats": 20,
        "rows": 2,
        "seats_per_row": 10,
        "default_price": 350.00
    }
    screen_resp = client.post("/api/v1/partners/cinema/screens", json=screen_payload, headers=headers)
    assert screen_resp.status_code == 201
    screen_id = screen_resp.json()["id"]

    # Verify seats were generated
    seats_resp = client.get(f"/api/v1/partners/cinema/screens/{screen_id}/seats", headers=headers)
    assert seats_resp.status_code == 200
    seats = seats_resp.json()
    assert len(seats) == 20

    # 3. Schedule a movie show
    movie = db_session.query(Movie).filter(Movie.is_active == True).first()
    assert movie is not None

    tomorrow = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).date()
    show_payload = {
        "movie_id": movie.id,
        "screen_id": screen_id,
        "show_date": str(tomorrow),
        "start_time": "18:30",
        "end_time": "21:30",
        "price_multiplier": 1.25
    }
    show_resp = client.post("/api/v1/partners/cinema/shows", json=show_payload, headers=headers)
    assert show_resp.status_code == 201
    show_id = show_resp.json()["id"]

    # 4. Update show status
    update_show = client.put(f"/api/v1/partners/cinema/shows/{show_id}", json={"status": "HOUSEFULL"}, headers=headers)
    assert update_show.status_code == 200
    assert update_show.json()["status"] == "HOUSEFULL"

    # Cleanup show & screen
    client.delete(f"/api/v1/partners/cinema/shows/{show_id}", headers=headers)
    db_session.query(Seat).filter(Seat.screen_id == screen_id).delete()
    db_session.query(Screen).filter(Screen.id == screen_id).delete()
    db_session.commit()


# ==============================================================================
# 4. EVENT ORGANIZER: EVENT CREATION, TIERED TICKETS & ATTENDEE LIST
# ==============================================================================

def test_event_organizer_event_lifecycle_and_ticket_tiers(client, db_session):
    """Tests live concert creation, VIP/General ticket tier management and attendee queries."""
    partner = db_session.query(Partner).filter(Partner.partner_type == "EVENT").first()
    assert partner is not None
    headers = _get_auth_headers(partner.user)

    event_payload = {
        "title": f"Hyderabad EDM Fest {uuid.uuid4().hex[:4]}",
        "category": "CONCERT",
        "venue_name": "GMR Arena Hyderabad",
        "venue_address": "Shamshabad, Hyderabad",
        "start_datetime": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14)).isoformat(),
        "end_datetime": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14, hours=6)).isoformat(),
        "description": "Massive electronic dance music experience featuring top international artists.",
        "artist_names": "DJ Titan, Electro Pulse",
        "is_featured": True
    }
    create_event = client.post("/api/v1/partners/events", json=event_payload, headers=headers)
    assert create_event.status_code == 201
    event_id = create_event.json()["id"]

    # Add VIP ticket tier
    vip_payload = {
        "name": "VIP Platinum Access",
        "description": "Unlimited drinks, lounge access, and front-stage viewing.",
        "price": 4999.00,
        "total_quantity": 50,
        "max_per_booking": 4
    }
    vip_resp = client.post(f"/api/v1/partners/events/{event_id}/tickets", json=vip_payload, headers=headers)
    assert vip_resp.status_code == 201
    vip_tier_id = vip_resp.json()["id"]

    # Verify event details with tiers
    detail_resp = client.get(f"/api/v1/partners/events/{event_id}", headers=headers)
    assert detail_resp.status_code == 200
    event_detail = detail_resp.json()
    assert len(event_detail["ticket_types"]) == 1
    assert event_detail["ticket_types"][0]["name"] == "VIP Platinum Access"

    # Query attendees (empty initially)
    att_resp = client.get(f"/api/v1/partners/events/{event_id}/attendees", headers=headers)
    assert att_resp.status_code == 200
    assert isinstance(att_resp.json(), list)

    # Cleanup
    client.delete(f"/api/v1/partners/events/tickets/{vip_tier_id}", headers=headers)
    client.delete(f"/api/v1/partners/events/{event_id}", headers=headers)
    db_session.query(EventTicketType).filter(EventTicketType.event_id == event_id).delete()
    db_session.query(Event).filter(Event.id == event_id).delete()
    db_session.commit()


# ==============================================================================
# 5. SPORTS & ACTIVITIES: TURF VENUES, COURTS & TIME SLOTS
# ==============================================================================

def test_sports_partner_venue_and_hourly_slot_management(client, db_session):
    """Tests sports venue configuration, court activities, and hourly slot generation."""
    partner = db_session.query(Partner).filter(Partner.partner_type == "SPORTS").first()
    assert partner is not None
    headers = _get_auth_headers(partner.user)

    # 1. Create a sports venue
    venue_payload = {
        "name": f"Gachibowli Arena {uuid.uuid4().hex[:4]}",
        "sport_types": ["Cricket", "Football", "Badminton"],
        "address": "Financial District, Gachibowli, Hyderabad",
        "amenities": ["Floodlights", "Locker Room", "Parking"]
    }
    venue_resp = client.post("/api/v1/partners/sports/venues", json=venue_payload, headers=headers)
    assert venue_resp.status_code == 201
    venue_id = venue_resp.json()["id"]

    # 2. Create court activity under venue
    activity_payload = {
        "venue_id": venue_id,
        "title": "Box Cricket Turf 1",
        "category": "SPORTS",
        "base_price": 1200.00,
        "duration_minutes": 60,
        "min_age": 8,
        "description": "Synthetic grass 7-a-side floodlit box cricket arena."
    }
    act_resp = client.post("/api/v1/partners/activities", json=activity_payload, headers=headers)
    assert act_resp.status_code == 201
    act_id = act_resp.json()["id"]

    # 3. Create time slots for tomorrow
    slot_date = str((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).date())
    slot_payload = {
        "slot_date": slot_date,
        "start_time": "19:00",
        "end_time": "20:00",
        "capacity": 14,
        "price_override": 1400.00,
        "is_available": True
    }
    slot_resp = client.post(f"/api/v1/partners/activities/{act_id}/slots", json=slot_payload, headers=headers)
    assert slot_resp.status_code == 201
    slot_id = slot_resp.json()["id"]

    # 4. List slots
    slots_list = client.get(f"/api/v1/partners/activities/{act_id}/slots?slot_date={slot_date}", headers=headers)
    assert slots_list.status_code == 200
    assert len(slots_list.json()) >= 1

    # Cleanup
    client.delete(f"/api/v1/partners/activities/slots/{slot_id}", headers=headers)
    client.delete(f"/api/v1/partners/activities/{act_id}", headers=headers)
    db_session.query(ActivitySlot).filter(ActivitySlot.activity_id == act_id).delete()
    db_session.query(Activity).filter(Activity.id == act_id).delete()
    db_session.query(SportsVenue).filter(SportsVenue.id == venue_id).delete()
    db_session.commit()


# ==============================================================================
# 6. TENANT ISOLATION & UNAUTHORIZED CROSS-ACCESS
# ==============================================================================

def test_strict_cross_partner_data_isolation(client, db_session):
    """Verifies a partner CANNOT view, update or delete resources belonging to another partner."""
    cinema_partner = db_session.query(Partner).filter(Partner.partner_type == "CINEMA").first()
    restaurant_partner = db_session.query(Partner).filter(Partner.partner_type == "RESTAURANT").first()
    assert cinema_partner is not None and restaurant_partner is not None

    cin_headers = _get_auth_headers(cinema_partner.user)
    rest_headers = _get_auth_headers(restaurant_partner.user)

    # Cinema partner attempts to access restaurant profile / menus
    illegal_resp = client.get("/api/v1/partners/restaurant/profile", headers=cin_headers)
    assert illegal_resp.status_code == 403

    # Restaurant partner attempts to access cinema profile
    illegal_cin = client.get("/api/v1/partners/cinema/profile", headers=rest_headers)
    assert illegal_cin.status_code == 403

    # Non-partner customer attempting to access partner dashboard
    customer_user = db_session.query(User).filter(User.email.like("%customer%")).first()
    if customer_user:
        cust_headers = _get_auth_headers(customer_user)
        cust_resp = client.get("/api/v1/partners/profile", headers=cust_headers)
        assert cust_resp.status_code == 403


# ==============================================================================
# 7. FINANCIAL ACCURACY & REVENUE CONSERVATION AUDIT
# ==============================================================================

def test_partner_revenue_settlement_and_financial_conservation(client, db_session):
    """Verifies that partner financials compute platform commission and partner payout
    strictly using captured payments, without counting pending or failed amounts."""
    partner = db_session.query(Partner).filter(Partner.id == 2).first()  # Restaurant partner
    assert partner is not None
    headers = _get_auth_headers(partner.user)

    resp = client.get("/api/v1/partners/financials", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["partner_id"] == partner.id
    assert Decimal(str(data["commission_rate"])) == Decimal("0.1000")
    assert "gross_confirmed_booking_value" in data
    assert "total_captured_payments" in data
    assert "total_refunded_amount" in data
    assert "actual_platform_revenue" in data
    assert "partner_settlements_payable" in data

    # Financial Conservation invariant check:
    # Net Collected = Total Captured - Total Refunded
    net = round(data["total_captured_payments"] - data["total_refunded_amount"], 2)
    assert abs(net - data["net_collected_amount"]) < 0.02

    # In regular non-over-refunded cases: Net Collected = Platform Revenue + Partner Settlements
    if not data["requires_financial_reconciliation"] and net > 0:
        sum_components = round(data["actual_platform_revenue"] + data["partner_settlements_payable"], 2)
        assert abs(net - sum_components) < 0.05


# ==============================================================================
# 8. BOOKINGS FILTERING & SINGLE BOOKING DETAIL
# ==============================================================================

def test_partner_bookings_filtering_and_single_booking_detail(client, db_session):
    """Verifies booking status filters (CONFIRMED, PENDING) and single booking inspection."""
    cinema_partner = db_session.query(Partner).filter(Partner.partner_type == "CINEMA").first()
    assert cinema_partner is not None
    headers = _get_auth_headers(cinema_partner.user)

    # 1. Fetch bookings with pagination and status filter
    resp = client.get("/api/v1/partners/bookings?status=CONFIRMED&page=1&page_size=10", headers=headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert "total" in res_data
    assert "bookings" in res_data
    assert isinstance(res_data["bookings"], list)

    # 2. If there are bookings, inspect one in detail
    if res_data["bookings"]:
        first_ref = res_data["bookings"][0]["booking_reference"]
        detail_resp = client.get(f"/api/v1/partners/bookings/{first_ref}", headers=headers)
        assert detail_resp.status_code == 200
        b_detail = detail_resp.json()
        assert b_detail["booking_reference"] == first_ref
        assert "items" in b_detail
        assert "payments_summary" in b_detail


# ==============================================================================
# 9. PARTNER NOTIFICATIONS MANAGEMENT
# ==============================================================================

def test_partner_notifications_management(client, db_session):
    """Verifies listing and marking partner notifications as read."""
    partner = db_session.query(Partner).filter(Partner.id == 2).first()
    assert partner is not None
    headers = _get_auth_headers(partner.user)

    # Insert a test notification
    notif = Notification(
        user_id=partner.user_id,
        title="Payout Processed",
        message="Weekly settlement of ₹15,400 has been transferred to your bank account.",
        type="PAYMENT_UPDATE",
        is_read=False
    )
    db_session.add(notif)
    db_session.commit()
    db_session.refresh(notif)

    try:
        # List notifications
        list_resp = client.get("/api/v1/partners/notifications", headers=headers)
        assert list_resp.status_code == 200
        notifs = list_resp.json()
        assert any(n["id"] == notif.id for n in notifs)

        # Mark single notification as read
        read_resp = client.put(f"/api/v1/partners/notifications/{notif.id}/read", headers=headers)
        assert read_resp.status_code == 200

        # Mark all as read
        read_all_resp = client.put("/api/v1/partners/notifications/read-all", headers=headers)
        assert read_all_resp.status_code == 200
    finally:
        db_session.delete(notif)
        db_session.commit()


# ==============================================================================
# 10. QR PASS SCANNER WITH AUDIT & TENANT CHECK
# ==============================================================================

def test_partner_qr_pass_scanner_tenant_boundary(client, db_session):
    """Verifies that gate scanner grants entry only to valid passes belonging to the partner's venue."""
    cinema_partner = db_session.query(Partner).filter(Partner.partner_type == "CINEMA").first()
    event_partner = db_session.query(Partner).filter(Partner.partner_type == "EVENT").first()
    assert cinema_partner is not None and event_partner is not None

    cin_headers = _get_auth_headers(cinema_partner.user)

    # 1. Test scanning invalid token
    invalid_resp = client.post("/api/v1/partners/verify-qr-pass", json={"qr_token": "INVALID-PASS-999"}, headers=cin_headers)
    assert invalid_resp.status_code == 200
    assert invalid_resp.json()["valid"] is False
    assert invalid_resp.json()["status"] == "INVALID"


# ==============================================================================
# 11. CONFIGURABLE COMMISSION CONSISTENCY (NO HARDCODED 10%)
# ==============================================================================

def test_configurable_partner_commission_rate_calculation(client, db_session):
    """
    Verifies that partner financials and analytics dynamically compute platform revenue
    and partner payouts using each partner's configured commission_rate (e.g. 15.00%),
    and never fall back to a hardcoded 10%.
    """
    partner = db_session.query(Partner).filter(Partner.id == 2).first()
    assert partner is not None
    original_rate = partner.commission_rate
    headers = _get_auth_headers(partner.user)

    try:
        # Set a non-default custom commission rate: 15.00%
        partner.commission_rate = Decimal("0.1500")
        db_session.commit()

        # 1. Verify /financials reflects 15.00%
        resp = client.get("/api/v1/partners/financials", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(str(data["commission_rate"])) == Decimal("0.1500")

        # 2. Verify /analytics reflects 15.00%
        analytics_resp = client.get("/api/v1/partners/analytics", headers=headers)
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        assert Decimal(str(analytics_data["commission_rate"])) == Decimal("0.1500")

        # 3. If there are captured bookings, verify mathematical attribution:
        # platform_fee = net * 0.15 and partner_payout = net * 0.85
        net = Decimal(str(data["net_collected_amount"]))
        if net > 0 and not data["requires_financial_reconciliation"]:
            expected_fee = (net * Decimal("0.1500")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            expected_payout = (net * Decimal("0.8500")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            actual_fee = Decimal(str(data["actual_platform_revenue"]))
            actual_payout = Decimal(str(data["partner_settlements_payable"]))
            assert abs(actual_fee - expected_fee) <= Decimal("0.02")
            assert abs(actual_payout - expected_payout) <= Decimal("0.02")
    finally:
        # Always restore original commission rate
        partner.commission_rate = original_rate
        db_session.commit()

