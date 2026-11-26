from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class TicketTypeResponse(BaseModel):
    id: int
    event_id: int
    name: str
    description: Optional[str] = None
    price: float
    total_quantity: int
    available_quantity: int
    max_per_booking: int

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id: int
    title: str
    slug: str
    category: str
    description: Optional[str] = None
    artist_names: Optional[str] = None
    venue_name: str
    venue_address: str
    start_datetime: datetime
    end_datetime: datetime
    banner_url: Optional[str] = None
    is_featured: bool
    is_active: bool
    location_name: Optional[str] = None
    locality_id: Optional[int] = None
    distance_km: Optional[float] = None
    lowest_price: Optional[float] = None

    class Config:
        from_attributes = True


class EventDetailResponse(EventResponse):
    ticket_types: List[TicketTypeResponse] = []

