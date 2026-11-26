from typing import Optional, List
from pydantic import BaseModel


class LocationResponse(BaseModel):
    id: int
    name: str
    slug: str
    type: str  # CITY or LOCALITY
    parent_id: Optional[int] = None
    state: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool
    distance_km: Optional[float] = None

    class Config:
        from_attributes = True


class LocationHierarchyResponse(LocationResponse):
    sub_locations: List[LocationResponse] = []


class CityResponse(BaseModel):
    id: int
    name: str
    slug: str
    state: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    localities_count: int = 0

    class Config:
        from_attributes = True


class NearbyLocalityResponse(BaseModel):
    nearest_locality: LocationResponse
    distance_km: float
    nearby_localities: List[LocationResponse] = []


class SelectLocationRequest(BaseModel):
    locality_id: int
    city_id: Optional[int] = None


class SelectLocationResponse(BaseModel):
    success: bool
    locality: LocationResponse
    city_name: str
    persisted_for_user: bool
    message: str

