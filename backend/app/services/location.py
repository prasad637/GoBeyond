"""GO BEYOND — Location & Locality Discovery Service

Handles:
1. Haversine distance calculations (in kilometers) between GPS coordinates.
2. Locality search with case-insensitive substring matching.
3. Nearest locality discovery from GPS coordinates.
4. Distance-based sorting and proximity filtering.
5. Multi-city expansion readiness (hierarchical: country -> state -> city -> locality).
"""
import math
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.location import Location


EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates using the Haversine formula.
    Returns distance in kilometers rounded to 2 decimal places.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = EARTH_RADIUS_KM * c
    return round(distance, 2)


def get_city_by_slug(db: Session, city_slug: str = "hyderabad") -> Optional[Location]:
    """Retrieves a city record by its slug."""
    return db.query(Location).filter(
        Location.type == "CITY",
        Location.slug == city_slug.lower(),
        Location.is_active == True
    ).first()


def search_localities(
    db: Session,
    city_slug: str = "hyderabad",
    search: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    max_distance_km: Optional[float] = None,
    sort_by: str = "name"  # "name" or "distance"
) -> List[Dict[str, Any]]:
    """
    Searches localities belonging to a city with optional GPS distance annotation and sorting.
    """
    city = get_city_by_slug(db, city_slug)
    if not city:
        return []

    query = db.query(Location).filter(
        Location.parent_id == city.id,
        Location.type == "LOCALITY",
        Location.is_active == True
    )

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(Location.name).like(term))

    localities = query.all()
    results = []

    has_coords = (lat is not None and lon is not None)

    for loc in localities:
        dist: Optional[float] = None
        if has_coords and loc.latitude is not None and loc.longitude is not None:
            dist = haversine_distance(lat, lon, loc.latitude, loc.longitude)
            if max_distance_km is not None and dist > max_distance_km:
                continue

        results.append({
            "location": loc,
            "distance_km": dist
        })

    # Sort results
    if sort_by == "distance" and has_coords:
        results.sort(key=lambda x: (x["distance_km"] if x["distance_km"] is not None else float("inf"), x["location"].name))
    else:
        results.sort(key=lambda x: x["location"].name)

    return results


def find_nearest_locality(
    db: Session,
    lat: float,
    lon: float,
    city_slug: str = "hyderabad"
) -> Tuple[Optional[Location], Optional[float]]:
    """
    Finds the single closest active locality in the city to the provided GPS coordinates.
    """
    city = get_city_by_slug(db, city_slug)
    if not city:
        return None, None

    localities = db.query(Location).filter(
        Location.parent_id == city.id,
        Location.type == "LOCALITY",
        Location.is_active == True,
        Location.latitude.isnot(None),
        Location.longitude.isnot(None)
    ).all()

    if not localities:
        return None, None

    nearest_loc: Optional[Location] = None
    min_distance = float("inf")

    for loc in localities:
        dist = haversine_distance(lat, lon, loc.latitude, loc.longitude)
        if dist < min_distance:
            min_distance = dist
            nearest_loc = loc

    return nearest_loc, round(min_distance, 2) if nearest_loc else None

