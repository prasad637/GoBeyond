import uuid
import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.core.locks import lock_service
from app.core.database import SessionLocal
from app.models.booking import SeatLock

client = TestClient(app)


@pytest.fixture
def customer_headers():
    token = create_access_token(subject=2, role="customer")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = create_access_token(subject=1, role="super_admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def partner_headers():
    token = create_access_token(subject=3, role="partner_cinema")
    return {"Authorization": f"Bearer {token}"}


def test_locations_api():
    res = client.get("/api/v1/locations/?type=LOCALITY")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 5
    names = [loc["name"] for loc in data]
    assert "Jubilee Hills" in names
    assert "Gachibowli" in names


def test_movies_listing_and_detail():
    res = client.get("/api/v1/movies/")
    assert res.status_code == 200
    movies = res.json()
    assert len(movies) >= 2
    first_movie = movies[0]

    detail_res = client.get(f"/api/v1/movies/{first_movie['slug']}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["title"] == first_movie["title"]
    assert "shows" in detail
    assert len(detail["shows"]) >= 1


def test_movie_seats_and_locking(customer_headers):
    # Fetch shows
    movies = client.get("/api/v1/movies/").json()
    movie_slug = movies[0]["slug"]
    detail = client.get(f"/api/v1/movies/{movie_slug}").json()
    show_id = detail["shows"][0]["id"]

    # Get seat layout
    seats_res = client.get(f"/api/v1/movies/shows/{show_id}/seats")
    assert seats_res.status_code == 200
    seats = seats_res.json()
    assert len(seats) >= 12
    available = [s for s in seats if not s["is_locked"] and not s["is_booked"]]
    assert len(available) > 0
    seat_1 = available[0]

    # Lock seats
    lock_res = client.post(
        f"/api/v1/movies/shows/{show_id}/lock-seats",
        json={"show_id": show_id, "seat_ids": [seat_1["id"]]},
        headers=customer_headers
    )
    assert lock_res.status_code == 200
    lock_data = lock_res.json()
    assert lock_data["success"] is True
    assert seat_1["id"] in lock_data["locked_seat_ids"]
    assert "lock_token" in lock_data

    # Cleanup lock after verification
    lock_service.release_lock(f"show_{show_id}:seat_{seat_1['id']}", lock_data["lock_token"])
    _db = SessionLocal()
    _db.query(SeatLock).filter(SeatLock.resource_type == "MOVIE_SHOW", SeatLock.resource_id == show_id, SeatLock.identifier == f"seat_{seat_1['id']}").delete()
    _db.commit()
    _db.close()


def test_concurrent_seat_lock_prevention(customer_headers):
    # User 2 tries to lock the already locked seat
    movies = client.get("/api/v1/movies/").json()
    show_id = client.get(f"/api/v1/movies/{movies[0]['slug']}").json()["shows"][0]["id"]
    seats = client.get(f"/api/v1/movies/shows/{show_id}/seats").json()
    available = [s for s in seats if not s["is_locked"] and not s["is_booked"]]
    assert len(available) > 0
    target_seat_id = available[0]["id"]

    # First user locks it
    res1 = client.post(
        f"/api/v1/movies/shows/{show_id}/lock-seats",
        json={"show_id": show_id, "seat_ids": [target_seat_id]},
        headers=customer_headers
    )
    assert res1.status_code == 200

    try:
        # Another customer attempts to lock the exact same seat simultaneously
        other_token = create_access_token(subject=1, role="customer")
        res2 = client.post(
            f"/api/v1/movies/shows/{show_id}/lock-seats",
            json={"show_id": show_id, "seat_ids": [target_seat_id]},
            headers={"Authorization": f"Bearer {other_token}"}
        )
        assert res2.status_code == 409
        assert "currently held" in res2.json()["detail"]
    finally:
        # Cleanup lock after verification
        lock_token = res1.json()["lock_token"]
        lock_service.release_lock(f"show_{show_id}:seat_{target_seat_id}", lock_token)
        _db = SessionLocal()
        _db.query(SeatLock).filter(SeatLock.resource_type == "MOVIE_SHOW", SeatLock.resource_id == show_id, SeatLock.identifier == f"seat_{target_seat_id}").delete()
        _db.commit()
        _db.close()


def test_dining_listing_and_reservation(customer_headers):
    res = client.get("/api/v1/dining/")
    assert res.status_code == 200
    restaurants = res.json()
    assert len(restaurants) >= 2
    rest = restaurants[0]

    # Detail
    detail_res = client.get(f"/api/v1/dining/{rest['slug']}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["menus"]) >= 1

    # Reserve a table
    test_date = (datetime.date.today() + datetime.timedelta(days=(uuid.uuid4().int % 300) + 20)).isoformat()
    reserve_res = client.post(
        "/api/v1/dining/reserve",
        json={
            "restaurant_id": rest["id"],
            "reservation_date": test_date,
            "reservation_time": "20:00:00",
            "guest_count": 2,
            "special_requests": "Window table please"
        },
        headers=customer_headers
    )
    assert reserve_res.status_code == 200
    res_data = reserve_res.json()
    assert res_data["success"] is True
    assert res_data["status"] == "CONFIRMED"
    assert "GB-DINE" in res_data["booking_reference"]


def test_events_and_booking_lifecycle(customer_headers):
    events = client.get("/api/v1/events/").json()
    assert len(events) >= 2
    event = events[0]
    detail = client.get(f"/api/v1/events/{event['slug']}").json()
    ticket_type = detail["ticket_types"][0]

    # Apply promo coupon
    coupon_res = client.post(
        "/api/v1/bookings/apply-coupon",
        json={"code": "BEYOND50", "order_amount": ticket_type["price"] * 2, "booking_type": "EVENT"}
    )
    assert coupon_res.status_code == 200, f"Coupon error: {coupon_res.text}"
    coupon_data = coupon_res.json()
    assert coupon_data["valid"] is True
    assert coupon_data["discount_amount"] > 0

    # Create Booking
    booking_res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "EVENT",
            "coupon_code": "BEYOND50",
            "items": [{
                "item_type": "TICKET",
                "item_id": ticket_type["id"],
                "name": ticket_type["name"],
                "quantity": 2,
                "unit_price": ticket_type["price"],
                "details": {"event_title": event["title"]}
            }]
        },
        headers=customer_headers
    )
    assert booking_res.status_code == 201
    booking = booking_res.json()
    assert booking["status"] == "PAYMENT_PENDING"
    assert booking["final_payable"] > 0
    booking_id = booking["id"]

    # Create Razorpay Order
    order_res = client.post(
        "/api/v1/payments/create-order",
        json={"booking_id": booking_id},
        headers=customer_headers
    )
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert "order_" in order_data["order_id"]

    # Verify Payment Signature
    test_pay_id = f"pay_test_{uuid.uuid4().hex[:10]}"
    verify_res = client.post(
        "/api/v1/payments/verify-signature",
        json={
            "booking_id": booking_id,
            "razorpay_order_id": order_data["order_id"],
            "razorpay_payment_id": test_pay_id,
            "razorpay_signature": "mock_valid_signature_2026"
        },
        headers=customer_headers
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["success"] is True
    assert verify_data["status"] == "CONFIRMED"
    assert "GB-PASS-" in verify_data["qr_code_token"]

    # Verify QR Pass via Gate Scanner
    scan_res = client.post(
        "/api/v1/partners/verify-qr-pass",
        json={"qr_token": verify_data["qr_code_token"]},
        headers=customer_headers
    )
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["valid"] is True
    assert scan_data["status"] == "VERIFIED_ENTRY_GRANTED"


def test_sports_and_activities():
    venues = client.get("/api/v1/sports/venues").json()
    assert len(venues) >= 2
    activities = client.get("/api/v1/activities/").json()
    assert len(activities) >= 3

    # Activity detail with slots
    act_slug = activities[0]["slug"]
    detail = client.get(f"/api/v1/activities/{act_slug}").json()
    assert len(detail["slots"]) >= 1


def test_admin_dashboard_operations(admin_headers):
    # Stats
    stats_res = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_users"] >= 2
    assert stats["total_movies"] >= 2

    # Partners queue
    partners_res = client.get("/api/v1/admin/partners", headers=admin_headers)
    assert partners_res.status_code == 200
    partners = partners_res.json()
    assert len(partners) >= 1

    # Coupons
    coupons_res = client.get("/api/v1/admin/coupons", headers=admin_headers)
    assert coupons_res.status_code == 200

    # Create new coupon
    rand_coupon_code = f"DISC_{uuid.uuid4().hex[:6].upper()}"
    new_coupon = client.post(
        "/api/v1/admin/coupons",
        json={
            "code": rand_coupon_code,
            "description": "Dynamic test discount",
            "discount_type": "PERCENTAGE",
            "discount_value": 30.0,
            "min_order_value": 100.0,
            "max_discount": 200.0
        },
        headers=admin_headers
    )
    assert new_coupon.status_code == 200
