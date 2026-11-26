import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.location import Location
from app.models.movie import Movie
from app.models.sports import Activity, SportsVenue
from app.models.user import User, UserProfile
from app.seed.seed_data import run_seed

client = TestClient(app)


def _login_customer():
    resp = client.post(
        "/api/v1/auth/login",
        json={"login": "customer@gobeyond.com", "password": "Customer@123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_hyderabad_localities_city_slug_endpoint():
    """
    AUD-M1-02: Verify /locations/localities?city_slug=hyderabad returns seeded Hyderabad localities.
    """
    resp = client.get("/api/v1/locations/localities?city_slug=hyderabad")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    names = {item["name"] for item in data}
    assert "Jubilee Hills" in names
    assert "Madhapur" in names
    assert all(item["type"] == "LOCALITY" for item in data)


def test_profile_locality_preservation_and_explicit_clear():
    """
    AUD-M1-02: Verify PUT /auth/me preserves locality_id updates, syncs parent city_id,
    rejects non-existent localities cleanly, and supports explicit null clearing.
    """
    run_seed()
    token = _login_customer()
    headers = {"Authorization": f"Bearer {token}"}

    locs_resp = client.get("/api/v1/locations/localities?city_slug=hyderabad")
    assert locs_resp.status_code == 200
    locs = locs_resp.json()
    by_id = {loc["id"]: loc for loc in locs}
    by_slug = {loc["slug"]: loc for loc in locs}
    jubilee_id = by_slug["jubilee-hills"]["id"]
    madhapur_id = by_slug["madhapur"]["id"]

    # Initially seeded customer resides in Hyderabad with a valid LOCALITY (not city-in-locality bug)
    me_initial = client.get("/api/v1/auth/me", headers=headers)
    assert me_initial.status_code == 200
    initial_data = me_initial.json()
    original_loc_id = initial_data["locality_id"] or jubilee_id
    assert initial_data["city_name"] == "Hyderabad"
    assert initial_data["locality_id"] in by_id

    target_id = jubilee_id if initial_data["locality_id"] == madhapur_id else madhapur_id
    target_name = by_id[target_id]["name"]

    try:
        # Update locality and confirm persistence
        upd = client.put(
            "/api/v1/auth/me",
            headers=headers,
            json={"locality_id": target_id},
        )
        assert upd.status_code == 200
        upd_data = upd.json()
        assert upd_data["city_name"] == "Hyderabad"
        assert upd_data["locality_id"] == target_id
        assert upd_data["locality_name"] == target_name

        # Invalid locality ID must fail cleanly with 404
        bad = client.put(
            "/api/v1/auth/me",
            headers=headers,
            json={"locality_id": 9999999},
        )
        assert bad.status_code == 404

        # Explicit null clear must remove locality while keeping Hyderabad city_name
        cleared = client.put(
            "/api/v1/auth/me",
            headers=headers,
            json={"locality_id": None},
        )
        assert cleared.status_code == 200
        cleared_data = cleared.json()
        assert cleared_data["city_name"] == "Hyderabad"
        assert cleared_data["locality_id"] is None
        assert cleared_data["locality_name"] is None
    finally:
        # Restore baseline cleanly
        client.put(
            "/api/v1/auth/me",
            headers=headers,
            json={"locality_id": original_loc_id},
        )


def test_seed_media_assets_and_profile_location_integrity():
    """
    AUD-M1-05 & AUD-M1-02: Verify idempotent seed uses local Nocturne Editorial
    seed images and stores CITY vs LOCALITY cleanly on seeded customer profile.
    """
    run_seed()
    db = SessionLocal()
    try:
        cust = db.query(User).filter(User.email == "customer@gobeyond.com").first()
        assert cust is not None and cust.profile is not None
        city = db.query(Location).filter(Location.id == cust.profile.city_id).first()
        loc = db.query(Location).filter(Location.id == cust.profile.locality_id).first()
        assert city is not None and city.type == "CITY" and city.name == "Hyderabad"
        assert loc is not None and loc.type == "LOCALITY"

        for slug, expected_img in [
            ("devara-part-1", "/images/seed/movie-devara.jpg"),
            ("dune-part-two", "/images/seed/movie-dune.jpg"),
            ("pushpa-2-the-rule", "/images/seed/movie-pushpa.jpg"),
        ]:
            mov = db.query(Movie).filter(Movie.slug == slug).first()
            assert mov is not None
            assert mov.poster_url == expected_img

        apex = db.query(SportsVenue).filter(SportsVenue.name == "Apex Turf Arena: Kondapur").first()
        assert apex is not None
        assert apex.images == ["/images/seed/sports-turf.jpg"]

        turf_act = db.query(Activity).filter(Activity.slug == "floodlit-astroturf-football-apex").first()
        kart_act = db.query(Activity).filter(Activity.slug == "pitstop-high-speed-go-karting-madhapur").first()
        assert turf_act is not None and turf_act.image_url == "/images/seed/sports-turf.jpg"
        assert kart_act is not None and kart_act.image_url == "/images/seed/activity-gokart.jpg"
    finally:
        db.close()


def test_movie_seat_lock_failure_releases_preacquired_locks_and_reflects_pending_holds():
    """
    PAY-BLOCKER regression:
    1. GET /movies/shows/{show_id}/seats marks seats held by unexpired PAYMENT_PENDING bookings as is_locked=True.
    2. POST /movies/shows/{show_id}/lock-seats rejects seats already held in active pending checkouts upfront.
    3. Failed POST /bookings/ (e.g. invalid coupon) releases caller's pre-acquired lock_token cleanly without stranding locks.
    """
    run_seed()
    token = _login_customer()
    headers = {"Authorization": f"Bearer {token}"}

    seats_resp = client.get("/api/v1/movies/shows/1/seats")
    assert seats_resp.status_code == 200
    avail = [s for s in seats_resp.json() if not s["is_booked"] and not s["is_locked"]]
    assert len(avail) > 0
    seat = avail[0]

    # 1. Pre-lock seat via /lock-seats, then fail POST /bookings/ with an invalid coupon -> lock must NOT be stranded
    lock_resp = client.post(
        "/api/v1/movies/shows/1/lock-seats",
        headers=headers,
        json={"show_id": 1, "seat_ids": [seat["id"]]},
    )
    assert lock_resp.status_code == 200, lock_resp.text
    lock_token = lock_resp.json()["lock_token"]

    bad_booking = client.post(
        "/api/v1/bookings/",
        headers=headers,
        json={
            "booking_type": "MOVIE",
            "items": [
                {
                    "item_type": "SEAT",
                    "item_id": seat["id"],
                    "quantity": 1,
                    "details": {"show_id": 1},
                }
            ],
            "coupon_code": "NONEXISTENT_COUPON_XYZ",
            "lock_token": lock_token,
        },
    )
    assert bad_booking.status_code == 400

    # Seat must be immediately unlocked again
    seats_after_bad = client.get("/api/v1/movies/shows/1/seats").json()
    seat_after = next(s for s in seats_after_bad if s["id"] == seat["id"])
    assert seat_after["is_locked"] is False

    # 2. Acquire lock and create PAYMENT_PENDING booking, then report failure -> seat released for retry
    lock_resp2 = client.post(
        "/api/v1/movies/shows/1/lock-seats",
        headers=headers,
        json={"show_id": 1, "seat_ids": [seat["id"]]},
    )
    assert lock_resp2.status_code == 200, lock_resp2.text
    booking_resp = client.post(
        "/api/v1/bookings/",
        headers=headers,
        json={
            "booking_type": "MOVIE",
            "items": [
                {
                    "item_type": "SEAT",
                    "item_id": seat["id"],
                    "quantity": 1,
                    "details": {"show_id": 1},
                }
            ],
            "lock_token": lock_resp2.json()["lock_token"],
        },
    )
    assert booking_resp.status_code == 201, booking_resp.text
    booking_id = booking_resp.json()["id"]

    # While PAYMENT_PENDING, /seats reports is_locked=True and /lock-seats rejects duplicate hold
    seats_while_pending = client.get("/api/v1/movies/shows/1/seats").json()
    assert next(s for s in seats_while_pending if s["id"] == seat["id"])["is_locked"] is True
    dup_lock = client.post(
        "/api/v1/movies/shows/1/lock-seats",
        headers=headers,
        json={"show_id": 1, "seat_ids": [seat["id"]]},
    )
    assert dup_lock.status_code == 409

    # Report payment failure -> transitions booking to FAILED and releases Redis + DB seat lock
    fail_resp = client.post(
        "/api/v1/payments/report-failure",
        headers=headers,
        json={
            "booking_id": booking_id,
            "error_code": "CHECKOUT_INIT_FAULT",
            "error_description": "Test recovery release",
        },
    )
    assert fail_resp.status_code == 200, fail_resp.text
    assert fail_resp.json()["inventory_released"] is True

    seats_after_fail = client.get("/api/v1/movies/shows/1/seats").json()
    assert next(s for s in seats_after_fail if s["id"] == seat["id"])["is_locked"] is False

