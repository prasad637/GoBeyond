from typing import List, Optional, Dict, Any
import datetime
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.database import get_db
from app.models.user import User, Role, UserProfile, RefreshToken
from app.models.partner import Partner, PartnerDocument
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund, Coupon
from app.models.movie import Cinema, Screen, Movie, MovieShow, Seat
from app.models.dining import Restaurant, DiningTable
from app.models.event import Event, EventTicketType
from app.models.sports import SportsVenue, Activity, ActivitySlot
from app.models.location import Location
from app.models.audit import AuditLog, Notification
from app.services.notifications.service import NotificationService
from app.schemas.admin import (
    AdminStatsResponse,
    PartnerStatusUpdateRequest,
    PartnerCommissionUpdateRequest,
    PartnerDocumentVerifyRequest,
    AdminPartnerDetailResponse,
    AdminUserResponse,
    UserStatusUpdateRequest,
    AdminBookingDetailResponse,
    AdminBookingItemDetail,
    AdminPaymentDetail,
    AdminRefundDetail,
    AdminPaymentListItem,
    AdminRefundListItem,
    AdminRefundActionRequest,
    CreateCouponRequest,
    BroadcastNotificationRequest,
    AdminAuditLogItem
)
from app.schemas.partner import PartnerResponse
from app.schemas.booking import BookingResponse
from app.api.deps import get_current_user, require_roles
from app.api.v1.endpoints.partners import get_partner_booking_ids
from app.services.revenue import calculate_revenue_metrics, quantize_currency
from app.services.booking import BookingEngineService, validate_state_transition
from app.core.rate_limit import admin_api_rate_limiter, admin_mutation_rate_limiter

router = APIRouter(dependencies=[Depends(require_roles(["super_admin"])), Depends(admin_api_rate_limiter)])


# ==============================================================================
# 1. OVERVIEW & ANALYTICS
# ==============================================================================

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_dashboard_stats(db: Session = Depends(get_db)):
    """
    Returns verified system-wide key performance indicators, live listing tallies,
    financial revenue attribution, and historical trends across all 5 verticals.
    """
    total_users = db.query(User).count()
    customer_role = db.query(Role).filter(Role.name == "customer").first()
    if customer_role:
        total_customers = db.query(User).filter(User.roles.contains(customer_role)).count()
    else:
        total_customers = max(0, total_users - 1)

    total_partners = db.query(Partner).count()
    approved_partners = db.query(Partner).filter(Partner.status == "APPROVED").count()
    pending_partners = db.query(Partner).filter(
        Partner.status.in_(["PENDING_VERIFICATION", "PENDING_APPROVAL"])
    ).count()
    suspended_partners = db.query(Partner).filter(Partner.status == "SUSPENDED").count()

    total_bookings = db.query(Booking).count()
    confirmed_bookings = db.query(Booking).filter(Booking.status == "CONFIRMED").count()

    # Breakdown by vertical
    vertical_counts = {
        "MOVIE": db.query(Booking).filter(Booking.booking_type == "MOVIE").count(),
        "DINING": db.query(Booking).filter(Booking.booking_type == "DINING").count(),
        "EVENT": db.query(Booking).filter(Booking.booking_type == "EVENT").count(),
        "SPORTS": db.query(Booking).filter(Booking.booking_type == "SPORTS").count(),
        "ACTIVITY": db.query(Booking).filter(Booking.booking_type == "ACTIVITY").count(),
    }

    # Revenue calculation using the core Decimal precision engine
    rev_metrics = calculate_revenue_metrics(db)

    total_movies = db.query(Movie).count()
    total_restaurants = db.query(Restaurant).count()
    total_events = db.query(Event).count()
    total_activities = db.query(Activity).count()

    # 7-day daily trends
    now = datetime.datetime.now(datetime.timezone.utc)
    daily_trends = []
    for i in range(6, -1, -1):
        target_day = (now - datetime.timedelta(days=i)).date()
        day_bookings = db.query(Booking).filter(
            func.date(Booking.created_at) == target_day,
            Booking.status == "CONFIRMED"
        ).all()
        b_count = len(day_bookings)
        gross_val = sum(float(b.final_payable) for b in day_bookings)
        daily_trends.append({
            "date": target_day.strftime("%b %d"),
            "bookings": b_count,
            "gross_revenue": round(gross_val, 2)
        })

    # 6-month monthly trends
    monthly_trends = []
    for m in range(5, -1, -1):
        # Approximate month offset
        month_target = (now - datetime.timedelta(days=m * 30)).date().replace(day=1)
        next_month = (month_target + datetime.timedelta(days=32)).replace(day=1)
        m_bookings = db.query(Booking).filter(
            Booking.created_at >= month_target,
            Booking.created_at < next_month,
            Booking.status == "CONFIRMED"
        ).all()
        monthly_trends.append({
            "month": month_target.strftime("%b %Y"),
            "bookings": len(m_bookings),
            "gross_revenue": round(sum(float(b.final_payable) for b in m_bookings), 2)
        })

    return AdminStatsResponse(
        total_users=total_users,
        total_customers=total_customers,
        total_partners=total_partners,
        approved_partners=approved_partners,
        pending_partner_verifications=pending_partners,
        suspended_partners=suspended_partners,
        total_bookings=total_bookings,
        confirmed_bookings=confirmed_bookings,
        vertical_bookings=vertical_counts,
        total_revenue=rev_metrics["total_revenue"],
        gross_confirmed_booking_value=rev_metrics["gross_confirmed_booking_value"],
        total_captured_payments=rev_metrics["total_captured_payments"],
        total_refunded_amount=rev_metrics["total_refunded_amount"],
        net_collected_amount=rev_metrics["net_collected_amount"],
        actual_platform_revenue=rev_metrics["actual_platform_revenue"],
        partner_settlements_payable=rev_metrics["partner_settlements_payable"],
        total_over_refunded_amount=rev_metrics["total_over_refunded_amount"],
        over_refunded_bookings_count=rev_metrics["over_refunded_bookings_count"],
        requires_financial_reconciliation=rev_metrics["requires_financial_reconciliation"],
        total_movies=total_movies,
        total_restaurants=total_restaurants,
        total_events=total_events,
        total_sports_activities=total_activities,
        daily_trends=daily_trends,
        monthly_trends=monthly_trends
    )


# ==============================================================================
# 2. PARTNER MANAGEMENT
# ==============================================================================

@router.get("/partners")
def list_partners(
    status: Optional[str] = Query(None),
    partner_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists partners with search, vertical filter, verification status filter, and pagination."""
    query = db.query(Partner)
    if status:
        query = query.filter(Partner.status == status.upper())
    if partner_type:
        query = query.filter(Partner.partner_type == partner_type.upper())
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Partner.business_name.ilike(search_fmt),
                Partner.contact_email.ilike(search_fmt),
                Partner.contact_phone.ilike(search_fmt)
            )
        )

    total = query.count()
    partners = query.order_by(Partner.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for p in partners:
        doc_count = db.query(PartnerDocument).filter(PartnerDocument.partner_id == p.id).count()
        results.append({
            "id": p.id,
            "user_id": p.user_id,
            "business_name": p.business_name,
            "partner_type": p.partner_type,
            "contact_email": p.contact_email,
            "contact_phone": p.contact_phone,
            "gstin": p.gstin,
            "pan_number": p.pan_number,
            "commission_rate": float(p.commission_rate),
            "status": p.status,
            "verified_at": p.verified_at.strftime("%Y-%m-%d %H:%M") if p.verified_at else None,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else None,
            "documents_count": doc_count
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "partners": results
    }


@router.get("/partners/{partner_id}", response_model=AdminPartnerDetailResponse)
def get_partner_details(partner_id: int, db: Session = Depends(get_db)):
    """Deep inspection of a partner profile, verified documents, and isolated financial ledger."""
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Document list
    docs = db.query(PartnerDocument).filter(PartnerDocument.partner_id == partner.id).all()
    doc_list = [{
        "id": d.id,
        "document_type": d.document_type,
        "document_url": d.document_url,
        "status": d.status,
        "uploaded_at": d.uploaded_at.strftime("%Y-%m-%d %H:%M") if d.uploaded_at else ""
    } for d in docs]

    # Listings count
    total_listings = (
        db.query(Restaurant).filter(Restaurant.partner_id == partner.id).count() +
        db.query(Cinema).filter(Cinema.partner_id == partner.id).count() +
        db.query(Event).filter(Event.partner_id == partner.id).count() +
        db.query(SportsVenue).filter(SportsVenue.partner_id == partner.id).count() +
        db.query(Activity).filter(Activity.partner_id == partner.id).count()
    )

    # Bookings & financial attribution
    partner_b_ids = get_partner_booking_ids(db, partner.id)
    financials = calculate_revenue_metrics(db, booking_ids=partner_b_ids)

    return AdminPartnerDetailResponse(
        id=partner.id,
        user_id=partner.user_id,
        business_name=partner.business_name,
        partner_type=partner.partner_type,
        contact_email=partner.contact_email,
        contact_phone=partner.contact_phone,
        gstin=partner.gstin,
        pan_number=partner.pan_number,
        commission_rate=float(partner.commission_rate),
        status=partner.status,
        verified_at=partner.verified_at.strftime("%Y-%m-%d %H:%M") if partner.verified_at else None,
        created_at=partner.created_at.strftime("%Y-%m-%d %H:%M") if partner.created_at else None,
        total_listings=total_listings,
        total_bookings=len(partner_b_ids),
        gross_booking_value=financials["gross_confirmed_booking_value"],
        platform_fee=financials["actual_platform_revenue"],
        partner_payout=financials["partner_settlements_payable"],
        documents=doc_list
    )


@router.put("/partners/{partner_id}/status", dependencies=[Depends(admin_mutation_rate_limiter)])
def update_partner_status(
    partner_id: int,
    req: PartnerStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approves, rejects, or suspends a partner application.
    Enforces immutable audit logging and triggers notifications.
    """
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    new_status = req.status.upper()
    if new_status not in ["APPROVED", "REJECTED", "SUSPENDED", "PENDING_APPROVAL"]:
        raise HTTPException(status_code=400, detail="Invalid partner status.")

    old_status = partner.status
    partner.status = new_status
    if new_status == "APPROVED":
        partner.verified_at = datetime.datetime.now(datetime.timezone.utc)
        partner.verified_by = current_user.id

    # Notification to partner
    db.add(Notification(
        user_id=partner.user_id,
        title=f"Partner Account {new_status.title()}! 🏢",
        message=f"Your partner account for '{partner.business_name}' status updated to {new_status} by Super Admin.",
        type="PARTNER_ALERT"
    ))

    # Immutable Audit Log
    db.add(AuditLog(
        user_id=current_user.id,
        action="PARTNER_STATUS_UPDATE",
        resource_type="PARTNER",
        resource_id=str(partner.id),
        details={
            "old_status": old_status,
            "new_status": new_status,
            "business_name": partner.business_name,
            "notes": req.notes
        }
    ))

    # Outbox notification for partner status change
    try:
        NotificationService.notify_partner_status_change(db, partner, new_status, reason=req.notes)
    except Exception:
        pass

    db.commit()
    return {"success": True, "partner_id": partner.id, "status": new_status}


@router.put("/partners/{partner_id}/commission", dependencies=[Depends(admin_mutation_rate_limiter)])
def update_partner_commission_rate(
    partner_id: int,
    req: PartnerCommissionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates a partner's contract commission take-rate with exact Numeric(5, 4) precision.
    Audited with before-and-after values.
    """
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    old_rate = partner.commission_rate
    partner.commission_rate = req.commission_rate

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="PARTNER_COMMISSION_UPDATE",
        resource_type="PARTNER",
        resource_id=str(partner.id),
        details={
            "old_commission_rate": float(old_rate),
            "new_commission_rate": float(req.commission_rate),
            "business_name": partner.business_name,
            "notes": req.notes
        }
    ))

    # Notification
    db.add(Notification(
        user_id=partner.user_id,
        title="Commission Rate Updated 📈",
        message=f"Your contractual platform commission rate has been adjusted to {float(req.commission_rate) * 100:.2f}%.",
        type="FINANCIAL_ALERT"
    ))

    db.commit()
    return {
        "success": True,
        "partner_id": partner.id,
        "new_commission_rate": float(partner.commission_rate)
    }


@router.get("/partners/{partner_id}/documents")
def get_partner_documents(partner_id: int, db: Session = Depends(get_db)):
    """Lists compliance & KYC documents for a specific partner."""
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return db.query(PartnerDocument).filter(PartnerDocument.partner_id == partner.id).order_by(PartnerDocument.uploaded_at.desc()).all()


@router.put("/partners/{partner_id}/documents/{document_id}", dependencies=[Depends(admin_mutation_rate_limiter)])
def verify_partner_document(
    partner_id: int,
    document_id: int,
    req: PartnerDocumentVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verifies or rejects a partner's compliance KYC document."""
    doc = db.query(PartnerDocument).filter(
        PartnerDocument.id == document_id,
        PartnerDocument.partner_id == partner_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    new_status = req.status.upper()
    if new_status not in ["VERIFIED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be VERIFIED or REJECTED.")

    doc.status = new_status
    db.add(AuditLog(
        user_id=current_user.id,
        action="PARTNER_DOCUMENT_VERIFY",
        resource_type="PARTNER_DOCUMENT",
        resource_id=str(doc.id),
        details={
            "partner_id": partner_id,
            "document_type": doc.document_type,
            "status": new_status,
            "notes": req.notes
        }
    ))
    db.commit()
    return {"success": True, "document_id": doc.id, "status": new_status}


# ==============================================================================
# 3. USER MANAGEMENT
# ==============================================================================

@router.get("/users")
def list_users(
    search: Optional[str] = Query(None),
    account_status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists users with search, role filter, account status filter, and pagination."""
    query = db.query(User)

    if account_status:
        query = query.filter(User.account_status == account_status.upper())
    if role:
        target_role = db.query(Role).filter(Role.name == role.lower()).first()
        if target_role:
            query = query.filter(User.roles.contains(target_role))
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_fmt),
                User.email.ilike(search_fmt),
                User.phone.ilike(search_fmt)
            )
        )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for u in users:
        booking_count = db.query(Booking).filter(Booking.user_id == u.id).count()
        city_name = u.profile.city.name if u.profile and u.profile.city else None
        locality_name = u.profile.locality.name if u.profile and u.profile.locality else None

        results.append(AdminUserResponse(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            phone=u.phone,
            roles=[r.name for r in u.roles],
            is_active=u.is_active,
            is_verified=u.is_verified,
            account_status=u.account_status,
            created_at=u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            total_bookings=booking_count,
            city_name=city_name,
            locality_name=locality_name
        ))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": results
    }


@router.get("/users/{user_id}")
def get_user_details(user_id: int, db: Session = Depends(get_db)):
    """Deep profile inspection of a user and summary of their activities."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    booking_count = db.query(Booking).filter(Booking.user_id == u.id).count()
    return {
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "phone": u.phone,
        "roles": [r.name for r in u.roles],
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "account_status": u.account_status,
        "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
        "total_bookings": booking_count,
        "profile": {
            "avatar_url": u.profile.avatar_url if u.profile else None,
            "city": u.profile.city.name if u.profile and u.profile.city else None,
            "locality": u.profile.locality.name if u.profile and u.profile.locality else None,
            "preferred_language": u.profile.preferred_language if u.profile else "English"
        }
    }


@router.put("/users/{user_id}/status", dependencies=[Depends(admin_mutation_rate_limiter)])
def update_user_status(
    user_id: int,
    req: UserStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Suspends, deactivates, or reactivates a user account.
    Revokes all active refresh tokens immediately if deactivated/suspended.
    Prevents self-deactivation by the authenticated super admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate or suspend your own super admin account.")

    new_status = req.account_status.upper()
    if new_status not in ["ACTIVE", "SUSPENDED", "DEACTIVATED"]:
        raise HTTPException(status_code=400, detail="Invalid account status.")

    old_status = user.account_status
    user.account_status = new_status
    user.is_active = (new_status == "ACTIVE")

    # If deactivating, revoke all active sessions immediately
    if new_status in ["SUSPENDED", "DEACTIVATED"]:
        now = datetime.datetime.now(datetime.timezone.utc)
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == False
        ).update({
            RefreshToken.is_revoked: True,
            RefreshToken.revoked_at: now
        }, synchronize_session=False)

    db.add(AuditLog(
        user_id=current_user.id,
        action="USER_STATUS_UPDATE",
        resource_type="USER",
        resource_id=str(user.id),
        details={
            "old_status": old_status,
            "new_status": new_status,
            "target_email": user.email,
            "reason": req.reason
        }
    ))

    db.commit()
    return {"success": True, "user_id": user.id, "account_status": new_status, "is_active": user.is_active}


@router.get("/users/{user_id}/bookings")
def get_user_bookings(user_id: int, db: Session = Depends(get_db)):
    """Retrieves full booking history for a specific customer."""
    bookings = db.query(Booking).filter(Booking.user_id == user_id).order_by(Booking.created_at.desc()).all()
    results = []
    for b in bookings:
        results.append({
            "id": b.id,
            "booking_reference": b.booking_reference,
            "booking_type": b.booking_type,
            "status": b.status,
            "final_payable": float(b.final_payable),
            "created_at": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
            "items_count": len(b.items)
        })
    return results


# ==============================================================================
# 4. BOOKINGS MANAGEMENT (ALL 5 VERTICALS)
# ==============================================================================

@router.get("/bookings")
def list_all_bookings(
    status: Optional[str] = Query(None),
    booking_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists bookings across all 5 verticals with search, status filters, and pagination."""
    query = db.query(Booking)
    if status:
        query = query.filter(Booking.status == status.upper())
    if booking_type:
        query = query.filter(Booking.booking_type == booking_type.upper())
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.join(User).filter(
            or_(
                Booking.booking_reference.ilike(search_fmt),
                User.email.ilike(search_fmt),
                User.full_name.ilike(search_fmt)
            )
        )
    if start_date:
        query = query.filter(Booking.created_at >= start_date)
    if end_date:
        query = query.filter(Booking.created_at <= end_date)

    total = query.count()
    bookings = query.order_by(Booking.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for b in bookings:
        items_desc = ", ".join(i.name for i in b.items[:2])
        if len(b.items) > 2:
            items_desc += f" (+{len(b.items) - 2} more)"
        results.append({
            "id": b.id,
            "booking_reference": b.booking_reference,
            "booking_type": b.booking_type,
            "status": b.status,
            "final_payable": float(b.final_payable),
            "customer_name": b.user.full_name if b.user else "Customer",
            "customer_email": b.user.email if b.user else "",
            "items_summary": items_desc,
            "created_at": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else ""
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "bookings": results
    }


@router.get("/bookings/{booking_reference}", response_model=AdminBookingDetailResponse)
def get_booking_detail(booking_reference: str, db: Session = Depends(get_db)):
    """Deep booking inspector with line items, payments, refunds, and customer details."""
    b = db.query(Booking).filter(Booking.booking_reference == booking_reference).first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")

    items = [
        AdminBookingItemDetail(
            id=i.id,
            item_type=i.item_type,
            item_id=i.item_id,
            name=i.name,
            quantity=i.quantity,
            unit_price=float(i.unit_price),
            subtotal=float(i.subtotal),
            details=i.details or {}
        ) for i in b.items
    ]

    payments = [
        AdminPaymentDetail(
            id=p.id,
            gateway_payment_id=p.gateway_payment_id,
            gateway_order_id=p.gateway_order_id,
            amount=float(p.amount),
            currency=p.currency,
            status=p.status,
            payment_gateway=p.payment_gateway,
            created_at=p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else None
        ) for p in b.payments
    ]

    refund_records = db.query(Refund).filter(Refund.booking_id == b.id).all()
    refunds = [
        AdminRefundDetail(
            id=r.id,
            gateway_refund_id=r.gateway_refund_id,
            amount=float(r.amount),
            reason=r.reason,
            status=r.status,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None
        ) for r in refund_records
    ]

    customer_info = {
        "id": b.user.id if b.user else None,
        "name": b.user.full_name if b.user else "Customer",
        "email": b.user.email if b.user else "",
        "phone": b.user.phone if b.user else ""
    }

    return AdminBookingDetailResponse(
        id=b.id,
        booking_reference=b.booking_reference,
        booking_type=b.booking_type,
        status=b.status,
        total_amount=float(b.total_amount),
        tax_amount=float(b.tax_amount),
        discount_amount=float(b.discount_amount),
        final_payable=float(b.final_payable),
        created_at=b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else None,
        customer=customer_info,
        items=items,
        payments=payments,
        refunds=refunds,
        cancellation_reason=b.cancellation_reason
    )


@router.post("/bookings/{booking_reference}/cancel", dependencies=[Depends(admin_mutation_rate_limiter)])
def admin_cancel_booking(
    booking_reference: str,
    reason: str = Query("Admin cancelled", min_length=3),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Safely cancels an active booking, restores inventory, initiates refund if paid, and logs audit."""
    b = db.query(Booking).filter(Booking.booking_reference == booking_reference).with_for_update().first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")

    if b.status in ["CANCELLED", "REFUNDED", "REFUND_PENDING", "EXPIRED", "FAILED"]:
        raise HTTPException(status_code=400, detail=f"Booking is already in {b.status} state.")

    previous_status = b.status
    BookingEngineService.release_inventory_for_booking(db, b)

    captured_payment = db.query(Payment).filter(
        Payment.booking_id == b.id,
        Payment.status.in_(["CAPTURED", "SUCCESS"])
    ).with_for_update().first()

    was_confirmed_paid = (
        previous_status == "CONFIRMED"
        and captured_payment is not None
        and b.final_payable > Decimal("0.00")
    )
    next_status = "REFUND_PENDING" if was_confirmed_paid else "CANCELLED"
    validate_state_transition(previous_status, next_status)

    b.status = next_status
    b.cancellation_reason = reason

    if was_confirmed_paid:
        refund_id = f"rfn_{uuid.uuid4().hex[:14]}"
        db.add(Refund(
            payment_id=captured_payment.id,
            booking_id=b.id,
            gateway_refund_id=refund_id,
            amount=captured_payment.amount,
            reason=f"Admin cancellation: {reason}",
            status="INITIATED"
        ))
        captured_payment.status = "REFUND_PENDING"

    db.add(AuditLog(
        user_id=current_user.id,
        action="ADMIN_BOOKING_CANCEL",
        resource_type="BOOKING",
        resource_id=b.booking_reference,
        details={"reason": reason, "previous_status": previous_status, "new_status": b.status}
    ))
    try:
        with db.begin_nested():
            NotificationService.notify_booking_cancelled(db, b, current_user.id, reason=reason, commit=False)
    except Exception:
        pass
    db.commit()
    return {"success": True, "booking_reference": b.booking_reference, "status": b.status}


# ==============================================================================
# 5. PAYMENTS & FINANCIAL MANAGEMENT
# ==============================================================================

@router.get("/financials/ledger")
def get_financial_ledger(db: Session = Depends(get_db)):
    """
    Returns system-wide revenue ledger metrics computed strictly via Decimal precision
    and ROUND_HALF_UP policies.
    """
    return calculate_revenue_metrics(db)


@router.get("/payments")
def list_payments(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists payment transactions across all gateways with search and status filters."""
    query = db.query(Payment).join(Booking).join(User, Booking.user_id == User.id)
    if status:
        query = query.filter(Payment.status == status.upper())
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Payment.gateway_payment_id.ilike(search_fmt),
                Payment.gateway_order_id.ilike(search_fmt),
                Booking.booking_reference.ilike(search_fmt),
                User.email.ilike(search_fmt)
            )
        )

    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for p in payments:
        results.append(AdminPaymentListItem(
            id=p.id,
            booking_id=p.booking_id,
            booking_reference=p.booking.booking_reference if p.booking else "",
            customer_name=p.user.full_name if p.user else "Customer",
            customer_email=p.user.email if p.user else "",
            gateway_payment_id=p.gateway_payment_id,
            gateway_order_id=p.gateway_order_id,
            amount=float(p.amount),
            currency=p.currency,
            status=p.status,
            payment_gateway=p.payment_gateway,
            created_at=p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else ""
        ))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "payments": results
    }


@router.get("/refunds")
def list_refunds(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists all refund transactions."""
    query = db.query(Refund).join(Booking).join(User, Booking.user_id == User.id)
    if status:
        query = query.filter(Refund.status == status.upper())

    total = query.count()
    refunds = query.order_by(Refund.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for r in refunds:
        results.append(AdminRefundListItem(
            id=r.id,
            booking_id=r.booking_id,
            booking_reference=r.booking.booking_reference if r.booking else "",
            customer_name=r.booking.user.full_name if r.booking and r.booking.user else "Customer",
            gateway_refund_id=r.gateway_refund_id,
            amount=float(r.amount),
            status=r.status,
            reason=r.reason,
            created_at=r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
        ))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "refunds": results
    }


@router.post("/bookings/{booking_reference}/refund", dependencies=[Depends(admin_mutation_rate_limiter)])
def process_admin_refund(
    booking_reference: str,
    req: AdminRefundActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Admin-authorized refund with idempotency and financial validation safeguards.
    Ensures refund does not exceed captured payments, locks rows, updates payment/booking status,
    and creates immutable audit entries.
    """
    b = db.query(Booking).filter(Booking.booking_reference == booking_reference).with_for_update().first()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")

    captured_payments = (
        db.query(Payment)
        .filter(
            Payment.booking_id == b.id,
            Payment.status.in_(["CAPTURED", "SUCCESS", "REFUND_PENDING", "PARTIALLY_REFUNDED"]),
        )
        .with_for_update()
        .all()
    )
    if not captured_payments:
        raise HTTPException(
            status_code=400,
            detail="Cannot process refund. No captured payment exists for this booking."
        )

    total_captured = sum((quantize_currency(p.amount) for p in captured_payments), Decimal("0.00"))
    existing_refunds = db.query(Refund).filter(
        Refund.booking_id == b.id,
        Refund.status.in_(["PROCESSED", "SUCCESS", "INITIATED"])
    ).all()
    total_refunded = sum((quantize_currency(r.amount) for r in existing_refunds), Decimal("0.00"))

    available_to_refund = total_captured - total_refunded
    if available_to_refund <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Booking has already been fully refunded.")

    refund_amt = quantize_currency(req.amount) if req.amount is not None else available_to_refund
    if refund_amt <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Refund amount must be greater than zero.")
    if refund_amt > available_to_refund:
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount ₹{refund_amt} exceeds refundable balance ₹{available_to_refund}."
        )

    target_payment = captured_payments[0]
    refund_record = Refund(
        payment_id=target_payment.id,
        booking_id=b.id,
        gateway_refund_id=f"rfnd_adm_{uuid.uuid4().hex[:12]}",
        amount=refund_amt,
        reason=req.reason,
        status="PROCESSED"
    )
    db.add(refund_record)

    # Synchronize Payment and Booking status with partial vs full refund semantics
    new_total_refunded = total_refunded + refund_amt
    if new_total_refunded >= total_captured:
        target_payment.status = "REFUNDED"
        b.status = "REFUNDED"
    else:
        target_payment.status = "PARTIALLY_REFUNDED"

    db.add(Notification(
        user_id=b.user_id,
        title="Refund Processed 💰",
        message=f"Admin-approved refund of ₹{float(refund_amt):.2f} for booking {b.booking_reference} has been processed.",
        type="PAYMENT_UPDATE"
    ))

    db.flush()
    try:
        with db.begin_nested():
            NotificationService.notify_refund_processed(db, refund_record, b, b.user_id, commit=False)
    except Exception:
        pass

    db.add(AuditLog(
        user_id=current_user.id,
        action="ADMIN_REFUND_ISSUED",
        resource_type="REFUND",
        resource_id=refund_record.gateway_refund_id,
        details={
            "booking_reference": b.booking_reference,
            "refund_amount": float(refund_amt),
            "payment_status": target_payment.status,
            "booking_status": b.status,
            "reason": req.reason
        }
    ))

    db.commit()
    return {
        "success": True,
        "gateway_refund_id": refund_record.gateway_refund_id,
        "amount": float(refund_amt),
        "booking_status": b.status,
        "payment_status": target_payment.status
    }


# ==============================================================================
# 6. PLATFORM MANAGEMENT (COUPONS, NOTIFICATIONS, AUDIT LOGS)
# ==============================================================================

@router.get("/coupons")
def list_coupons(db: Session = Depends(get_db)):
    """Lists all platform promotional coupons."""
    return db.query(Coupon).order_by(Coupon.created_at.desc()).all()


@router.post("/coupons", dependencies=[Depends(admin_mutation_rate_limiter)])
def create_coupon(
    req: CreateCouponRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new promotional discount coupon with audit logging."""
    code_clean = req.code.strip().upper()
    existing = db.query(Coupon).filter(Coupon.code == code_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Coupon with code '{code_clean}' already exists.")

    coupon = Coupon(
        code=code_clean,
        description=req.description,
        discount_type=req.discount_type.upper(),
        discount_value=Decimal(str(req.discount_value)),
        min_order_value=Decimal(str(req.min_order_value)),
        max_discount=Decimal(str(req.max_discount)),
        usage_limit=req.usage_limit,
        valid_until=req.valid_until,
        is_active=True
    )
    db.add(coupon)
    db.add(AuditLog(
        user_id=current_user.id,
        action="COUPON_CREATED",
        resource_type="COUPON",
        resource_id=code_clean,
        details={"discount_type": req.discount_type, "discount_value": req.discount_value}
    ))
    db.commit()
    return {"success": True, "coupon": coupon.code}


@router.put("/coupons/{coupon_id}/toggle", dependencies=[Depends(admin_mutation_rate_limiter)])
def toggle_coupon_status(
    coupon_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggles active/inactive state of a promotional coupon."""
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    coupon.is_active = not coupon.is_active
    db.add(AuditLog(
        user_id=current_user.id,
        action="COUPON_STATUS_TOGGLE",
        resource_type="COUPON",
        resource_id=coupon.code,
        details={"is_active": coupon.is_active}
    ))
    db.commit()
    return {"success": True, "coupon": coupon.code, "is_active": coupon.is_active}


@router.delete("/coupons/{coupon_id}", dependencies=[Depends(admin_mutation_rate_limiter)])
def delete_coupon(
    coupon_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes an unused promotional coupon."""
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    db.add(AuditLog(
        user_id=current_user.id,
        action="COUPON_DELETED",
        resource_type="COUPON",
        resource_id=coupon.code
    ))
    db.delete(coupon)
    db.commit()
    return {"success": True, "message": "Coupon deleted."}


@router.get("/notifications")
def list_recent_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists recent platform notifications."""
    total = db.query(Notification).count()
    notifs = db.query(Notification).order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    results = []
    for n in notifs:
        results.append({
            "id": n.id,
            "user_id": n.user_id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else ""
        })
    return {"total": total, "notifications": results}


@router.post("/notifications/broadcast", dependencies=[Depends(admin_mutation_rate_limiter)])
def broadcast_notification(
    req: BroadcastNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Broadcasts a platform alert or notification to all customers, partners, or everyone.
    """
    target = req.target_role.upper()
    query = db.query(User).filter(User.is_active == True)

    if target == "CUSTOMER":
        cust_role = db.query(Role).filter(Role.name == "customer").first()
        if cust_role:
            query = query.filter(User.roles.contains(cust_role))
    elif target == "PARTNER":
        # Any partner user
        partner_user_ids = [p.user_id for p in db.query(Partner.user_id).all()]
        query = query.filter(User.id.in_(partner_user_ids))

    users = query.all()
    for u in users:
        db.add(Notification(
            user_id=u.id,
            title=req.title,
            message=req.message,
            type=req.type
        ))

    db.add(AuditLog(
        user_id=current_user.id,
        action="BROADCAST_NOTIFICATION",
        resource_type="NOTIFICATION",
        resource_id=target,
        details={"title": req.title, "recipients_count": len(users)}
    ))

    db.commit()
    return {"success": True, "recipients_count": len(users), "target": target}


@router.get("/audit-logs")
def list_audit_logs(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Paginated search for immutable system audit logs."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type.upper())
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for l in logs:
        results.append(AdminAuditLogItem(
            id=l.id,
            user_id=l.user_id,
            user_email=l.user.email if l.user else None,
            action=l.action,
            resource_type=l.resource_type,
            resource_id=l.resource_id,
            details=l.details or {},
            created_at=l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else ""
        ))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": results
    }
