from typing import Optional, List, Any
from datetime import date, time
from pydantic import BaseModel


class ActivitySlotResponse(BaseModel):
    id: int
    activity_id: int
    slot_date: date
    start_time: time
    end_time: time
    capacity: int
    booked_count: int
    available_spots: int
    price: float
    is_available: bool


class ActivityResponse(BaseModel):
    id: int
    venue_id: Optional[int] = None
    venue_name: Optional[str] = None
    title: str
    slug: str
    category: str
    description: Optional[str] = None
    base_price: float
    duration_minutes: int
    image_url: Optional[str] = None
    min_age: int
    is_active: bool
    location_name: Optional[str] = None
    locality_id: Optional[int] = None
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class ActivityDetailResponse(ActivityResponse):
    slots: List[ActivitySlotResponse] = []


class SportsVenueResponse(BaseModel):
    id: int
    name: str
    sport_types: Any
    address: str
    amenities: Any
    images: Any
    rating: float
    is_active: bool
    location_name: Optional[str] = None
    locality_id: Optional[int] = None
    distance_km: Optional[float] = None
    activities: List[ActivityResponse] = []

    class Config:
        from_attributes = True

