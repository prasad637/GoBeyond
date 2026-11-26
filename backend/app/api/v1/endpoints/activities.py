from typing import List, Optional
import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.sports import Activity, ActivitySlot
from app.models.location import Location
from app.schemas.sports import ActivityResponse, ActivityDetailResponse, ActivitySlotResponse
from app.services.location import haversine_distance

router = APIRouter()


@router.get("/", response_model=List[ActivityResponse])
def list_activities(
    category: Optional[str] = Query(None, description="SPORTS, GAMING_ZONE, AMUSEMENT, ADVENTURE"),
    locality: Optional[str] = Query(None),
    locality_id: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("title", description="Sort by 'title' or 'distance'"),
    db: Session = Depends(get_db)
):
    query = db.query(Activity).filter(Activity.is_active == True)
    if category:
        query = query.filter(Activity.category == category.upper())
    if locality_id:
        query = query.filter(Activity.location_id == locality_id)
    elif locality:
        query = query.join(Location, Activity.location_id == Location.id).filter(
            (Location.slug == locality) | (Location.name.ilike(f"%{locality}%"))
        )
    if search:
        query = query.filter(Activity.title.ilike(f"%{search}%"))

    activities = query.all()
    results = []
    has_coords = (lat is not None and lon is not None)

    for a in activities:
        item = ActivityResponse.from_orm(a)
        item.venue_name = a.venue.name if a.venue else None
        item.location_name = a.location.name if a.location else "Hyderabad"
        item.locality_id = a.location_id
        if has_coords and a.location and a.location.latitude and a.location.longitude:
            item.distance_km = haversine_distance(lat, lon, a.location.latitude, a.location.longitude)
        results.append(item)

    if sort_by == "distance" and has_coords:
        results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), x.title))
    else:
        results.sort(key=lambda x: x.title)

    return results


@router.get("/{identifier}", response_model=ActivityDetailResponse)
def get_activity_detail(identifier: str, db: Session = Depends(get_db)):
    if identifier.isdigit():
        act = db.query(Activity).filter(Activity.id == int(identifier), Activity.is_active == True).first()
    else:
        act = db.query(Activity).filter(Activity.slug == identifier, Activity.is_active == True).first()

    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    slots_data = []
    for s in act.slots:
        available = max(0, s.capacity - s.booked_count)
        slots_data.append(ActivitySlotResponse(
            id=s.id,
            activity_id=s.activity_id,
            slot_date=s.slot_date,
            start_time=s.start_time,
            end_time=s.end_time,
            capacity=s.capacity,
            booked_count=s.booked_count,
            available_spots=available,
            price=s.price_override if s.price_override is not None else act.base_price,
            is_available=s.is_available and available > 0
        ))

    return ActivityDetailResponse(
        id=act.id,
        venue_id=act.venue_id,
        venue_name=act.venue.name if act.venue else None,
        title=act.title,
        slug=act.slug,
        category=act.category,
        description=act.description,
        base_price=act.base_price,
        duration_minutes=act.duration_minutes,
        image_url=act.image_url,
        min_age=act.min_age,
        is_active=act.is_active,
        location_name=act.location.name if act.location else "Hyderabad",
        slots=slots_data
    )
