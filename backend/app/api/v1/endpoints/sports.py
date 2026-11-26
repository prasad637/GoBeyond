from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.sports import SportsVenue, Activity
from app.models.location import Location
from app.schemas.sports import SportsVenueResponse, ActivityResponse
from app.services.location import haversine_distance

router = APIRouter()


@router.get("/venues", response_model=List[SportsVenueResponse])
def list_sports_venues(
    sport: Optional[str] = Query(None),
    locality: Optional[str] = Query(None),
    locality_id: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("rating", description="Sort by 'rating' or 'distance'"),
    db: Session = Depends(get_db)
):
    query = db.query(SportsVenue).filter(SportsVenue.is_active == True)
    if locality_id:
        query = query.filter(SportsVenue.location_id == locality_id)
    elif locality:
        query = query.join(Location, SportsVenue.location_id == Location.id).filter(
            (Location.slug == locality) | (Location.name.ilike(f"%{locality}%"))
        )
    if search:
        query = query.filter(SportsVenue.name.ilike(f"%{search}%"))

    venues = query.all()
    results = []
    has_coords = (lat is not None and lon is not None)

    for v in venues:
        item = SportsVenueResponse.from_orm(v)
        item.location_name = v.location.name if v.location else "Hyderabad"
        item.locality_id = v.location_id
        if has_coords and v.location and v.location.latitude and v.location.longitude:
            item.distance_km = haversine_distance(lat, lon, v.location.latitude, v.location.longitude)
        item.activities = [ActivityResponse.from_orm(a) for a in v.activities if a.is_active]
        results.append(item)

    if sort_by == "distance" and has_coords:
        results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -x.rating))
    else:
        results.sort(key=lambda x: -x.rating)

    return results


@router.get("/venues/{venue_id}", response_model=SportsVenueResponse)
def get_sports_venue(venue_id: int, db: Session = Depends(get_db)):
    v = db.query(SportsVenue).filter(SportsVenue.id == venue_id, SportsVenue.is_active == True).first()
    if not v:
        raise HTTPException(status_code=404, detail="Sports venue not found")

    item = SportsVenueResponse.from_orm(v)
    item.location_name = v.location.name if v.location else "Hyderabad"
    item.activities = [ActivityResponse.from_orm(a) for a in v.activities if a.is_active]
    return item

