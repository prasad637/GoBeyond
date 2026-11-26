import uuid
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import update, or_
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import get_db
from app.core.locks import lock_service
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.dining import DiningReservation
from app.models.payment import Coupon, Payment, Refund
from app.models.user import User
from app.models.partner import Partner
from app.models.audit import Notification, AuditLog
from app.schemas.booking import (
    CreateBookingRequest,
    BookingResponse,
    CancelBookingRequest,
    ApplyCouponRequest,
    ApplyCouponResponse,
    ExpireStaleResponse
)
from app.api.deps import get_current_user, require_roles
from app.core.rate_limit import booking_rate_limiter
from app.api.v1.endpoints.partners import get_partner_booking_ids
from app.services.notifications.service import NotificationService
from app.services.booking import (
    BookingEngineService,
    generate_booking_reference,
    generate_secure_qr_pass_token,
    validate_state_transition,
    quantize_amount
)

router = APIRouter()


def _to_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _release_acquired_locks(keys: List[str], token: str) -> None:
    for k in keys:
        try:
            lock_service.release_lock(k, token)
        except Exception:
            pass


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(booking_rate_limiter)])
@router.post("/initiate", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(booking_rate_limiter)])
def create_or_initiate_booking(
    req: CreateBookingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Universal booking initiator for all 5 verticals:
    - Calculates merchandise prices strictly from database catalog models.
    - Validates inventory limits and acquires pessimistic Redis locks.
    - Applies coupon discounts and 18% GST with exact Decimal precision.
    - Enforces idempotency if idempotency_key is provided.
    - Generates authenticated QR gate pass without customer PII.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="Cannot create empty booking without items.")

    # Idempotency verification
    if req.idempotency_key:
        existing_booking = db.query(Booking).filter(
            Booking.user_id == current_user.id,
            Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING", "CONFIRMED"])
        ).join(Payment, Payment.booking_id == Booking.id, isouter=True).filter(
            Payment.idempotency_key == req.idempotency_key
        ).first()

        if existing_booking:
            return existing_booking

    items_dicts = [i.model_dump() for i in req.items]

    # Validate inventory and calculate prices from database
    total_merchandise, validated_items, acquired_keys, effective_token = (
        BookingEngineService.calculate_merchandise_and_validate_inventory(
            db=db,
            booking_type=req.booking_type,
            items=items_dicts,
            current_user=current_user,
            lock_token=req.lock_token
        )
    )

    # Apply Coupon if requested (with strict window and atomic usage_limit validation)
    discount_amount = Decimal("0.00")
    applied_coupon_id = None
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    if req.coupon_code:
        clean_code = req.coupon_code.strip().upper()
        coupon = db.query(Coupon).filter(
            Coupon.code == clean_code,
            Coupon.is_active == True
        ).first()

        if not coupon:
            db.rollback()
            _release_acquired_locks(acquired_keys, effective_token)
            BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
            raise HTTPException(status_code=400, detail="Invalid or inactive promo code.")

        valid_from = _to_utc(coupon.valid_from)
        valid_until = _to_utc(coupon.valid_until)
        if valid_from and now_utc < valid_from:
            db.rollback()
            _release_acquired_locks(acquired_keys, effective_token)
            BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
            raise HTTPException(status_code=400, detail="This promo code is not active yet.")
        if valid_until and now_utc > valid_until:
            db.rollback()
            _release_acquired_locks(acquired_keys, effective_token)
            BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
            raise HTTPException(status_code=400, detail="This promo code has expired.")
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            db.rollback()
            _release_acquired_locks(acquired_keys, effective_token)
            BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
            raise HTTPException(status_code=400, detail="This promo code has reached its redemption limit.")

        min_order_val = quantize_amount(coupon.min_order_value)
        if total_merchandise < min_order_val:
            db.rollback()
            _release_acquired_locks(acquired_keys, effective_token)
            BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
            raise HTTPException(
                status_code=400,
                detail=f"Promo code requires minimum order value of ₹{min_order_val:.0f}."
            )

        # Atomic conditional usage increment to prevent concurrent usage_limit bypass
        upd_stmt = (
            update(Coupon)
            .where(
                Coupon.id == coupon.id,
                Coupon.is_active == True,
                or_(Coupon.usage_limit.is_(None), Coupon.used_count < Coupon.usage_limit)
            )
            .values(used_count=Coupon.used_count + 1)
        )
        upd_res = db.execute(upd_stmt)
        if upd_res.rowcount == 0:
            db.rollback()
            _release_acquired_locks(acquired_keys, effective_token)
            BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
            raise HTTPException(status_code=400, detail="This promo code has reached its redemption limit.")

        disc_val = quantize_amount(coupon.discount_value)
        max_disc = quantize_amount(coupon.max_discount)
        if coupon.discount_type == "PERCENTAGE":
            calc_disc = (total_merchandise * disc_val) / Decimal("100.00")
            discount_amount = min(max_disc, calc_disc)
        else:
            discount_amount = min(max_disc, disc_val)

        discount_amount = quantize_amount(discount_amount)
        applied_coupon_id = coupon.id

    # 18% GST Tax calculation on taxable amount
    taxable_amount = max(Decimal("0.00"), total_merchandise - discount_amount)
    tax_amount = quantize_amount(taxable_amount * Decimal("0.18"))
    final_payable = quantize_amount(taxable_amount + tax_amount)

    # Reference and Expiration
    booking_ref = generate_booking_reference(req.booking_type)
    qr_token = generate_secure_qr_pass_token(booking_ref)
    expires_at = now_utc + datetime.timedelta(seconds=settings.LOCK_EXPIRY_SECONDS)

    initial_status = "CONFIRMED" if final_payable == Decimal("0.00") else "PAYMENT_PENDING"

    booking = Booking(
        booking_reference=booking_ref,
        user_id=current_user.id,
        booking_type=req.booking_type.upper(),
        total_amount=total_merchandise,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        final_payable=final_payable,
        coupon_id=applied_coupon_id,
        status=initial_status,
        qr_code_token=qr_token,
        expires_at=expires_at
    )
    db.add(booking)
    db.flush()

    for item_data in validated_items:
        bi = BookingItem(
            booking_id=booking.id,
            item_type=item_data["item_type"],
            item_id=item_data["item_id"],
            name=item_data["name"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            subtotal=item_data["subtotal"],
            details=item_data["details"]
        )
        db.add(bi)

        if booking.booking_type == "DINING" and item_data["item_type"] == "TABLE":
            d_det = item_data["details"]
            db.add(DiningReservation(
                restaurant_id=int(d_det["restaurant_id"]),
                table_id=int(item_data["item_id"]),
                user_id=current_user.id,
                booking_id=booking.id,
                reservation_date=datetime.date.fromisoformat(d_det["reservation_date"]),
                reservation_time=datetime.time.fromisoformat(d_det["reservation_time"]),
                start_datetime=datetime.datetime.fromisoformat(d_det["start_datetime"]),
                end_datetime=datetime.datetime.fromisoformat(d_det["end_datetime"]),
                duration_minutes=90,
                buffer_minutes=15,
                guest_count=int(d_det.get("guest_count", item_data["quantity"])),
                status="CONFIRMED" if initial_status == "CONFIRMED" else "PENDING",
            ))

    # Audit Log
    db.add(AuditLog(
        user_id=current_user.id,
        action="BOOKING_INITIATED",
        resource_type="BOOKING",
        resource_id=booking_ref,
        details={
            "booking_type": req.booking_type,
            "merchandise_total": float(total_merchandise),
            "final_payable": float(final_payable)
        }
    ))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _release_acquired_locks(acquired_keys, effective_token)
        BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected inventory was just reserved by another customer. Please choose another option."
        )
    except Exception:
        db.rollback()
        _release_acquired_locks(acquired_keys, effective_token)
        BookingEngineService.release_user_lock_token(db, current_user.id, req.lock_token, commit=True)
        raise

    # For DINING, DiningReservation is now durable in PostgreSQL (backed by GiST exclusion constraint);
    # release the transient Redis mutex so cancellations immediately allow re-booking.
    if booking.booking_type == "DINING":
        _release_acquired_locks(acquired_keys, effective_token)

    db.refresh(booking)
    return booking


@router.get("/my-bookings", response_model=List[BookingResponse])
def get_user_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns authenticated user's personal bookings.
    Customer tenant boundary strictly enforced.
    """
    query = db.query(Booking).filter(Booking.user_id == current_user.id)
    if status_filter:
        query = query.filter(Booking.status == status_filter.upper())

    bookings = query.order_by(Booking.created_at.desc()).all()
    return bookings


@router.get("/{identifier}", response_model=BookingResponse)
def get_booking_detail(
    identifier: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves booking receipt & pass details.
    Enforces tenant boundaries: Customer can view their own; Partner can view their establishment's; Admin can view all.
    """
    if identifier.isdigit():
        booking = db.query(Booking).filter(Booking.id == int(identifier)).first()
    else:
        booking = db.query(Booking).filter(Booking.booking_reference == identifier).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    user_roles = [r.name.lower() for r in current_user.roles]
    is_admin = "super_admin" in user_roles or "admin" in user_roles

    if not is_admin and booking.user_id != current_user.id:
        partner = db.query(Partner).filter(Partner.user_id == current_user.id).first()
        if partner:
            partner_b_ids = get_partner_booking_ids(db, partner.id)
            if booking.id not in partner_b_ids:
                raise HTTPException(status_code=403, detail="Unauthorized access to this booking.")
        else:
            raise HTTPException(status_code=403, detail="Unauthorized access to this booking.")

    return booking


@router.post("/{booking_id}/cancel", dependencies=[Depends(booking_rate_limiter)])
def cancel_booking(
    booking_id: int,
    req: CancelBookingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Customer cancellation endpoint with cancellation policy validation and automatic refund triggering.
    """
    actor_user_id = current_user.id
    actor_roles = [r.name.lower() for r in current_user.roles]
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    is_admin = "super_admin" in actor_roles or "admin" in actor_roles
    if booking.user_id != actor_user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Unauthorized access to cancel this booking.")

    if booking.status in ["CANCELLED", "REFUNDED"]:
        raise HTTPException(status_code=400, detail=f"Booking is already {booking.status}.")

    # Release inventory back to the catalog
    BookingEngineService.release_inventory_for_booking(db, booking)

    was_confirmed = booking.status == "CONFIRMED"
    next_status = "REFUND_PENDING" if (was_confirmed and booking.final_payable > Decimal("0.00")) else "CANCELLED"
    validate_state_transition(booking.status, next_status)

    booking.status = next_status
    booking.cancellation_reason = req.reason

    # If captured payment exists, initiate refund record
    if was_confirmed and booking.final_payable > Decimal("0.00"):
        payment = db.query(Payment).filter(
            Payment.booking_id == booking.id,
            Payment.status == "CAPTURED"
        ).first()

        if payment:
            refund_id = f"rfn_{uuid.uuid4().hex[:14]}"
            refund = Refund(
                payment_id=payment.id,
                booking_id=booking.id,
                gateway_refund_id=refund_id,
                amount=payment.amount,
                reason=f"Customer cancellation: {req.reason}",
                status="INITIATED"
            )
            db.add(refund)
            payment.status = "REFUND_PENDING"

    db.add(Notification(
        user_id=booking.user_id,
        title="Booking Cancelled",
        message=f"Booking {booking.booking_reference} has been cancelled. { 'Full refund initiated to original payment method.' if was_confirmed else '' }",
        type="PAYMENT_UPDATE"
    ))

    db.add(AuditLog(
        user_id=actor_user_id,
        action="BOOKING_CANCELLED",
        resource_type="BOOKING",
        resource_id=booking.booking_reference,
        details={"reason": req.reason, "status": booking.status}
    ))

    # Outbox notifications for cancellation
    try:
        with db.begin_nested():
            NotificationService.notify_booking_cancelled(db, booking, actor_user_id, reason=req.reason, commit=False)
    except Exception:
        pass

    db.commit()
    return {
        "success": True,
        "booking_reference": booking.booking_reference,
        "status": booking.status,
        "message": "Booking cancellation processed successfully."
    }


@router.post("/apply-coupon", response_model=ApplyCouponResponse)
def apply_coupon(req: ApplyCouponRequest, db: Session = Depends(get_db)):
    code_clean = req.code.strip().upper()
    coupon = db.query(Coupon).filter(
        Coupon.code == code_clean,
        Coupon.is_active == True
    ).first()

    order_amt = quantize_amount(req.order_amount)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    if not coupon:
        return ApplyCouponResponse(
            valid=False,
            code=code_clean,
            discount_amount=0.0,
            final_amount=float(order_amt),
            message="Invalid or inactive promo code."
        )

    valid_from = _to_utc(coupon.valid_from)
    valid_until = _to_utc(coupon.valid_until)
    if valid_from and now_utc < valid_from:
        return ApplyCouponResponse(
            valid=False,
            code=code_clean,
            discount_amount=0.0,
            final_amount=float(order_amt),
            message="This promo code is not active yet."
        )

    if valid_until and now_utc > valid_until:
        return ApplyCouponResponse(
            valid=False,
            code=code_clean,
            discount_amount=0.0,
            final_amount=float(order_amt),
            message="This promo code has expired."
        )

    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return ApplyCouponResponse(
            valid=False,
            code=code_clean,
            discount_amount=0.0,
            final_amount=float(order_amt),
            message="This promo code has reached its redemption limit."
        )

    min_order_val = quantize_amount(coupon.min_order_value)
    max_disc_val = quantize_amount(coupon.max_discount)
    disc_val = quantize_amount(coupon.discount_value)

    if order_amt < min_order_val:
        return ApplyCouponResponse(
            valid=False,
            code=code_clean,
            discount_amount=0.0,
            final_amount=float(order_amt),
            message=f"Code valid only on orders above ₹{min_order_val:.0f}."
        )

    if coupon.discount_type == "PERCENTAGE":
        discount = min(max_disc_val, quantize_amount((order_amt * disc_val) / Decimal("100.00")))
    else:
        discount = min(max_disc_val, disc_val)

    discount = quantize_amount(discount)
    final_amt = quantize_amount(max(Decimal("0.00"), order_amt - discount))

    return ApplyCouponResponse(
        valid=True,
        code=code_clean,
        discount_amount=float(discount),
        final_amount=float(final_amt),
        message=f"Coupon '{code_clean}' applied! You saved ₹{discount:.2f}."
    )


@router.post("/expire-stale", response_model=ExpireStaleResponse)
def expire_stale_bookings_trigger(
    current_user: User = Depends(require_roles(["super_admin"])),
    db: Session = Depends(get_db)
):
    """
    Admin/operator endpoint that frees stale locks and transitions expired holds.
    Requires super_admin authorization.
    """
    count = BookingEngineService.expire_stale_bookings(db)
    return ExpireStaleResponse(
        expired_count=count,
        message=f"Successfully processed and released {count} expired bookings."
    )
