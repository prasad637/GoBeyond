import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_home_feed_success():
    """
    Test that GET /api/v1/discovery/home returns all 5 discovery verticals,
    plus curated trending and recommended feeds backed by real database records.
    """
    response = client.get("/api/v1/discovery/home")
    assert response.status_code == 200
    data = response.json()

    assert data["city_name"] == "Hyderabad"
    assert data["city_slug"] == "hyderabad"
    assert "trending" in data and len(data["trending"]) > 0
    assert "movies" in data and len(data["movies"]) > 0
    assert "restaurants" in data and len(data["restaurants"]) > 0
    assert "events" in data and len(data["events"]) > 0
    assert "sports_venues" in data and len(data["sports_venues"]) > 0
    assert "activities" in data and len(data["activities"]) > 0
    assert "recommended" in data

    # Verify movie fields
    movie = data["movies"][0]
    assert "title" in movie and "slug" in movie and "rating" in movie

    # Verify restaurant fields
    rest = data["restaurants"][0]
    assert "name" in rest and "location_name" in rest and "cost_for_two" in rest

    # Verify event fields
    event = data["events"][0]
    assert "title" in event and "lowest_price" in event

    # Verify trending item schema
    trend_item = data["trending"][0]
    assert "id" in trend_item
    assert "title" in trend_item
    assert "category" in trend_item
    assert "action_url" in trend_item


def test_home_feed_with_locality_filter():
    """
    Test that supplying locality_id filters the vertical results to that locality.
    """
    # Locality 5 corresponds to Hitec City
    response = client.get("/api/v1/discovery/home?locality_id=5")
    assert response.status_code == 200
    data = response.json()

    assert data["locality_id"] == 5
    assert data["locality_name"] == "Hitec City"

    # All returned restaurants must belong to locality 5
    for r in data["restaurants"]:
        assert r["locality_id"] == 5

    # All returned activities in locality 5
    for a in data["activities"]:
        assert a["locality_id"] == 5


def test_home_feed_with_gps_coords():
    """
    Test that supplying user GPS coordinates annotates items with distance_km.
    """
    # Coordinates in Hitec City (17.4474, 78.3762)
    response = client.get("/api/v1/discovery/home?lat=17.4474&lon=78.3762")
    assert response.status_code == 200
    data = response.json()

    # Verify that restaurants close to Hitec City have distance_km populated
    has_distance = any(r.get("distance_km") is not None for r in data["restaurants"])
    assert has_distance is True

    # Verify distance is non-negative float
    for r in data["restaurants"]:
        if r.get("distance_km") is not None:
            assert isinstance(r["distance_km"], (int, float))
            assert r["distance_km"] >= 0.0


def test_unified_search_all_categories():
    """
    Test global multi-vertical search query matching across items in all 5 verticals.
    """
    response = client.get("/api/v1/discovery/search?q=hyderabad")
    assert response.status_code == 200
    data = response.json()

    assert data["total_results"] > 0
    categories = {item["category"] for item in data["results"]}
    # Should match multiple categories
    assert len(categories) >= 2


def test_unified_search_by_category():
    """
    Test filtering unified search to specific categories.
    """
    # Dining category
    res_dining = client.get("/api/v1/discovery/search?category=DINING")
    assert res_dining.status_code == 200
    dining_data = res_dining.json()
    assert len(dining_data["results"]) > 0
    for item in dining_data["results"]:
        assert item["category"] == "DINING"
        assert item["action_label"] == "Reserve Table"

    # Movies category
    res_movies = client.get("/api/v1/discovery/search?category=MOVIES")
    assert res_movies.status_code == 200
    movies_data = res_movies.json()
    assert len(movies_data["results"]) > 0
    for item in movies_data["results"]:
        assert item["category"] == "MOVIES"
        assert item["action_label"] == "Book Tickets"

    # Events category
    res_events = client.get("/api/v1/discovery/search?category=EVENTS")
    assert res_events.status_code == 200
    events_data = res_events.json()
    assert len(events_data["results"]) > 0
    for item in events_data["results"]:
        assert item["category"] == "EVENTS"

    # Sports category
    res_sports = client.get("/api/v1/discovery/search?category=SPORTS")
    assert res_sports.status_code == 200
    sports_data = res_sports.json()
    assert len(sports_data["results"]) > 0
    for item in sports_data["results"]:
        assert item["category"] == "SPORTS"

    # Activities category
    res_act = client.get("/api/v1/discovery/search?category=ACTIVITIES")
    assert res_act.status_code == 200
    act_data = res_act.json()
    assert len(act_data["results"]) > 0
    for item in act_data["results"]:
        assert item["category"] == "ACTIVITIES"


def test_unified_search_price_filtering():
    """
    Test price range filters on search results.
    """
    # Filter for luxury dining/events >= 1500
    res_high = client.get("/api/v1/discovery/search?min_price=1500")
    assert res_high.status_code == 200
    high_items = res_high.json()["results"]
    for item in high_items:
        assert item["price_value"] >= 1500.0

    # Filter for budget activities <= 600
    res_low = client.get("/api/v1/discovery/search?max_price=600")
    assert res_low.status_code == 200
    low_items = res_low.json()["results"]
    for item in low_items:
        assert item["price_value"] <= 600.0


def test_unified_search_sorting():
    """
    Test sort_by options: rating, price_asc, price_desc, distance.
    """
    # Sort by rating desc
    res_rating = client.get("/api/v1/discovery/search?sort_by=rating")
    assert res_rating.status_code == 200
    ratings = [item["rating"] for item in res_rating.json()["results"] if item.get("rating") is not None]
    assert ratings == sorted(ratings, reverse=True)

    # Sort by price asc
    res_price_asc = client.get("/api/v1/discovery/search?sort_by=price_asc")
    assert res_price_asc.status_code == 200
    prices_asc = [item["price_value"] for item in res_price_asc.json()["results"] if item.get("price_value") is not None]
    assert prices_asc == sorted(prices_asc)

    # Sort by distance
    res_dist = client.get("/api/v1/discovery/search?lat=17.4474&lon=78.3762&sort_by=distance")
    assert res_dist.status_code == 200
    distances = [item["distance_km"] for item in res_dist.json()["results"] if item.get("distance_km") is not None]
    assert distances == sorted(distances)


def test_unified_search_pagination():
    """
    Test pagination: page, page_size, and has_more flag.
    """
    res_p1 = client.get("/api/v1/discovery/search?page=1&page_size=3")
    assert res_p1.status_code == 200
    d1 = res_p1.json()
    assert d1["page"] == 1
    assert d1["page_size"] == 3
    assert len(d1["results"]) == 3
    assert d1["has_more"] is True

    res_p2 = client.get("/api/v1/discovery/search?page=2&page_size=3")
    assert res_p2.status_code == 200
    d2 = res_p2.json()
    assert d2["page"] == 2
    assert len(d2["results"]) > 0
    # Results between page 1 and page 2 must be different items
    p1_ids = {(it["category"], it["id"]) for it in d1["results"]}
    p2_ids = {(it["category"], it["id"]) for it in d2["results"]}
    assert p1_ids.isdisjoint(p2_ids)


def test_unified_search_empty_state():
    """
    Test that querying for non-existent terms returns an empty list cleanly without errors.
    """
    res = client.get("/api/v1/discovery/search?q=NonExistentTermXYZ99999")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 0
    assert data["results"] == []
    assert data["has_more"] is False


def test_guest_browsing_without_authentication():
    """
    Verify that unauthenticated guests can freely access both home feed and unified search.
    """
    # No Authorization header supplied
    res_home = client.get("/api/v1/discovery/home")
    assert res_home.status_code == 200

    res_search = client.get("/api/v1/discovery/search?q=biryani")
    assert res_search.status_code == 200
