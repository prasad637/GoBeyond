from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class CreatePaymentOrderRequest(BaseModel):
    booking_id: int
    idempotency_key: Optional[str] = None


class CreatePaymentOrderResponse(BaseModel):
    order_id: str
    booking_reference: str
    amount: float
    currency: str
    key_id: str
    booking_id: int


class VerifyPaymentRequest(BaseModel):
    booking_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    idempotency_key: Optional[str] = None


class VerifyPaymentResponse(BaseModel):
    success: bool
    status: str
    booking_reference: str
    payment_id: str
    qr_code_token: Optional[str] = None
    message: str


class PaymentFailureReportRequest(BaseModel):
    booking_id: int
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    error_code: Optional[str] = Field(None, max_length=100)
    error_description: Optional[str] = Field(None, max_length=500)
    error_reason: Optional[str] = Field(None, max_length=255)


class PaymentFailureReportResponse(BaseModel):
    success: bool
    booking_reference: str
    booking_status: str
    payment_status: str
    inventory_released: bool
    message: str


class RefundRequest(BaseModel):
    booking_id: int
    amount: Optional[Decimal] = Field(None, ge=Decimal("0.01"), description="Optional partial refund amount in INR. If omitted, full remaining balance is refunded.")
    reason: str = Field(..., min_length=3, description="Audit reason for refund.")
    idempotency_key: Optional[str] = None


class RefundResponse(BaseModel):
    success: bool
    refund_id: str
    amount: float
    status: str
    remaining_balance: float = 0.0
    message: str


class PaymentTransactionResponse(BaseModel):
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


class RefundRecordResponse(BaseModel):
    id: int
    booking_id: int
    booking_reference: str
    gateway_refund_id: Optional[str] = None
    amount: float
    status: str
    reason: Optional[str] = None
    created_at: str


class ReconciliationDiscrepancyItem(BaseModel):
    code: str
    severity: str  # HIGH, MEDIUM, LOW
    booking_reference: Optional[str] = None
    payment_id: Optional[int] = None
    gateway_id: Optional[str] = None
    description: str
    suggested_action: str
    details: Dict[str, Any] = {}


class ReconciliationReportResponse(BaseModel):
    is_healthy: bool
    total_bookings_audited: int
    total_payments_audited: int
    total_refunds_audited: int
    total_captured_amount: float
    total_refunded_amount: float
    net_collected_amount: float
    platform_revenue: float
    partner_settlements: float
    discrepancies_count: int
    discrepancies: List[ReconciliationDiscrepancyItem] = []
    audited_at: str
