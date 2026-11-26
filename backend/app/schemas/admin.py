from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class AdminStatsResponse(BaseModel):
    total_users: int
    total_customers: int
    total_partners: int
    approved_partners: int = 0
    pending_partner_verifications: int = 0
    suspended_partners: int = 0
    total_bookings: int
    confirmed_bookings: int
    vertical_bookings: Dict[str, int] = {}
    total_revenue: float
    gross_confirmed_booking_value: float = 0.0
    total_captured_payments: float = 0.0
    total_refunded_amount: float = 0.0
    net_collected_amount: float = 0.0
    actual_platform_revenue: float = 0.0
    partner_settlements_payable: float = 0.0
    total_over_refunded_amount: float = 0.0
    over_refunded_bookings_count: int = 0
    requires_financial_reconciliation: bool = False
    total_movies: int
    total_restaurants: int
    total_events: int
    total_sports_activities: int
    daily_trends: List[Dict[str, Any]] = []
    monthly_trends: List[Dict[str, Any]] = []


class PartnerStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="APPROVED, REJECTED, SUSPENDED")
    notes: Optional[str] = None


class PartnerCommissionUpdateRequest(BaseModel):
    commission_rate: Decimal = Field(..., ge=0.0, le=1.0, description="Commission take-rate e.g. 0.1250 for 12.50%")
    notes: Optional[str] = None


class PartnerDocumentVerifyRequest(BaseModel):
    status: str = Field(..., description="VERIFIED, REJECTED")
    notes: Optional[str] = None


class AdminPartnerDetailResponse(BaseModel):
    id: int
    user_id: int
    business_name: str
    partner_type: str
    contact_email: str
    contact_phone: str
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    commission_rate: float
    status: str
    verified_at: Optional[str] = None
    created_at: Optional[str] = None
    total_listings: int = 0
    total_bookings: int = 0
    gross_booking_value: float = 0.0
    platform_fee: float = 0.0
    partner_payout: float = 0.0
    documents: List[Dict[str, Any]] = []


class AdminUserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    roles: List[str]
    is_active: bool
    is_verified: bool
    account_status: str
    created_at: Optional[str] = None
    total_bookings: int = 0
    city_name: Optional[str] = None
    locality_name: Optional[str] = None


class UserStatusUpdateRequest(BaseModel):
    account_status: str = Field(..., description="ACTIVE, SUSPENDED, DEACTIVATED")
    reason: Optional[str] = None


class AdminBookingItemDetail(BaseModel):
    id: int
    item_type: str
    item_id: int
    name: str
    quantity: int
    unit_price: float
    subtotal: float
    details: Dict[str, Any] = {}


class AdminPaymentDetail(BaseModel):
    id: int
    gateway_payment_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    amount: float
    currency: str = "INR"
    status: str
    payment_gateway: str = "RAZORPAY"
    created_at: Optional[str] = None


class AdminRefundDetail(BaseModel):
    id: int
    gateway_refund_id: Optional[str] = None
    amount: float
    reason: Optional[str] = None
    status: str
    created_at: Optional[str] = None


class AdminBookingDetailResponse(BaseModel):
    id: int
    booking_reference: str
    booking_type: str
    status: str
    total_amount: float
    tax_amount: float
    discount_amount: float
    final_payable: float
    created_at: Optional[str] = None
    customer: Dict[str, Any]
    items: List[AdminBookingItemDetail] = []
    payments: List[AdminPaymentDetail] = []
    refunds: List[AdminRefundDetail] = []
    cancellation_reason: Optional[str] = None


class AdminPaymentListItem(BaseModel):
    id: int
    booking_id: int
    booking_reference: str
    customer_name: str
    customer_email: str
    gateway_payment_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    payment_gateway: str
    created_at: str


class AdminRefundListItem(BaseModel):
    id: int
    booking_id: int
    booking_reference: str
    customer_name: str
    gateway_refund_id: Optional[str] = None
    amount: float
    status: str
    reason: Optional[str] = None
    created_at: str


class AdminRefundActionRequest(BaseModel):
    amount: Optional[Decimal] = None
    reason: str = Field(..., min_length=3, description="Audit reason for triggering refund")


class CreateCouponRequest(BaseModel):
    code: str
    description: str
    discount_type: str = "PERCENTAGE"  # PERCENTAGE, FLAT
    discount_value: float
    min_order_value: float = 0.0
    max_discount: float = 500.0
    usage_limit: int = 1000
    valid_until: Optional[datetime] = None


class BroadcastNotificationRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5)
    type: str = "PLATFORM_BROADCAST"
    target_role: str = Field("ALL", description="ALL, CUSTOMER, PARTNER")


class AdminAuditLogItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Dict[str, Any] = {}
    created_at: str
