from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field


# ==============================================================================
# PARTNER CORE & ONBOARDING SCHEMAS
# ==============================================================================

class PartnerRegisterRequest(BaseModel):
    business_name: str
    partner_type: str  # RESTAURANT, CINEMA, EVENT, SPORTS, ACTIVITIES
    contact_email: EmailStr
    contact_phone: str
    gstin: Optional[str] = None
    pan_number: Optional[str] = None


class PartnerProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    # Bank & Payout account settings
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    account_holder_name: Optional[str] = None
    # Commission rate is explicitly NEVER modifiable by partners!


class PartnerResponse(BaseModel):
    id: int
    user_id: int
    business_name: str
    partner_type: str
    contact_email: str
    contact_phone: str
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    commission_rate: float = 0.10
    status: str
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PartnerDocumentUpload(BaseModel):
    document_type: str  # GST, PAN, FSSAI, TRADE_LICENSE, ID_PROOF
    document_url: str


class PartnerDocumentResponse(BaseModel):
    id: int
    partner_id: int
    document_type: str
    document_url: str
    status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ==============================================================================
# PERFORMANCE, REVENUE & ANALYTICS SCHEMAS
# ==============================================================================

class PartnerAnalyticsResponse(BaseModel):
    partner_type: str
    business_name: str
    status: str
    commission_rate: float = 0.10
    total_listings: int = 0
    total_bookings: int = 0
    confirmed_bookings: int = 0
    pending_bookings: int = 0
    cancelled_bookings: int = 0
    refunded_bookings: int = 0
    total_revenue: float = 0.0  # Kept for backward compatibility
    gross_revenue: float = 0.0
    platform_fee: float = 0.0
    partner_payout: float = 0.0
    daily_stats: List[Dict[str, Any]] = []
    recent_bookings: List[Dict[str, Any]] = []


class PartnerFinancialTransaction(BaseModel):
    booking_id: int
    booking_reference: str
    booking_type: str
    status: str
    created_at: str
    gross_amount: float
    captured_amount: float
    refund_amount: float
    net_collected: float
    commission_rate: float
    platform_fee: float
    partner_payout: float


class PartnerFinancialsResponse(BaseModel):
    partner_id: int
    business_name: str
    partner_type: str
    commission_rate: float
    gross_confirmed_booking_value: float
    total_captured_payments: float
    total_refunded_amount: float
    net_collected_amount: float
    actual_platform_revenue: float
    partner_settlements_payable: float
    total_over_refunded_amount: float = 0.0
    requires_financial_reconciliation: bool = False
    transactions: List[PartnerFinancialTransaction] = []


# ==============================================================================
# BOOKING & RESERVATION DETAILS SCHEMAS
# ==============================================================================

class BookingItemDetail(BaseModel):
    id: int
    item_type: str
    name: str
    quantity: int
    unit_price: float
    subtotal: float
    details: Dict[str, Any] = {}


class PartnerBookingDetail(BaseModel):
    id: int
    booking_reference: str
    booking_type: str
    status: str
    customer_id: int
    customer_name: str
    customer_email: str
    customer_phone: str
    total_amount: float
    discount_amount: float
    tax_amount: float
    final_payable: float
    created_at: str
    qr_code_token: Optional[str] = None
    items: List[BookingItemDetail] = []
    payments_summary: List[Dict[str, Any]] = []
    refunds_summary: List[Dict[str, Any]] = []


# ==============================================================================
# VERTICAL: RESTAURANT SCHEMAS
# ==============================================================================

class RestaurantProfileUpdate(BaseModel):
    name: Optional[str] = None
    cuisines: Optional[List[str]] = None
    cost_for_two: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    timings: Optional[str] = None
    images: Optional[List[str]] = None
    has_buffet: Optional[bool] = None
    has_alcohol: Optional[bool] = None
    is_pure_veg: Optional[bool] = None
    is_active: Optional[bool] = None


class RestaurantMenuCreate(BaseModel):
    category: str
    item_name: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    is_veg: bool = True
    is_bestseller: bool = False
    image_url: Optional[str] = None
    is_available: bool = True


class RestaurantMenuUpdate(BaseModel):
    category: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    is_veg: Optional[bool] = None
    is_bestseller: Optional[bool] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None


class DiningTableCreate(BaseModel):
    table_number: str
    capacity: int = Field(..., gt=0)
    zone: str = "Indoor"
    is_active: bool = True


class DiningTableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = Field(None, gt=0)
    zone: Optional[str] = None
    is_active: Optional[bool] = None


class ReservationStatusUpdate(BaseModel):
    status: str  # CONFIRMED, SEATED, CANCELLED, NO_SHOW


# ==============================================================================
# VERTICAL: CINEMA SCHEMAS
# ==============================================================================

class CinemaProfileUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    amenities: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ScreenCreate(BaseModel):
    name: str
    screen_type: str = "2D"  # 2D, 3D, IMAX 3D, 4DX
    total_seats: int = 50
    rows: int = 5
    seats_per_row: int = 10
    default_price: float = 250.0


class MovieShowCreate(BaseModel):
    movie_id: int
    screen_id: int
    show_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM or HH:MM:SS
    end_time: str  # HH:MM or HH:MM:SS
    price_multiplier: float = 1.0


class MovieShowUpdate(BaseModel):
    price_multiplier: Optional[float] = None
    status: Optional[str] = None  # SCHEDULED, HOUSEFULL, CANCELLED, COMPLETED


class SeatUpdate(BaseModel):
    tier: Optional[str] = None
    base_price: Optional[float] = None
    is_accessible: Optional[bool] = None


# ==============================================================================
# VERTICAL: EVENTS SCHEMAS
# ==============================================================================

class EventCreate(BaseModel):
    title: str
    category: str = "CONCERT"  # CONCERT, COMEDY, FESTIVAL, THEATRE, WORKSHOP
    venue_name: str
    venue_address: str
    start_datetime: str  # ISO string or YYYY-MM-DD HH:MM:SS
    end_datetime: str
    description: Optional[str] = None
    artist_names: Optional[str] = None
    banner_url: Optional[str] = None
    location_id: Optional[int] = None
    is_featured: bool = False


class EventUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    description: Optional[str] = None
    artist_names: Optional[str] = None
    banner_url: Optional[str] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None


class EventTicketTypeCreate(BaseModel):
    name: str  # Early Bird, General Admission, VIP Lounge
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    total_quantity: int = Field(..., gt=0)
    max_per_booking: int = 10


class EventTicketTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    total_quantity: Optional[int] = Field(None, gt=0)
    available_quantity: Optional[int] = Field(None, ge=0)
    max_per_booking: Optional[int] = None


# ==============================================================================
# VERTICAL: SPORTS & ACTIVITIES SCHEMAS
# ==============================================================================

class SportsVenueCreate(BaseModel):
    name: str
    sport_types: List[str] = []
    address: str
    amenities: List[str] = []
    images: List[str] = []
    location_id: Optional[int] = None


class SportsVenueUpdate(BaseModel):
    name: Optional[str] = None
    sport_types: Optional[List[str]] = None
    address: Optional[str] = None
    amenities: Optional[List[str]] = None
    images: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ActivityCreate(BaseModel):
    title: str
    category: str = "SPORTS"  # SPORTS, GAMING_ZONE, AMUSEMENT, ADVENTURE
    base_price: float = Field(..., ge=0)
    duration_minutes: int = 60
    min_age: int = 5
    description: Optional[str] = None
    image_url: Optional[str] = None
    location_id: Optional[int] = None
    venue_id: Optional[int] = None


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    base_price: Optional[float] = Field(None, ge=0)
    duration_minutes: Optional[int] = None
    min_age: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class ActivitySlotCreate(BaseModel):
    slot_date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    capacity: int = Field(10, gt=0)
    price_override: Optional[float] = None
    is_available: bool = True


class ActivitySlotUpdate(BaseModel):
    capacity: Optional[int] = Field(None, gt=0)
    price_override: Optional[float] = None
    is_available: Optional[bool] = None


# ==============================================================================
# QR VERIFICATION & NOTIFICATIONS
# ==============================================================================

class QRVerificationRequest(BaseModel):
    qr_token: str


class QRVerificationResponse(BaseModel):
    valid: bool
    booking_reference: str
    booking_type: str
    customer_name: str
    status: str
    items: List[Dict[str, Any]] = []
    message: str
