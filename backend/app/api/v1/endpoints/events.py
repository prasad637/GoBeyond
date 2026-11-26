from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.event import Event, EventTicketType
from app.models.location import Location
from app.schemas.event import EventResponse, EventDetailResponse, TicketTypeResponse
from app.services.location import haversine_distance

router = APIRouter()


@router.get("/", response_model=List[EventResponse])
def list_events(
    category: Optional[str] = Query(None),
    featured_only: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    locality: Optional[str] = Query(None),
    locality_id: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    sort_by: str = Query("date", description="Sort by 'date' or 'distance'"),
    db: Session = Depends(get_db)
):
    query = db.query(Event).filter(Event.is_active == True)
    if category:
        query = query.filter(Event.category == category.upper())
    if featured_only:
        query = query.filter(Event.is_featured == True)
    if locality_id:
        query = query.filter(Event.location_id == locality_id)
    elif locality:
        query = query.join(Location, Event.location_id == Location.id).filter(
            (Location.slug == locality) | (Location.name.ilike(f"%{locality}%"))
        )
    if search:
        query = query.filter((Event.title.ilike(f"%{search}%")) | (Event.artist_names.ilike(f"%{search}%")))

    events = query.all()
    results = []
    has_coords = (lat is not None and lon is not None)

    for ev in events:
        item = EventResponse.from_orm(ev)
        item.location_name = ev.location.name if ev.location else "Hyderabad"
        item.locality_id = ev.location_id
        if has_coords and ev.location and ev.location.latitude and ev.location.longitude:
            item.distance_km = haversine_distance(lat, lon, ev.location.latitude, ev.location.longitude)
        prices = [float(tt.price) for tt in ev.ticket_types]
        item.lowest_price = min(prices) if prices else 0.0
        results.append(item)

    if sort_by == "distance" and has_coords:
        results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), x.start_datetime))
    else:
        results.sort(key=lambda x: x.start_datetime)

    return results


@router.get("/{identifier}", response_model=EventDetailResponse)
def get_event_detail(identifier: str, db: Session = Depends(get_db)):
    if identifier.isdigit():
        event = db.query(Event).filter(Event.id == int(identifier), Event.is_active == True).first()
    else:
        event = db.query(Event).filter(Event.slug == identifier, Event.is_active == True).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    detail = EventDetailResponse.from_orm(event)
    detail.location_name = event.location.name if event.location else "Hyderabad"
    prices = [float(tt.price) for tt in event.ticket_types]
    detail.lowest_price = min(prices) if prices else 0.0
    detail.ticket_types = [
        TicketTypeResponse(
            id=tt.id,
            event_id=tt.event_id,
            name=tt.name,
            description=tt.description,
            price=float(tt.price),
            total_quantity=tt.total_quantity,
            available_quantity=tt.available_quantity,
            max_per_booking=tt.max_per_booking
        )
        for tt in event.ticket_types
    ]
    return detail

