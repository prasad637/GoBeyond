from typing import Optional, List, Any
from pydantic import BaseModel
from app.schemas.movie import MovieResponse
from app.schemas.dining import RestaurantResponse
from app.schemas.event import EventResponse
from app.schemas.sports import SportsVenueResponse, ActivityResponse


class SearchResultItem(BaseModel):
    id: int
    title: str
    slug: str
    category: str  # "MOVIES", "DINING", "EVENTS", "SPORTS", "ACTIVITIES"
    category_label: str  # "Movies", "Dining", "Live Events", "Sports Turfs", "Activities"
    description: Optional[str] = None
    image_url: Optional[str] = None
    location_name: str
    locality_id: Optional[int] = None
    distance_km: Optional[float] = None
    rating: Optional[float] = None
    price_label: Optional[str] = None
    price_value: Optional[float] = None
    action_url: str
    action_label: str
    tags: List[str] = []


class SearchResponse(BaseModel):
    total_results: int
    page: int
    page_size: int
    has_more: bool
    results: List[SearchResultItem]


class HomeFeedResponse(BaseModel):
    city_name: str
    city_slug: str
    locality_name: Optional[str] = None
    locality_id: Optional[int] = None
    trending: List[SearchResultItem] = []
    movies: List[MovieResponse] = []
    restaurants: List[RestaurantResponse] = []
    events: List[EventResponse] = []
    sports_venues: List[SportsVenueResponse] = []
    activities: List[ActivityResponse] = []
    recommended: List[SearchResultItem] = []
