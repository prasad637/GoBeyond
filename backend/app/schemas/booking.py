from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class BookingItemCreate(BaseModel):
    item_type: str  # SEAT, TICKET, TABLE, SLOT
    item_id: int
    name: Optional[str] = ""
    quantity: int = Field(default=1, ge=1)
    unit_price: Optional[float] = Field(default=0.0, ge=0)
    details: Dict[str, Any] = {}


class CreateBookingRequest(BaseModel):
    booking_type: str  # MOVIE, DINING, EVENT, SPORTS, ACTIVITY
    items: List[BookingItemCreate]
    coupon_code: Optional[str] = None
    lock_token: Optional[str] = None
    idempotency_key: Optional[str] = None


class BookingItemResponse(BaseModel):
    id: int
    item_type: str
    item_id: int
    name: str
    quantity: int
    unit_price: float
    subtotal: float
    details: Dict[str, Any]

    class Config:
        from_attributes = True


class BookingResponse(BaseModel):
    id: int
    booking_reference: str
    user_id: int
    booking_type: str
    total_amount: float
    tax_amount: float
    discount_amount: float
    final_payable: float
    status: str
    qr_code_token: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    items: List[BookingItemResponse] = []

    class Config:
        from_attributes = True


class CancelBookingRequest(BaseModel):
    reason: str


class ApplyCouponRequest(BaseModel):
    code: str
    order_amount: float
    booking_type: str


class ApplyCouponResponse(BaseModel):
    valid: bool
    code: str
    discount_amount: float
    final_amount: float
    message: str


class ExpireStaleResponse(BaseModel):
    expired_count: int
    message: str
