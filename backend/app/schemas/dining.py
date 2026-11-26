from typing import Optional, List, Any
from datetime import date, time
from pydantic import BaseModel


class MenuItemResponse(BaseModel):
    id: int
    category: str
    item_name: str
    description: Optional[str] = None
    price: float
    is_veg: bool
    is_bestseller: bool
    image_url: Optional[str] = None
    is_available: bool

    class Config:
        from_attributes = True


class DiningTableResponse(BaseModel):
    id: int
    table_number: str
    capacity: int
    zone: str
    is_active: bool

    class Config:
        from_attributes = True


class RestaurantResponse(BaseModel):
    id: int
    name: str
    slug: str
    cuisines: Any
    cost_for_two: int
    address: str
    phone: str
    timings: str
    images: Any
    rating: float
    review_count: int
    has_buffet: bool
    has_alcohol: bool
    is_pure_veg: bool
    is_active: bool
    location_name: Optional[str] = None
    locality_id: Optional[int] = None
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class RestaurantDetailResponse(RestaurantResponse):
    menus: List[MenuItemResponse] = []
    tables: List[DiningTableResponse] = []


class TableReservationRequest(BaseModel):
    restaurant_id: int
    reservation_date: date
    reservation_time: str  # e.g. "19:30:00"
    guest_count: int
    zone_preference: Optional[str] = "Indoor"
    special_requests: Optional[str] = None


class TableReservationResponse(BaseModel):
    success: bool
    reservation_id: int
    booking_reference: str
    restaurant_name: str
    table_number: str
    reservation_date: date
    reservation_time: str
    guest_count: int
    status: str

