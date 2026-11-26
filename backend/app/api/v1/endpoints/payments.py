import hmac
import hashlib
import uuid
import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
import razorpay

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.payment import Payment, Refund
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.event import EventTicketType
from app.models.sports import ActivitySlot
from app.models.dining import DiningReservation
from app.models.user import User
from app.models.audit import Notification, AuditLog
from app.schemas.payment import (
    CreatePaymentOrderRequest,
    CreatePaymentOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    PaymentFailureReportRequest,
    PaymentFailureReportResponse,
    RefundRequest,
    RefundResponse,
    ReconciliationReportResponse
)
from app.api.deps import get_current_user, require_roles
from app.services.booking import (
    BookingEngineService,
    quantize_amount,
    generate_secure_qr_pass_token,
    validate_state_transition,
)
from app.services.revenue import quantize_currency
from app.services.reconciliation import ReconciliationEngine
from app.services.notifications.service import NotificationService
from app.core.rate_limit import payment_rate_limiter

router = APIRouter()

# ==============================================================================
# PAYMENT STATE MACHINE
# ==============================================================================

VALID_PAYMENT_STATUSES = {
    "INITIATED",
    "PENDING",
    "CAPTURED",
    "FAILED",
    "EXPIRED",
    "CANCELLED",
    "REFUND_PENDING",
    "REFUNDED",
    "PARTIALLY_REFUNDED"
}

ALLOWED_PAYMENT_TRANSITIONS: Dict[str, List[str]] = {
    "INITIATED": ["PENDING", "CAPTURED", "FAILED", "EXPIRED", "CANCELLED"],
    "PENDING": ["CAPTURED", "FAILED", "EXPIRED", "CANCELLED"],
    "CAPTURED": ["REFUND_PENDING", "REFUNDED", "PARTIALLY_REFUNDED"],
    "REFUND_PENDING": ["REFUNDED", "PARTIALLY_REFUNDED", "FAILED"],
    "PARTIALLY_REFUNDED": ["REFUNDED", "PARTIALLY_REFUNDED"],
    "REFUNDED": [],       # Terminal
    "FAILED": [],         # Terminal
    "EXPIRED": ["REFUND_PENDING"],  # When late payment arrives after hold expired
    "CANCELLED": ["REFUND_PENDING"]
}


def validate_payment_state_transition(current_status: str, next_status: str) -> None:
    """Enforces strict state machine transitions for financial transactions."""
    if next_status not in VALID_PAYMENT_STATUSES:
        raise ValueError(f"Invalid payment status '{next_status}'.")
    if current_status == next_status:
        return  # Idempotent no-op
    allowed = ALLOWED_PAYMENT_TRANSITIONS.get(current_status, [])
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Illegal payment state transition from '{current_status}' to '{next_status}'."
        )


def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


# ==============================================================================
# 1. ORDER CREATION
# ==============================================================================

@router.post("/create-order", response_model=CreatePaymentOrderResponse, dependencies=[Depends(payment_rate_limiter)])
def create_payment_order(
    req: CreatePaymentOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a payment order strictly computed from the server-side booking hold price.
    Never trusts client-supplied prices.
    """
    booking = db.query(Booking).filter(Booking.id == req.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking record not found.")

    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this booking.")

    if booking.status == "CONFIRMED":
        raise HTTPException(status_code=400, detail="This booking has already been paid and confirmed.")

    if booking.status in ["CANCELLED", "EXPIRED", "REFUNDED", "FAILED", "REFUND_PENDING"]:
        raise HTTPException(status_code=400, detail=f"Cannot initiate payment for {booking.status} booking.")

    # Calculate exact amount on server side
    final_dec = quantize_currency(booking.final_payable)
    amount_in_paise = int(final_dec * 100)

    order_id = f"order_{uuid.uuid4().hex[:14]}"
    if not settings.RAZORPAY_SANDBOX_MODE:
        try:
            client = get_razorpay_client()
            razorpay_order = client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": booking.booking_reference,
                "notes": {"booking_id": booking.id, "user_id": current_user.id}
            })
            order_id = razorpay_order["id"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Razorpay order creation failed: {str(e)}"
            )

    # Create or update payment record
    existing_payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    if not existing_payment:
        payment = Payment(
            booking_id=booking.id,
            user_id=current_user.id,
            payment_gateway="RAZORPAY",
            gateway_order_id=order_id,
            amount=final_dec,
            currency="INR",
            status="INITIATED",
            idempotency_key=req.idempotency_key or str(uuid.uuid4())
        )
        db.add(payment)
    else:
        validate_payment_state_transition(existing_payment.status, "INITIATED")
        existing_payment.gateway_order_id = order_id
        existing_payment.status = "INITIATED"
        existing_payment.amount = final_dec

    booking.status = "PAYMENT_PENDING"
    db.commit()

    return CreatePaymentOrderResponse(
        order_id=order_id,
        booking_reference=booking.booking_reference,
        amount=float(final_dec),
        currency="INR",
        key_id=settings.RAZORPAY_KEY_ID,
        booking_id=booking.id
    )


# ==============================================================================
# 2. SIGNATURE VERIFICATION & CONFIRMATION
# ==============================================================================

@router.post("/verify", response_model=VerifyPaymentResponse, dependencies=[Depends(payment_rate_limiter)])
@router.post("/verify-signature", response_model=VerifyPaymentResponse, dependencies=[Depends(payment_rate_limiter)])
def verify_payment_signature(
    req: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifies payment signature from Razorpay.
    Includes strict defense against late payment callbacks on expired holds.
    If payment arrives after the inventory hold has expired or inventory is reassigned,
    booking transitions to REFUND_PENDING and automated refund reconciliation is recorded.
    """
    actor_user_id = current_user.id
    actor_roles = [r.name.lower() for r in current_user.roles]
    is_admin = "super_admin" in actor_roles or "admin" in actor_roles

    booking = db.query(Booking).filter(Booking.id == req.booking_id).with_for_update().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.user_id != actor_user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to verify payment for this booking."
        )

    owner_user_id = booking.user_id or actor_user_id

    # Idempotency Check: Already confirmed?
    if booking.status == "CONFIRMED":
        existing_payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
        qr_tok = booking.qr_code_token or generate_secure_qr_pass_token(booking.booking_reference)
        b_ref = booking.booking_reference
        gw_pay_id = existing_payment.gateway_payment_id if existing_payment and existing_payment.gateway_payment_id else "pay_already_confirmed"
        db.rollback()
        return VerifyPaymentResponse(
            success=True,
            status="CONFIRMED",
            booking_reference=b_ref,
            payment_id=gw_pay_id,
            qr_code_token=qr_tok,
            message="Payment already verified and booking confirmed."
        )

    # Order consistency check: prevent order-ID substitution when a Payment order exists
    existing_payment_order = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    if (
        existing_payment_order
        and existing_payment_order.gateway_order_id
        and existing_payment_order.gateway_order_id != req.razorpay_order_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment order ID does not match the initiated order for this booking."
        )

    # Signature verification
    signature_valid = False
    if settings.RAZORPAY_SANDBOX_MODE and (
        req.razorpay_signature.startswith("mock_") or 
        req.razorpay_signature.startswith("sandbox_")
    ):
        signature_valid = True
    else:
        msg = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode("utf-8")
        generated_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            msg,
            hashlib.sha256
        ).hexdigest()
        signature_valid = hmac.compare_digest(generated_signature, req.razorpay_signature)

    if not signature_valid:
        booking.status = "FAILED"
        payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
        if payment:
            payment.status = "FAILED"
            payment.error_message = "Signature verification failed."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed. Invalid HMAC signature."
        )

    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Check whether hold expired or booking was marked expired
    is_expired = False
    if booking.status == "EXPIRED":
        is_expired = True
    elif booking.expires_at:
        exp = booking.expires_at.replace(tzinfo=datetime.timezone.utc) if booking.expires_at.tzinfo is None else booking.expires_at
        if now_utc > exp:
            is_expired = True

    # Check for inventory conflicts
    inventory_conflict = False
    if is_expired:
        for item in booking.items:
            if booking.booking_type == "MOVIE" and item.item_type == "SEAT":
                conflict_lock = db.query(SeatLock).filter(
                    SeatLock.resource_type == "MOVIE_SHOW",
                    SeatLock.identifier == f"seat_{item.item_id}",
                    SeatLock.is_released == False,
                    SeatLock.user_id != booking.user_id,
                    SeatLock.expires_at > now_utc
                ).first()
                if conflict_lock:
                    inventory_conflict = True
                    break
                conflict_item = db.query(BookingItem).join(Booking).filter(
                    Booking.id != booking.id,
                    Booking.status == "CONFIRMED",
                    BookingItem.item_type == "SEAT",
                    BookingItem.item_id == item.item_id
                ).first()
                if conflict_item:
                    inventory_conflict = True
                    break

            elif booking.booking_type == "EVENT" and item.item_type == "TICKET":
                ticket_type = db.query(EventTicketType).filter(EventTicketType.id == item.item_id).first()
                if not ticket_type or ticket_type.available_quantity < 0:
                    inventory_conflict = True
                    break

            elif booking.booking_type in ["SPORTS", "ACTIVITY"] and item.item_type == "SLOT":
                slot = db.query(ActivitySlot).filter(ActivitySlot.id == item.item_id).first()
                if not slot or slot.booked_count > slot.capacity:
                    inventory_conflict = True
                    break

    # LATE PAYMENT HANDLING:
    if is_expired and (inventory_conflict or booking.status == "EXPIRED"):
        booking.status = "REFUND_PENDING"
        payment = db.query(Payment).filter(Payment.booking_id == booking.id).with_for_update().first()
        if not payment:
            payment = Payment(
                booking_id=booking.id,
                user_id=owner_user_id,
                payment_gateway="RAZORPAY",
                amount=quantize_currency(booking.final_payable),
                currency="INR"
            )
            db.add(payment)
            db.flush()

        payment.gateway_order_id = req.razorpay_order_id
        payment.gateway_payment_id = req.razorpay_payment_id
        payment.gateway_signature = req.razorpay_signature
        payment.status = "REFUND_PENDING"
        payment.raw_payload = {
            "order_id": req.razorpay_order_id,
            "payment_id": req.razorpay_payment_id,
            "verified_at": now_utc.isoformat(),
            "reason": "Payment arrived after inventory hold expired"
        }
        db.flush()

        existing_refund = db.query(Refund).filter(Refund.payment_id == payment.id).first()
        if not existing_refund:
            rfn = Refund(
                payment_id=payment.id,
                booking_id=booking.id,
                gateway_refund_id=f"rfn_late_{uuid.uuid4().hex[:10]}",
                amount=quantize_currency(booking.final_payable),
                reason="Late payment after hold expiry; inventory reassigned",
                status="INITIATED"
            )
            db.add(rfn)

        db.add(Notification(
            user_id=owner_user_id,
            title="Booking Hold Expired - Refund Initiated ⚠️",
            message=f"Your payment for booking {booking.booking_reference} arrived after the inventory hold expired. A full refund has been initiated.",
            type="REFUND_INITIATED",
            data={"booking_id": booking.id, "booking_reference": booking.booking_reference}
        ))

        db.add(AuditLog(
            user_id=actor_user_id,
            action="PAYMENT_LATE_HOLD_REFUND",
            resource_type="PAYMENT",
            resource_id=req.razorpay_payment_id,
            details={"booking_ref": booking.booking_reference, "amount": float(booking.final_payable)}
        ))

        db.commit()
        return VerifyPaymentResponse(
            success=False,
            status="REFUND_PENDING",
            booking_reference=booking.booking_reference,
            payment_id=req.razorpay_payment_id,
            qr_code_token="",
            message="Hold expired and inventory was re-assigned. Automatic refund initiated."
        )

    # Valid Payment Capture:
    payment = db.query(Payment).filter(Payment.booking_id == booking.id).with_for_update().first()
    if not payment:
        payment = Payment(
            booking_id=booking.id,
            user_id=owner_user_id,
            payment_gateway="RAZORPAY",
            amount=quantize_currency(booking.final_payable),
            currency="INR",
            status="INITIATED"
        )
        db.add(payment)

    validate_payment_state_transition(payment.status, "CAPTURED")
    payment.gateway_order_id = req.razorpay_order_id
    payment.gateway_payment_id = req.razorpay_payment_id
    payment.gateway_signature = req.razorpay_signature
    payment.status = "CAPTURED"
    payment.raw_payload = {
        "order_id": req.razorpay_order_id,
        "payment_id": req.razorpay_payment_id,
        "verified_at": now_utc.isoformat()
    }
    db.flush()

    # Finalize booking
    booking.status = "CONFIRMED"
    if not booking.qr_code_token:
        booking.qr_code_token = generate_secure_qr_pass_token(booking.booking_reference)

    if booking.booking_type == "DINING":
        db.query(DiningReservation).filter(
            DiningReservation.booking_id == booking.id,
            DiningReservation.status == "PENDING"
        ).update({"status": "CONFIRMED"})

    # Release temporary locks
    db.query(SeatLock).filter(
        SeatLock.user_id == owner_user_id,
        SeatLock.is_released == False
    ).update({"is_released": True})

    # Confirmation notification
    db.add(Notification(
        user_id=owner_user_id,
        title="Booking Confirmed! 🎉",
        message=f"Your booking {booking.booking_reference} for ₹{float(booking.final_payable):.2f} is confirmed!",
        type="BOOKING_CONFIRMATION",
        data={"booking_id": booking.id, "booking_reference": booking.booking_reference}
    ))

    # Trigger durable outbox notifications for customer and partner atomically via savepoint
    try:
        with db.begin_nested():
            NotificationService.notify_booking_confirmed(db, booking, owner_user_id, commit=False)
            NotificationService.notify_payment_success(db, payment, booking, owner_user_id, commit=False)
    except Exception:
        pass

    # Audit log
    db.add(AuditLog(
        user_id=actor_user_id,
        action="PAYMENT_CAPTURED",
        resource_type="PAYMENT",
        resource_id=req.razorpay_payment_id,
        details={"booking_ref": booking.booking_reference, "amount": float(booking.final_payable)}
    ))

    db.commit()

    return VerifyPaymentResponse(
        success=True,
        status="CONFIRMED",
        booking_reference=booking.booking_reference,
        payment_id=req.razorpay_payment_id,
        qr_code_token=booking.qr_code_token,
        message="Payment verified successfully! Your booking is confirmed."
    )


@router.post("/report-failure", response_model=PaymentFailureReportResponse, dependencies=[Depends(payment_rate_limiter)])
def report_payment_failure(
    req: PaymentFailureReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Records a client-reported Razorpay payment failure for an unpaid booking hold
    and immediately releases reserved inventory (seats, event tickets, slots, dining tables).
    Never mutates CONFIRMED, REFUND_PENDING, or REFUNDED bookings.
    """
    actor_roles = [r.name.lower() for r in current_user.roles]
    is_admin = "super_admin" in actor_roles or "admin" in actor_roles

    booking = db.query(Booking).filter(Booking.id == req.booking_id).with_for_update().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to update payment status for this booking."
        )

    if booking.status in ("CONFIRMED", "REFUND_PENDING", "REFUNDED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark booking as FAILED once it is '{booking.status}'."
        )

    payment = db.query(Payment).filter(Payment.booking_id == booking.id).with_for_update().first()

    if booking.status in ("FAILED", "CANCELLED", "EXPIRED"):
        return PaymentFailureReportResponse(
            success=True,
            booking_reference=booking.booking_reference,
            booking_status=booking.status,
            payment_status=payment.status if payment else "FAILED",
            inventory_released=False,
            message=f"Booking is already in '{booking.status}' state."
        )

    reason_text = (
        (req.error_description or "").strip()
        or (req.error_reason or "").strip()
        or "Payment failed during Razorpay checkout."
    )[:500]

    # Release reserved inventory immediately back to pool
    BookingEngineService.release_inventory_for_booking(db, booking)
    validate_state_transition(booking.status, "FAILED")
    booking.status = "FAILED"
    booking.cancellation_reason = f"Payment failed: {reason_text}"[:250]

    payment_status = "FAILED"
    if payment:
        if payment.status not in ("CAPTURED", "REFUND_PENDING", "REFUNDED", "PARTIALLY_REFUNDED"):
            validate_payment_state_transition(payment.status, "FAILED")
            payment.status = "FAILED"
            payment.error_message = reason_text
            if req.razorpay_payment_id and not payment.gateway_payment_id:
                payment.gateway_payment_id = req.razorpay_payment_id
        payment_status = payment.status
    else:
        owner_id = booking.user_id or current_user.id
        payment = Payment(
            booking_id=booking.id,
            user_id=owner_id,
            payment_gateway="RAZORPAY",
            gateway_order_id=req.razorpay_order_id,
            gateway_payment_id=req.razorpay_payment_id,
            amount=quantize_currency(booking.final_payable),
            currency="INR",
            status="FAILED",
            error_message=reason_text,
        )
        db.add(payment)
        db.flush()

    db.add(AuditLog(
        user_id=current_user.id,
        action="PAYMENT_FAILED_REPORTED",
        resource_type="PAYMENT",
        resource_id=req.razorpay_order_id or req.razorpay_payment_id or booking.booking_reference,
        details={
            "booking_ref": booking.booking_reference,
            "error_code": req.error_code,
            "reason": reason_text,
        }
    ))

    try:
        owner_id = booking.user_id or current_user.id
        with db.begin_nested():
            NotificationService.notify_payment_failed(
                db, payment, booking, owner_id, reason=reason_text, commit=False
            )
    except Exception:
        pass

    db.commit()

    return PaymentFailureReportResponse(
        success=True,
        booking_reference=booking.booking_reference,
        booking_status=booking.status,
        payment_status=payment_status,
        inventory_released=True,
        message="Payment failure recorded and held inventory released."
    )


# ==============================================================================
# 3. WEBHOOK SECURITY & IDEMPOTENT PROCESSING
# ==============================================================================

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handles incoming Razorpay asynchronous webhooks (payment.captured, payment.failed, refund.processed).
    Includes constant-time HMAC signature verification, Redis deduplication, and late-payment refund protection.
    Never processes an unverified webhook.
    """
    body_bytes = await request.body()

    # Webhook signature verification
    if not x_razorpay_signature:
        if not settings.RAZORPAY_SANDBOX_MODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required X-Razorpay-Signature header."
            )
        # Sandbox mode allows test harness without header
        signature_valid = True
    else:
        expected_sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        # In sandbox mode, allow mock signatures for test harnesses
        if settings.RAZORPAY_SANDBOX_MODE and (
            x_razorpay_signature.startswith("mock_") or 
            x_razorpay_signature.startswith("sandbox_")
        ):
            signature_valid = True
        else:
            signature_valid = hmac.compare_digest(expected_sig, x_razorpay_signature)

    if not signature_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature."
        )

    payload = await request.json()
    event_id = (
        payload.get("event_id") or 
        payload.get("id") or 
        payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id") or 
        str(uuid.uuid4())
    )
    event_type = payload.get("event")

    # Redis Deduplication
    redis_client = None
    try:
        redis_client = get_redis()
        dedup_key = f"gobeyond:webhook_dedup:{event_id}"
        if redis_client.get(dedup_key):
            return {"status": "already_processed", "event_id": event_id}
        redis_client.setex(dedup_key, 604800, "1")  # 7-day TTL
    except Exception:
        pass

    # Record webhook received in AuditLog
    db.add(AuditLog(
        action="WEBHOOK_RECEIVED",
        resource_type="WEBHOOK",
        resource_id=event_id,
        details={"event_type": event_type}
    ))

    # Event: payment.captured
    if event_type == "payment.captured":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        gateway_payment_id = payment_entity.get("id")

        if order_id:
            payment_meta = db.query(Payment.id, Payment.booking_id).filter(
                Payment.gateway_order_id == order_id
            ).first()
            if payment_meta and payment_meta.booking_id:
                booking = db.query(Booking).filter(
                    Booking.id == payment_meta.booking_id
                ).with_for_update().first()
                payment = db.query(Payment).filter(
                    Payment.id == payment_meta.id
                ).with_for_update().first()

                if payment and booking:
                    if payment.status == "CAPTURED" and booking.status == "CONFIRMED":
                        db.rollback()
                        return {"status": "already_processed", "event_id": event_id}

                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    is_expired = False
                    if booking.status == "EXPIRED":
                        is_expired = True
                    elif booking.expires_at:
                        exp = booking.expires_at.replace(tzinfo=datetime.timezone.utc) if booking.expires_at.tzinfo is None else booking.expires_at
                        if now_utc > exp:
                            is_expired = True

                    inventory_conflict = False
                    if is_expired:
                        for item in booking.items:
                            if booking.booking_type == "MOVIE" and item.item_type == "SEAT":
                                conflict_lock = db.query(SeatLock).filter(
                                    SeatLock.resource_type == "MOVIE_SHOW",
                                    SeatLock.identifier == f"seat_{item.item_id}",
                                    SeatLock.is_released == False,
                                    SeatLock.user_id != booking.user_id,
                                    SeatLock.expires_at > now_utc
                                ).first()
                                if conflict_lock:
                                    inventory_conflict = True
                                    break
                                conflict_item = db.query(BookingItem).join(Booking).filter(
                                    Booking.id != booking.id,
                                    Booking.status == "CONFIRMED",
                                    BookingItem.item_type == "SEAT",
                                    BookingItem.item_id == item.item_id
                                ).first()
                                if conflict_item:
                                    inventory_conflict = True
                                    break

                    if is_expired and (inventory_conflict or booking.status == "EXPIRED"):
                        payment.status = "REFUND_PENDING"
                        booking.status = "REFUND_PENDING"
                        payment.gateway_payment_id = gateway_payment_id
                        existing_rfn = db.query(Refund).filter(Refund.payment_id == payment.id).first()
                        if not existing_rfn:
                            rfn = Refund(
                                payment_id=payment.id,
                                booking_id=booking.id,
                                gateway_refund_id=f"rfn_webhook_{uuid.uuid4().hex[:10]}",
                                amount=quantize_currency(booking.final_payable),
                                reason="Webhook: payment on expired hold with conflict",
                                status="INITIATED"
                            )
                            db.add(rfn)
                    else:
                        payment.status = "CAPTURED"
                        booking.status = "CONFIRMED"
                        payment.gateway_payment_id = gateway_payment_id
                        if not booking.qr_code_token:
                            booking.qr_code_token = generate_secure_qr_pass_token(booking.booking_reference)
                        if booking.booking_type == "DINING":
                            db.query(DiningReservation).filter(
                                DiningReservation.booking_id == booking.id,
                                DiningReservation.status == "PENDING"
                            ).update({"status": "CONFIRMED"})
                        db.flush()
                        try:
                            if booking.user_id:
                                with db.begin_nested():
                                    NotificationService.notify_booking_confirmed(db, booking, booking.user_id, commit=False)
                                    NotificationService.notify_payment_success(db, payment, booking, booking.user_id, commit=False)
                        except Exception:
                            pass

                    db.commit()

    # Event: payment.failed
    elif event_type == "payment.failed":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        if order_id:
            payment_meta = db.query(Payment.id, Payment.booking_id).filter(
                Payment.gateway_order_id == order_id
            ).first()
            if payment_meta:
                booking = None
                if payment_meta.booking_id:
                    booking = db.query(Booking).filter(
                        Booking.id == payment_meta.booking_id
                    ).with_for_update().first()
                payment = db.query(Payment).filter(
                    Payment.id == payment_meta.id
                ).with_for_update().first()
                if payment:
                    payment.status = "FAILED"
                    payment.error_message = payment_entity.get("error_description", "Payment failed via gateway.")
                    if booking and booking.status == "PAYMENT_PENDING":
                        booking.status = "FAILED"
                        try:
                            if booking.user_id:
                                with db.begin_nested():
                                    NotificationService.notify_payment_failed(
                                        db, payment, booking, booking.user_id,
                                        reason=payment.error_message,
                                        commit=False
                                    )
                        except Exception:
                            pass
                    db.commit()

    # Event: refund.processed
    elif event_type == "refund.processed":
        refund_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
        refund_id = refund_entity.get("id")
        if refund_id:
            refund_meta = db.query(Refund.id, Refund.payment_id, Refund.booking_id).filter(
                Refund.gateway_refund_id == refund_id
            ).first()
            if refund_meta:
                booking = None
                if refund_meta.booking_id:
                    booking = db.query(Booking).filter(
                        Booking.id == refund_meta.booking_id
                    ).with_for_update().first()
                payment = None
                if refund_meta.payment_id:
                    payment = db.query(Payment).filter(
                        Payment.id == refund_meta.payment_id
                    ).with_for_update().first()
                refund = db.query(Refund).filter(Refund.id == refund_meta.id).with_for_update().first()
                if refund:
                    refund.status = "PROCESSED"
                    db.flush()

                    if payment:
                        settled_for_payment = sum(
                            (
                                quantize_currency(r.amount)
                                for r in db.query(Refund).filter(
                                    Refund.payment_id == payment.id,
                                    Refund.status.in_(["PROCESSED", "SUCCESS"])
                                ).all()
                            ),
                            Decimal("0.00")
                        )
                        payment_amt = quantize_currency(payment.amount)
                        if settled_for_payment >= payment_amt and payment_amt > Decimal("0.00"):
                            payment.status = "REFUNDED"
                        elif settled_for_payment > Decimal("0.00") and payment.status != "REFUNDED":
                            payment.status = "PARTIALLY_REFUNDED"

                    if booking:
                        all_booking_payments = db.query(Payment).filter(
                            Payment.booking_id == booking.id,
                            Payment.status.in_(["CAPTURED", "SUCCESS", "PARTIALLY_REFUNDED", "REFUNDED", "REFUND_PENDING"])
                        ).all()
                        total_paid = sum((quantize_currency(p.amount) for p in all_booking_payments), Decimal("0.00"))
                        total_settled_refunds = sum(
                            (
                                quantize_currency(r.amount)
                                for r in db.query(Refund).filter(
                                    Refund.booking_id == booking.id,
                                    Refund.status.in_(["PROCESSED", "SUCCESS"])
                                ).all()
                            ),
                            Decimal("0.00")
                        )
                        if (
                            total_paid > Decimal("0.00")
                            and total_settled_refunds >= total_paid
                            and booking.status in ("REFUND_PENDING", "CANCELLED", "CONFIRMED")
                        ):
                            booking.status = "REFUNDED"

                    db.commit()

    return {"status": "received", "event_id": event_id}


# ==============================================================================
# 4. REFUND ENGINE (FULL, PARTIAL & MULTIPLE PARTIAL REFUNDS)
# ==============================================================================

@router.post("/refund", response_model=RefundResponse, dependencies=[Depends(payment_rate_limiter)])
def process_refund(
    req: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Processes full or partial refunds with exact Decimal precision and strict
    over-refund prevention. Ensures total refunds never exceed captured payments.
    """
    actor_user_id = current_user.id
    actor_roles = [r.name for r in current_user.roles]
    booking = db.query(Booking).filter(Booking.id == req.booking_id).with_for_update().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    # Authorization: Owner or Admin
    is_admin = "super_admin" in actor_roles or "admin" in actor_roles
    if booking.user_id != actor_user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Unauthorized to refund this booking.")

    # Retrieve all captured payments
    captured_payments = db.query(Payment).filter(
        Payment.booking_id == booking.id,
        Payment.status.in_(["CAPTURED", "SUCCESS", "REFUND_PENDING", "PARTIALLY_REFUNDED"])
    ).all()

    if not captured_payments:
        raise HTTPException(
            status_code=400,
            detail="No captured payments found for this booking to refund."
        )

    total_captured = sum((quantize_currency(p.amount) for p in captured_payments), Decimal("0.00"))

    # Sum existing refunds
    existing_refunds = db.query(Refund).filter(
        Refund.booking_id == booking.id,
        Refund.status.in_(["PROCESSED", "SUCCESS", "INITIATED"])
    ).all()
    total_refunded = sum((quantize_currency(r.amount) for r in existing_refunds), Decimal("0.00"))

    remaining_refundable = total_captured - total_refunded
    if remaining_refundable <= Decimal("0.00"):
        raise HTTPException(
            status_code=400,
            detail="This booking has already been fully refunded."
        )

    # Determine refund amount
    refund_amount = quantize_currency(req.amount) if req.amount is not None else remaining_refundable
    if refund_amount <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Refund amount must be greater than zero.")

    # OVER-REFUND PREVENTION
    if refund_amount > remaining_refundable:
        raise HTTPException(
            status_code=400,
            detail=f"Requested refund amount ₹{refund_amount} exceeds remaining refundable balance ₹{remaining_refundable}."
        )

    target_payment = captured_payments[0]
    refund_ref = f"rfn_{uuid.uuid4().hex[:14]}"

    refund = Refund(
        payment_id=target_payment.id,
        booking_id=booking.id,
        gateway_refund_id=refund_ref,
        amount=refund_amount,
        reason=req.reason,
        status="PROCESSED"
    )
    db.add(refund)

    # Update statuses
    new_total_refunded = total_refunded + refund_amount
    new_remaining = remaining_refundable - refund_amount

    if new_total_refunded >= total_captured:
        target_payment.status = "REFUNDED"
        booking.status = "REFUNDED"
    else:
        target_payment.status = "PARTIALLY_REFUNDED"

    db.add(Notification(
        user_id=booking.user_id,
        title="Refund Processed 💰",
        message=f"Refund of ₹{float(refund_amount):.2f} for booking {booking.booking_reference} has been processed.",
        type="PAYMENT_UPDATE"
    ))

    db.flush()

    # Outbox notifications for refund
    try:
        with db.begin_nested():
            NotificationService.notify_refund_processed(db, refund, booking, booking.user_id, commit=False)
    except Exception:
        pass

    db.add(AuditLog(
        user_id=actor_user_id,
        action="REFUND_PROCESSED",
        resource_type="REFUND",
        resource_id=refund_ref,
        details={
            "booking_reference": booking.booking_reference,
            "refund_amount": float(refund_amount),
            "remaining_balance": float(new_remaining)
        }
    ))

    db.commit()

    return RefundResponse(
        success=True,
        refund_id=refund_ref,
        amount=float(refund_amount),
        status="PROCESSED",
        remaining_balance=float(new_remaining),
        message=f"Refund of ₹{float(refund_amount):.2f} has been processed successfully."
    )


# ==============================================================================
# 5. FINANCIAL RECONCILIATION AUDIT ENDPOINT
# ==============================================================================

@router.post("/reconciliation/run", response_model=ReconciliationReportResponse)
def trigger_reconciliation_audit(
    current_user: User = Depends(require_roles(["super_admin"])),
    db: Session = Depends(get_db)
):
    """
    Triggers an on-demand reconciliation audit comparing local records,
    captured amounts, refunds, and multi-partner commission balances.
    """
    return ReconciliationEngine.run_reconciliation_audit(db, actor_id=current_user.id)
