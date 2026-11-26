from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.location import Location
from app.models.user import User, UserProfile
from app.schemas.location import (
    LocationResponse,
    LocationHierarchyResponse,
    CityResponse,
    NearbyLocalityResponse,
    SelectLocationRequest,
    SelectLocationResponse
)
from app.services.location import (
    search_localities,
    find_nearest_locality,
    haversine_distance,
    get_city_by_slug
)
from app.api.deps import get_optional_current_user
from app.core.cache import CacheService

router = APIRouter()


@router.get("/cities", response_model=List[CityResponse])
def get_cities(db: Session = Depends(get_db)):
    """
    Returns all active cities supported by GO BEYOND, ready for multi-city expansion.
    Includes locality count for each city.
    """
    cities = db.query(Location).filter(
        Location.type == "CITY",
        Location.is_active == True
    ).order_by(Location.name).all()

    result = []
    for c in cities:
        count = db.query(Location).filter(
            Location.parent_id == c.id,
            Location.type == "LOCALITY",
            Location.is_active == True
        ).count()
        result.append(CityResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            state=c.state,
            country=c.country,
            latitude=c.latitude,
            longitude=c.longitude,
            localities_count=count
        ))
    return result


@router.get("/localities", response_model=List[LocationResponse])
def get_localities(
    city_slug: str = Query("hyderabad", description="City slug (default: hyderabad)"),
    search: Optional[str] = Query(None, description="Search locality by name"),
    lat: Optional[float] = Query(None, description="User GPS latitude for distance sorting"),
    lon: Optional[float] = Query(None, description="User GPS longitude for distance sorting"),
    max_distance_km: Optional[float] = Query(None, description="Filter localities within radius (km)"),
    sort_by: str = Query("name", description="Sort order: 'name' or 'distance'"),
    db: Session = Depends(get_db)
):
    """
    Returns localities in a city with name search, Haversine distance calculation,
    and distance-based sorting.
    """
    is_default_query = (not search and lat is None and lon is None and not max_distance_km and sort_by == 'name')
    cache_key = f"locations:localities:{city_slug}"

    if is_default_query:
        cached = CacheService.get(cache_key)
        if cached:
            return [LocationResponse(**loc) for loc in cached]

    items = search_localities(
        db=db,
        city_slug=city_slug,
        search=search,
        lat=lat,
        lon=lon,
        max_distance_km=max_distance_km,
        sort_by=sort_by
    )

    response_items = []
    for item in items:
        loc = item["location"]
        resp = LocationResponse.from_orm(loc)
        resp.distance_km = item["distance_km"]
        response_items.append(resp)

    if is_default_query:
        CacheService.set(cache_key, [r.model_dump() for r in response_items], ttl_seconds=300)

    return response_items


@router.get("/nearby", response_model=NearbyLocalityResponse)
def get_nearby_locality(
    lat: float = Query(..., description="Current GPS latitude"),
    lon: float = Query(..., description="Current GPS longitude"),
    city_slug: str = Query("hyderabad", description="City slug"),
    db: Session = Depends(get_db)
):
    """
    Given GPS coordinates, discovers the nearest locality in the city using Haversine distance.
    Also returns other nearby localities sorted by proximity.
    """
    nearest, dist = find_nearest_locality(db, lat=lat, lon=lon, city_slug=city_slug)
    if not nearest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No localities found in city '{city_slug}'."
        )

    all_nearby = search_localities(
        db=db,
        city_slug=city_slug,
        lat=lat,
        lon=lon,
        sort_by="distance"
    )

    nearby_list = []
    for item in all_nearby:
        loc = item["location"]
        resp = LocationResponse.from_orm(loc)
        resp.distance_km = item["distance_km"]
        nearby_list.append(resp)

    nearest_resp = LocationResponse.from_orm(nearest)
    nearest_resp.distance_km = dist

    return NearbyLocalityResponse(
        nearest_locality=nearest_resp,
        distance_km=dist or 0.0,
        nearby_localities=nearby_list
    )


@router.post("/select", response_model=SelectLocationResponse)
def select_location(
    req: SelectLocationRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Selects a locality for browsing and discovery.
    - If user is authenticated: persists selection to user's database profile.
    - If user is a guest: confirms selection so frontend can persist in client storage.
    """
    locality = db.query(Location).filter(
        Location.id == req.locality_id,
        Location.type == "LOCALITY",
        Location.is_active == True
    ).first()

    if not locality:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The specified locality does not exist or is inactive."
        )

    city = locality.parent or (db.query(Location).filter(Location.id == locality.parent_id).first() if locality.parent_id else None)
    city_name = city.name if city else "Hyderabad"
    city_id = city.id if city else locality.parent_id

    persisted = False
    if current_user:
        profile = current_user.profile
        if not profile:
            profile = UserProfile(user_id=current_user.id)
            db.add(profile)
            db.flush()

        profile.locality_id = locality.id
        if city_id:
            profile.city_id = city_id
        db.commit()
        persisted = True

    loc_resp = LocationResponse.from_orm(locality)

    return SelectLocationResponse(
        success=True,
        locality=loc_resp,
        city_name=city_name,
        persisted_for_user=persisted,
        message=f"Location set to {locality.name}, {city_name}." + (" (Saved to profile)" if persisted else " (Saved for guest session)")
    )


@router.get("/", response_model=List[LocationResponse])
def get_locations(
    type: Optional[str] = Query(None, description="Filter by 'CITY' or 'LOCALITY'"),
    parent_slug: Optional[str] = Query(None, description="Filter localities of a city, e.g. 'hyderabad'"),
    search: Optional[str] = Query(None, description="Optional search filter by name"),
    lat: Optional[float] = Query(None, description="GPS latitude"),
    lon: Optional[float] = Query(None, description="GPS longitude"),
    sort_by: str = Query("name", description="Sort by 'name' or 'distance'"),
    db: Session = Depends(get_db)
):
    """
    General locations query supporting city filtering, locality discovery,
    search, and distance annotation.
    """
    if type and type.upper() == "LOCALITY" and (parent_slug or search or lat):
        city_slug = parent_slug or "hyderabad"
        items = search_localities(
            db=db,
            city_slug=city_slug,
            search=search,
            lat=lat,
            lon=lon,
            sort_by=sort_by
        )
        result = []
        for it in items:
            resp = LocationResponse.from_orm(it["location"])
            resp.distance_km = it["distance_km"]
            result.append(resp)
        return result

    query = db.query(Location).filter(Location.is_active == True)
    if type:
        query = query.filter(Location.type == type.upper())
    if parent_slug:
        parent = db.query(Location).filter(Location.slug == parent_slug).first()
        if parent:
            query = query.filter(Location.parent_id == parent.id)
    if search:
        query = query.filter(func.lower(Location.name).like(f"%{search.strip().lower()}%"))

    return query.order_by(Location.name).all()


@router.get("/hyderabad/hierarchy", response_model=LocationHierarchyResponse)
def get_hyderabad_hierarchy(db: Session = Depends(get_db)):
    city = db.query(Location).filter(Location.slug == "hyderabad").first()
    if not city:
        raise HTTPException(status_code=404, detail="Hyderabad location record not found.")
    
    localities = db.query(Location).filter(Location.parent_id == city.id, Location.is_active == True).order_by(Location.name).all()
    city_data = LocationHierarchyResponse.from_orm(city)
    city_data.sub_locations = [LocationResponse.from_orm(l) for l in localities]
    return city_data
