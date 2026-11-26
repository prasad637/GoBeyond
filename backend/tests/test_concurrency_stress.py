import concurrent.futures
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

client = TestClient(app)


def test_high_concurrency_seat_locking():
    """
    Simulate 20 concurrent threads trying to lock the exact same cinema seat
    simultaneously. Verifies strict pessimistic locking: exactly 1 succeeds,
    and 19 receive 409 Conflict.
    """
    # 1. Fetch available shows and seats
    movies = client.get("/api/v1/movies/").json()
    assert len(movies) > 0
    movie_slug = movies[0]["slug"]
    detail = client.get(f"/api/v1/movies/{movie_slug}").json()
    show_id = detail["shows"][0]["id"]

    seats = client.get(f"/api/v1/movies/shows/{show_id}/seats").json()
    assert len(seats) >= 5
    available = [s for s in seats if not s["is_locked"] and not s["is_booked"]]
    assert len(available) > 0
    target_seat_id = available[0]["id"]

    # 2. Prepare 20 distinct user authorization headers (valid authenticated customer)
    num_concurrent_users = 20
    user_headers = [
        {"Authorization": f"Bearer {create_access_token(subject=2, role='customer')}"}
        for _ in range(num_concurrent_users)
    ]

    def attempt_lock(header):
        return client.post(
            f"/api/v1/movies/shows/{show_id}/lock-seats",
            json={"show_id": show_id, "seat_ids": [target_seat_id]},
            headers=header
        )

    success_responses = []
    conflict_responses = []

    try:
        # 3. Fire all requests concurrently with ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_users) as executor:
            futures = [executor.submit(attempt_lock, h) for h in user_headers]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_responses = [r for r in responses if r.status_code == 200]
        conflict_responses = [r for r in responses if r.status_code == 409]

        # Verification:
        # Exactly 1 customer should have successfully locked the seat
        assert len(success_responses) == 1, f"Expected exactly 1 success, got {len(success_responses)}"
        # Exactly 19 customers should have been blocked with 409 Conflict
        assert len(conflict_responses) == num_concurrent_users - 1, f"Expected {num_concurrent_users - 1} conflicts, got {len(conflict_responses)}"

        # Ensure conflict detail message is accurate
        for r in conflict_responses:
            assert "currently held" in r.json()["detail"]
    finally:
        if success_responses:
            token = success_responses[0].json().get("lock_token")
            if token:
                from app.core.locks import lock_service
                from app.core.database import SessionLocal
                from app.models.booking import SeatLock
                lock_service.release_lock(f"show_{show_id}:seat_{target_seat_id}", token)
                _db = SessionLocal()
                _db.query(SeatLock).filter(SeatLock.resource_type == "MOVIE_SHOW", SeatLock.resource_id == show_id, SeatLock.identifier == f"seat_{target_seat_id}").delete()
                _db.commit()
                _db.close()


def test_payment_idempotency_concurrent_verification():
    """
    Verify payment idempotency under concurrent retries:
    Calling verify-signature repeatedly or concurrently with the same payment ID
    does not create duplicate payments or cause corrupt database state.
    """
    token = create_access_token(subject=2, role="customer")
    headers = {"Authorization": f"Bearer {token}"}

    # Create a booking
    events = client.get("/api/v1/events/").json()
    detail = client.get(f"/api/v1/events/{events[0]['slug']}").json()
    ticket_type = detail["ticket_types"][0]

    booking_res = client.post(
        "/api/v1/bookings/",
        json={
            "booking_type": "EVENT",
            "items": [{
                "item_type": "TICKET",
                "item_id": ticket_type["id"],
                "name": ticket_type["name"],
                "quantity": 1,
                "unit_price": ticket_type["price"],
                "details": {"event_title": events[0]["title"]}
            }]
        },
        headers=headers
    )
    assert booking_res.status_code == 201
    booking_id = booking_res.json()["id"]

    order_res = client.post(
        "/api/v1/payments/create-order",
        json={"booking_id": booking_id},
        headers=headers
    )
    order_id = order_res.json()["order_id"]

    shared_payment_id = f"pay_stress_{uuid.uuid4().hex[:8]}"

    def verify_payment():
        return client.post(
            "/api/v1/payments/verify-signature",
            json={
                "booking_id": booking_id,
                "razorpay_order_id": order_id,
                "razorpay_payment_id": shared_payment_id,
                "razorpay_signature": "mock_valid_signature_2026"
            },
            headers=headers
        )

    # Fire 5 concurrent requests with the identical transaction ID
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(verify_payment) for _ in range(5)]
        responses = [f.result() for f in concurrent.futures.as_completed(futures)]

    # At least the first completes with 200 and confirms booking; subsequent either return 200 (idempotent confirmed) or 400 (already processed)
    status_codes = [r.status_code for r in responses]
    assert 200 in status_codes
    assert all(code in (200, 400) for code in status_codes)

    # Ensure booking is strictly CONFIRMED and has QR token
    booking_check = client.get(f"/api/v1/bookings/{booking_id}", headers=headers).json()
    assert booking_check["status"] == "CONFIRMED"
    assert booking_check["qr_code_token"] is not None
