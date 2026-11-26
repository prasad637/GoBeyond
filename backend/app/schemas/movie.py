from typing import Optional, List
from datetime import date, time
from pydantic import BaseModel


class SeatSchema(BaseModel):
    id: int
    screen_id: int
    row_code: str
    seat_number: int
    tier: str
    base_price: float
    is_accessible: bool
    is_locked: bool = False
    is_booked: bool = False

    class Config:
        from_attributes = True


class MovieShowResponse(BaseModel):
    id: int
    movie_id: int
    screen_id: int
    cinema_id: int
    cinema_name: str
    screen_name: str
    screen_type: str
    show_date: date
    start_time: time
    end_time: time
    price_multiplier: float
    status: str
    address: str
    location_name: Optional[str] = None
    locality_id: Optional[int] = None
    distance_km: Optional[float] = None


class MovieResponse(BaseModel):
    id: int
    title: str
    slug: str
    description: Optional[str] = None
    duration_minutes: int
    language: str
    genre: str
    censor_rating: str
    release_date: date
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    trailer_url: Optional[str] = None
    rating: float
    vote_count: int
    is_active: bool

    class Config:
        from_attributes = True


class MovieDetailResponse(MovieResponse):
    shows: List[MovieShowResponse] = []


class LockSeatsRequest(BaseModel):
    show_id: int
    seat_ids: List[int]


class LockSeatsResponse(BaseModel):
    success: bool
    lock_token: str
    show_id: int
    locked_seat_ids: List[int]
    expires_at: str
    total_amount: float

