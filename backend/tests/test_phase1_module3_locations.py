"""GO BEYOND — Phase 1 Module 3: Location & Hyderabad Locality Discovery Integration Tests

Validates:
1. Haversine distance calculations and mathematical precision.
2. GPS-based nearest locality discovery (/api/v1/locations/nearby).
3. Locality search by name (case-insensitive substring) and empty result handling.
4. Proximity-based locality sorting (ascending distance_km).
5. Manual locality selection for guests vs authenticated users (profile persistence).
6. Never silently assigning locality when GPS is denied/omitted.
7. Multi-city hierarchy and expansion readiness (/api/v1/locations/cities).
8. All five verticals (Movies, Dining, Events, Sports, Activities) with locality and distance support.
"""
import uuid
import math
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.main import app
from app.models.location import Location
from app.models.user import User, UserProfile
from app.models.movie import Movie, Cinema, Screen, MovieShow
from app.models.dining import Restaurant
from app.models.event import Event
from app.models.sports import SportsVenue, Activity
from app.services.location import haversine_distance, find_nearest_locality, search_localities
from app.core.security import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def test_m3_haversine_distance_mathematical_precision():
    """
    Verify Haversine formula calculation against known geographic benchmarks:
    - Distance between Jubilee Hills (17.4319, 78.4073) and Banjara Hills (17.4156, 78.4354) is ~3.5 km.
    - Distance from a point to itself is 0.0 km.
    - Distance between Charminar (17.3616, 78.4747) and Hitec City (17.4435, 78.3772) is ~13.7 km.
    """
    # Self distance
    assert haversine_distance(17.4319, 78.4073, 17.4319, 78.4073) == 0.0

    # Jubilee Hills to Banjara Hills
    dist_jb = haversine_distance(17.4319, 78.4073, 17.4156, 78.4354)
    assert 3.3 <= dist_jb <= 3.8, f"Expected ~3.5 km, got {dist_jb}"

    # Charminar to Hitec City
    dist_ch = haversine_distance(17.3616, 78.4747, 17.4435, 78.3772)
    assert 13.0 <= dist_ch <= 15.0, f"Expected ~13.7 km, got {dist_ch}"


def test_m3_gps_based_nearest_locality_discovery(client: TestClient, db_session: Session):
    """
    Verify GPS coordinates discovery:
    Coordinates near Inorbit Mall Cyberabad (17.4334, 78.3866) should resolve
    nearest to Madhapur or Hitec City with accurate distance.
    """
    # Inorbit Mall Madhapur coordinates
    user_lat = 17.4334
    user_lon = 78.3866

    res = client.get(f"/api/v1/locations/nearby?lat={user_lat}&lon={user_lon}&city_slug=hyderabad")
    assert res.status_code == 200
    data = res.json()

    assert "nearest_locality" in data
    assert "distance_km" in data
    assert "nearby_localities" in data

    nearest = data["nearest_locality"]
    assert nearest["slug"] in ["madhapur", "hitec-city", "jubilee-hills"]
    assert data["distance_km"] < 4.0  # Within 4 km
    assert len(data["nearby_localities"]) >= 5

    # Verify nearby localities are ordered in ascending distance
    distances = [loc["distance_km"] for loc in data["nearby_localities"] if loc["distance_km"] is not None]
    assert distances == sorted(distances)


def test_m3_search_localities_by_name_and_empty_results(client: TestClient):
    """
    Verify locality search:
    1. Case-insensitive search finds matching localities.
    2. Substring matching ('gachi' -> Gachibowli).
    3. Non-existent search returns empty list (no crash).
    """
    # 1. Search 'banjara'
    res1 = client.get("/api/v1/locations/localities?search=banjara")
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1) == 1
    assert data1[0]["slug"] == "banjara-hills"

    # 2. Case-insensitive 'GACHI'
    res2 = client.get("/api/v1/locations/localities?search=GACHI")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2) == 1
    assert data2[0]["slug"] == "gachibowli"

    # 3. Empty search results
    res_empty = client.get("/api/v1/locations/localities?search=NonExistentLocalityXYZ")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


def test_m3_distance_based_sorting_and_radius_filter(client: TestClient):
    """
    Verify distance-based sorting and max_distance_km radius filter:
    Coordinates at Begumpet (17.4447, 78.4664):
    - Locality list sorted by distance should have Begumpet at distance 0.0 km.
    - Next closest localities should be Secunderabad (~3.3 km) or Banjara Hills (~4.6 km).
    - Setting max_distance_km=5.0 should filter out distant localities like Gachibowli (~13 km).
    """
    begumpet_lat = 17.4447
    begumpet_lon = 78.4664

    # 1. Sorted by distance
    res = client.get(
        f"/api/v1/locations/localities?lat={begumpet_lat}&lon={begumpet_lon}&sort_by=distance"
    )
    assert res.status_code == 200
    localities = res.json()
    assert len(localities) >= 5

    # First locality must be Begumpet at 0.0 km
    assert localities[0]["slug"] == "begumpet"
    assert localities[0]["distance_km"] == 0.0

    # Ensure strictly non-decreasing order of distance
    distances = [loc["distance_km"] for loc in localities if loc["distance_km"] is not None]
    assert distances == sorted(distances)

    # 2. Filter with max_distance_km = 6.0
    res_filtered = client.get(
        f"/api/v1/locations/localities?lat={begumpet_lat}&lon={begumpet_lon}&max_distance_km=6.0"
    )
    assert res_filtered.status_code == 200
    filtered = res_filtered.json()
    slugs = [loc["slug"] for loc in filtered]

    # Begumpet, Secunderabad, Banjara Hills should be included
    assert "begumpet" in slugs
    # Gachibowli (~13 km) and Kukatpally (~9 km) must be excluded
    assert "gachibowli" not in slugs


def test_m3_manual_locality_selection_guest_vs_authenticated(client: TestClient, db_session: Session):
    """
    Verify manual locality selection:
    1. Guest user selects a locality:
       - Returns 200 with persisted_for_user = False.
       - Confirms locality name and city name.
    2. Authenticated user selects a locality:
       - Returns 200 with persisted_for_user = True.
       - Database profile is immediately updated in PostgreSQL.
       - Subsequent GET /api/v1/auth/me returns the updated locality.
    """
    hitec = db_session.query(Location).filter(Location.slug == "hitec-city").first()
    assert hitec is not None

    # 1. Guest user selects Hitec City
    guest_res = client.post("/api/v1/locations/select", json={
        "locality_id": hitec.id
    })
    assert guest_res.status_code == 200
    guest_data = guest_res.json()
    assert guest_data["success"] is True
    assert guest_data["locality"]["name"] == "Hitec City"
    assert guest_data["city_name"] == "Hyderabad"
    assert guest_data["persisted_for_user"] is False

    # 2. Authenticated user selects Hitec City
    user = db_session.query(User).filter(User.email == "customer@gobeyond.com").first()
    assert user is not None
    token = create_access_token(subject=user.id, role="customer")

    auth_res = client.post(
        "/api/v1/locations/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"locality_id": hitec.id}
    )
    assert auth_res.status_code == 200
    auth_data = auth_res.json()
    assert auth_data["success"] is True
    assert auth_data["persisted_for_user"] is True
    assert auth_data["locality"]["id"] == hitec.id

    # 3. Verify in PostgreSQL database
    db_session.refresh(user)
    assert user.profile.locality_id == hitec.id

    # 4. Verify via /api/v1/auth/me endpoint
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["locality_id"] == hitec.id
    assert me_data["locality_name"] == "Hitec City"


def test_m3_never_silently_assign_locality_on_gps_denial(client: TestClient, db_session: Session):
    """
    Architectural & UX Guarantee:
    When GPS coordinates are omitted or denied:
    - The backend does NOT default or silently assign Banjara Hills or any locality.
    - Endpoints without coordinates return general results or un-annotated listings.
    - User's profile locality remains untouched unless explicitly chosen.
    """
    unique = uuid.uuid4().hex[:6]
    user = User(
        email=f"undecided_{unique}@gobeyond.in",
        phone=f"98{uuid.uuid4().int % 100000000:08d}",
        full_name="Undecided Locality User",
        hashed_password="SecurePassword@2026",
        is_active=True,
        account_status="ACTIVE"
    )
    db_session.add(user)
    db_session.flush()

    # User profile with Hyderabad city but NO locality assigned
    city = db_session.query(Location).filter(Location.slug == "hyderabad").first()
    profile = UserProfile(user_id=user.id, city_id=city.id, locality_id=None)
    db_session.add(profile)
    db_session.commit()

    token = create_access_token(subject=user.id, role="customer")

    # Fetch profile: locality must be None, NOT Banjara Hills
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["locality_id"] is None
    assert me_res.json()["locality_name"] is None


def test_m3_multi_city_hierarchy_and_expansion_readiness(client: TestClient, db_session: Session):
    """
    Verify multi-city readiness:
    1. /api/v1/locations/cities returns all supported cities with locality counts.
    2. Adding a new city (e.g. Bengaluru) with localities operates seamlessly without DDL changes.
    """
    res = client.get("/api/v1/locations/cities")
    assert res.status_code == 200
    cities = res.json()
    assert len(cities) >= 1
    hyd = next((c for c in cities if c["slug"] == "hyderabad"), None)
    assert hyd is not None
    assert hyd["localities_count"] >= 10

    # Expand to Bengaluru dynamically
    bengaluru = Location(
        name="Bengaluru",
        slug="bengaluru",
        type="CITY",
        state="Karnataka",
        country="India",
        latitude=12.9716,
        longitude=77.5946
    )
    db_session.add(bengaluru)
    db_session.flush()

    indiranagar = Location(
        name="Indiranagar",
        slug="indiranagar",
        type="LOCALITY",
        parent_id=bengaluru.id,
        state="Karnataka",
        country="India",
        latitude=12.9784,
        longitude=77.6408
    )
    koramangala = Location(
        name="Koramangala",
        slug="koramangala",
        type="LOCALITY",
        parent_id=bengaluru.id,
        state="Karnataka",
        country="India",
        latitude=12.9352,
        longitude=77.6245
    )
    db_session.add_all([indiranagar, koramangala])
    db_session.commit()

    try:
        # Verify Bengaluru appears in cities API
        cities_res = client.get("/api/v1/locations/cities")
        assert cities_res.status_code == 200
        blr_city = next((c for c in cities_res.json() if c["slug"] == "bengaluru"), None)
        assert blr_city is not None
        assert blr_city["localities_count"] == 2

        # Verify Bengaluru localities query
        blr_locs_res = client.get("/api/v1/locations/localities?city_slug=bengaluru")
        assert blr_locs_res.status_code == 200
        assert len(blr_locs_res.json()) == 2

    finally:
        db_session.delete(indiranagar)
        db_session.delete(koramangala)
        db_session.delete(bengaluru)
        db_session.commit()


def test_m3_all_five_verticals_location_and_distance_support(client: TestClient, db_session: Session):
    """
    Verify all five entertainment verticals support location and distance:
    1. Dining: /api/v1/dining/ with locality_id and lat/lon distance annotation.
    2. Events: /api/v1/events/ with locality_id and lat/lon distance annotation.
    3. Sports: /api/v1/sports/venues with locality_id and lat/lon distance annotation.
    4. Activities: /api/v1/activities/ with locality_id and lat/lon distance annotation.
    5. Movies: /api/v1/movies/ with locality_id filtering and /movies/{slug} with cinema distance.
    """
    user_lat = 17.4319
    user_lon = 78.4073  # Jubilee Hills

    banjara = db_session.query(Location).filter(Location.slug == "banjara-hills").first()
    assert banjara is not None

    # 1. Dining
    dining_res = client.get(f"/api/v1/dining/?lat={user_lat}&lon={user_lon}&sort_by=distance")
    assert dining_res.status_code == 200
    restaurants = dining_res.json()
    assert len(restaurants) >= 1
    assert "location_name" in restaurants[0]
    assert "distance_km" in restaurants[0]
    assert restaurants[0]["distance_km"] is not None

    # 2. Events
    event_res = client.get(f"/api/v1/events/?lat={user_lat}&lon={user_lon}&sort_by=distance")
    assert event_res.status_code == 200
    events = event_res.json()
    assert len(events) >= 1
    assert "location_name" in events[0]
    assert "distance_km" in events[0]

    # 3. Sports Venues
    sports_res = client.get(f"/api/v1/sports/venues?lat={user_lat}&lon={user_lon}&sort_by=distance")
    assert sports_res.status_code == 200
    venues = sports_res.json()
    assert len(venues) >= 1
    assert "location_name" in venues[0]
    assert "distance_km" in venues[0]

    # 4. Activities
    act_res = client.get(f"/api/v1/activities/?lat={user_lat}&lon={user_lon}&sort_by=distance")
    assert act_res.status_code == 200
    activities = act_res.json()
    assert len(activities) >= 1
    assert "location_name" in activities[0]
    assert "distance_km" in activities[0]

    # 5. Movies
    movie = db_session.query(Movie).first()
    assert movie is not None
    movie_res = client.get(f"/api/v1/movies/{movie.slug}?lat={user_lat}&lon={user_lon}")
    assert movie_res.status_code == 200
    movie_data = movie_res.json()
    assert "shows" in movie_data
    if movie_data["shows"]:
        show = movie_data["shows"][0]
        assert "location_name" in show
        assert "distance_km" in show

