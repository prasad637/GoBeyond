import uuid
import re
import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.rate_limit import partner_api_rate_limiter
from app.core.validators import validate_file_upload, validate_safe_input
from app.core.cache import CacheService

from app.core.database import get_db
from app.models.partner import Partner, PartnerDocument
from app.models.user import User, Role
from app.models.booking import Booking, BookingItem
from app.models.payment import Payment, Refund
from app.models.dining import Restaurant, RestaurantMenu, DiningTable, DiningReservation
from app.models.movie import Cinema, Screen, MovieShow, Movie, Seat
from app.models.event import Event, EventTicketType
from app.models.sports import SportsVenue, Activity, ActivitySlot
from app.models.audit import AuditLog, Notification
from app.models.location import Location
from app.services.revenue import calculate_revenue_metrics, quantize_currency
from app.schemas.partner import (
    PartnerRegisterRequest,
    PartnerProfileUpdate,
    PartnerResponse,
    PartnerDocumentUpload,
    PartnerDocumentResponse,
    PartnerAnalyticsResponse,
    PartnerFinancialsResponse,
    PartnerFinancialTransaction,
    PartnerBookingDetail,
    BookingItemDetail,
    RestaurantProfileUpdate,
    RestaurantMenuCreate,
    RestaurantMenuUpdate,
    DiningTableCreate,
    DiningTableUpdate,
    ReservationStatusUpdate,
    CinemaProfileUpdate,
    ScreenCreate,
    MovieShowCreate,
    MovieShowUpdate,
    SeatUpdate,
    EventCreate,
    EventUpdate,
    EventTicketTypeCreate,
    EventTicketTypeUpdate,
    SportsVenueCreate,
    SportsVenueUpdate,
    ActivityCreate,
    ActivityUpdate,
    ActivitySlotCreate,
    ActivitySlotUpdate,
    QRVerificationRequest,
    QRVerificationResponse
)
from app.api.deps import (
    get_current_user,
    get_current_partner,
    get_current_approved_partner,
    require_roles
)

router = APIRouter(dependencies=[Depends(partner_api_rate_limiter)])


# ==============================================================================
# TENANT ISOLATION HELPERS
# ==============================================================================

def get_partner_booking_ids(db: Session, partner_id: int) -> List[int]:
    """
    Resolves all booking IDs that contain items belonging to a specific partner.
    Enforces strict tenant data isolation across all 5 entertainment verticals.
    """
    cinema_ids = [c[0] for c in db.query(Cinema.id).filter(Cinema.partner_id == partner_id).all()]
    restaurant_ids = [r[0] for r in db.query(Restaurant.id).filter(Restaurant.partner_id == partner_id).all()]
    event_ids = [e[0] for e in db.query(Event.id).filter(Event.partner_id == partner_id).all()]
    venue_ids = [v[0] for v in db.query(SportsVenue.id).filter(SportsVenue.partner_id == partner_id).all()]
    
    activity_ids = [a[0] for a in db.query(Activity.id).filter(
        (Activity.partner_id == partner_id) | (Activity.venue_id.in_(venue_ids) if venue_ids else False)
    ).all()]

    seat_ids = [s[0] for s in db.query(Seat.id).join(Screen).filter(Screen.cinema_id.in_(cinema_ids)).all()] if cinema_ids else []
    show_ids = [ms[0] for ms in db.query(MovieShow.id).join(Screen).filter(Screen.cinema_id.in_(cinema_ids)).all()] if cinema_ids else []
    table_ids = [t[0] for t in db.query(DiningTable.id).filter(DiningTable.restaurant_id.in_(restaurant_ids)).all()] if restaurant_ids else []
    ticket_ids = [tt[0] for tt in db.query(EventTicketType.id).filter(EventTicketType.event_id.in_(event_ids)).all()] if event_ids else []
    slot_ids = [sl[0] for sl in db.query(ActivitySlot.id).filter(ActivitySlot.activity_id.in_(activity_ids)).all()] if activity_ids else []

    b_ids = set()
    if seat_ids:
        b_ids.update(b[0] for b in db.query(BookingItem.booking_id).filter(BookingItem.item_type == "SEAT", BookingItem.item_id.in_(seat_ids)).all())
    if show_ids:
        for item in db.query(BookingItem).filter(BookingItem.item_type == "SEAT").all():
            if item.details and str(item.details.get("show_id")) in [str(sid) for sid in show_ids]:
                b_ids.add(item.booking_id)
    if table_ids:
        b_ids.update(b[0] for b in db.query(BookingItem.booking_id).filter(BookingItem.item_type == "TABLE", BookingItem.item_id.in_(table_ids)).all())
    if ticket_ids:
        b_ids.update(b[0] for b in db.query(BookingItem.booking_id).filter(BookingItem.item_type == "TICKET", BookingItem.item_id.in_(ticket_ids)).all())
    if slot_ids:
        b_ids.update(b[0] for b in db.query(BookingItem.booking_id).filter(BookingItem.item_type == "SLOT", BookingItem.item_id.in_(slot_ids)).all())

    return list(b_ids)


def _generate_slug(title: str) -> str:
    cleaned = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return f"{cleaned[:240]}-{uuid.uuid4().hex[:6]}"


def _ensure_partner_type(current_partner: Partner, allowed_types: List[str], label: str) -> None:
    """Enforces vertical partner_type authorization across specialized partner endpoints."""
    if (current_partner.partner_type or "").upper() not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Endpoint exclusive to {label}."
        )


# ==============================================================================
# 1. CORE & ONBOARDING ENDPOINTS
# ==============================================================================

@router.get("/profile", response_model=PartnerResponse)
def get_partner_profile(
    current_partner: Partner = Depends(get_current_partner)
):
    """Returns the authenticated partner's business profile."""
    return current_partner


@router.put("/profile", response_model=PartnerResponse)
def update_partner_profile(
    req: PartnerProfileUpdate,
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db)
):
    """
    Updates partner business profile details and payout configuration.
    Commission rate cannot be modified by the partner.
    """
    if req.business_name is not None and req.business_name.strip():
        current_partner.business_name = req.business_name.strip()
    if req.contact_email is not None:
        current_partner.contact_email = str(req.contact_email)
    if req.contact_phone is not None and req.contact_phone.strip():
        current_partner.contact_phone = req.contact_phone.strip()
    if req.gstin is not None:
        current_partner.gstin = req.gstin.strip() if req.gstin else None
    if req.pan_number is not None:
        current_partner.pan_number = req.pan_number.strip() if req.pan_number else None

    payout_info = {}
    if req.bank_name:
        payout_info["bank_name"] = req.bank_name
    if req.bank_account_number:
        payout_info["bank_account_number"] = f"***{req.bank_account_number[-4:]}"
    if req.bank_ifsc:
        payout_info["bank_ifsc"] = req.bank_ifsc
    if req.account_holder_name:
        payout_info["account_holder_name"] = req.account_holder_name

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="PARTNER_PROFILE_UPDATED",
        resource_type="PARTNER",
        resource_id=str(current_partner.id),
        details={"business_name": current_partner.business_name, "payout_info": payout_info}
    ))

    db.commit()
    db.refresh(current_partner)
    return current_partner


@router.post("/register", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
def register_partner(
    req: PartnerRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Registers a new partner application in PENDING_APPROVAL status."""
    existing = db.query(Partner).filter(Partner.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already registered as a partner.")

    partner = Partner(
        user_id=current_user.id,
        business_name=req.business_name,
        partner_type=req.partner_type.upper(),
        contact_email=req.contact_email,
        contact_phone=req.contact_phone,
        gstin=req.gstin,
        pan_number=req.pan_number,
        status="PENDING_APPROVAL"
    )
    current_user.account_status = "PENDING_APPROVAL"
    db.add(partner)

    role_type = req.partner_type.lower()
    role_name = f"partner_{role_type}"
    if role_type == "activities":
        role_name = "partner_sports"
    role = db.query(Role).filter(Role.name == role_name).first()
    if role and role not in current_user.roles:
        current_user.roles.append(role)

    db.add(AuditLog(
        user_id=current_user.id,
        action="PARTNER_ONBOARDING_REQUEST",
        resource_type="PARTNER",
        resource_id=req.business_name
    ))

    # Alert super admin of new partner application
    try:
        from app.services.notifications.service import NotificationService
        NotificationService.notify_admin_alert(
            db=db,
            alert_type="ADMIN_NEW_PARTNER_APPLIED",
            title=f"New Partner Application: {partner.business_name} 📝",
            description=f"Partner {partner.business_name} ({partner.partner_type}) submitted an application.",
            details={"partner_id": partner.id, "business_name": partner.business_name}
        )
    except Exception:
        pass

    db.commit()
    db.refresh(partner)
    return partner


@router.get("/documents", response_model=List[PartnerDocumentResponse])
def get_partner_documents(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db)
):
    """Lists compliance & KYC documents uploaded by the partner."""
    return db.query(PartnerDocument).filter(PartnerDocument.partner_id == current_partner.id).order_by(PartnerDocument.uploaded_at.desc()).all()


@router.post("/documents")
def upload_partner_document(
    req: PartnerDocumentUpload,
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db)
):
    """Uploads a compliance & KYC verification document with payload sanitization."""
    safe_url = validate_safe_input(req.document_url, field_name="document_url")
    doc = PartnerDocument(
        partner_id=current_partner.id,
        document_type=req.document_type.upper(),
        document_url=safe_url,
        status="SUBMITTED"
    )
    db.add(doc)
    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="PARTNER_DOCUMENT_UPLOADED",
        resource_type="PARTNER_DOCUMENT",
        resource_id=req.document_type.upper()
    ))

    # Alert super admin of KYC document submission
    try:
        from app.services.notifications.service import NotificationService
        NotificationService.notify_admin_alert(
            db=db,
            alert_type="ADMIN_KYC_SUBMITTED",
            title=f"KYC Document Submitted: {current_partner.business_name} 📄",
            description=f"Partner {current_partner.business_name} uploaded {req.document_type.upper()} KYC document.",
            details={"partner_id": current_partner.id, "document_type": req.document_type.upper()}
        )
    except Exception:
        pass

    db.commit()
    return {"success": True, "message": "Verification document uploaded successfully."}


@router.post("/documents/upload-file")
def upload_partner_document_file(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db)
):
    """
    Direct multipart file upload for KYC verification documents.
    Enforces maximum file size (5MB), MIME type whitelist, extension whitelist,
    and binary magic bytes verification to prevent malicious code execution.
    """
    validate_file_upload(file)

    clean_ext = file.filename[file.filename.rfind("."):].lower()
    safe_filename = f"kyc_{current_partner.id}_{uuid.uuid4().hex[:12]}{clean_ext}"
    safe_url = f"/uploads/kyc/{safe_filename}"

    doc = PartnerDocument(
        partner_id=current_partner.id,
        document_type=document_type.upper(),
        document_url=safe_url,
        status="SUBMITTED"
    )
    db.add(doc)
    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="PARTNER_DOCUMENT_UPLOADED",
        resource_type="PARTNER_DOCUMENT",
        resource_id=document_type.upper()
    ))
    db.commit()
    return {"success": True, "message": "Document file uploaded and validated.", "document_url": safe_url, "document_id": doc.id}


# ==============================================================================
# 2. OVERVIEW, ANALYTICS & REVENUE ENDPOINTS
# ==============================================================================

@router.get("/analytics", response_model=PartnerAnalyticsResponse)
def get_partner_analytics(
    current_partner: Partner = Depends(get_current_partner),
    db: Session = Depends(get_db)
):
    """
    Returns analytics strictly isolated to the authenticated partner.
    Calculates verified revenue, confirmed bookings, and time-series performance.
    """
    total_listings = 0
    if current_partner.partner_type == "RESTAURANT":
        total_listings = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).count()
    elif current_partner.partner_type == "CINEMA":
        total_listings = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).count()
    elif current_partner.partner_type == "EVENT":
        total_listings = db.query(Event).filter(Event.partner_id == current_partner.id).count()
    elif current_partner.partner_type in ["SPORTS", "ACTIVITIES"]:
        total_listings = (
            db.query(SportsVenue).filter(SportsVenue.partner_id == current_partner.id).count() +
            db.query(Activity).filter(Activity.partner_id == current_partner.id).count()
        )

    partner_b_ids = get_partner_booking_ids(db, current_partner.id)
    all_bookings = []
    if partner_b_ids:
        all_bookings = db.query(Booking).filter(Booking.id.in_(partner_b_ids)).all()

    total_count = len(all_bookings)
    confirmed_count = sum(1 for b in all_bookings if b.status == "CONFIRMED")
    pending_count = sum(1 for b in all_bookings if b.status in ["PENDING", "INVENTORY_HELD", "PAYMENT_PENDING"])
    cancelled_count = sum(1 for b in all_bookings if b.status == "CANCELLED")
    refunded_count = sum(1 for b in all_bookings if b.status in ["REFUNDED", "REFUND_PENDING"])

    # Compute financial metrics using Decimal precision service
    financials = calculate_revenue_metrics(db, booking_ids=partner_b_ids)

    # 7-day daily breakdown for charts
    daily_stats = []
    now = datetime.datetime.now(datetime.timezone.utc)
    for i in range(6, -1, -1):
        day = now - datetime.timedelta(days=i)
        day_date = day.date()
        day_bookings = [
            b for b in all_bookings 
            if b.created_at and b.created_at.date() == day_date and b.status == "CONFIRMED"
        ]
        day_revenue = sum(float(b.final_payable) for b in day_bookings)
        daily_stats.append({
            "date": day_date.strftime("%b %d"),
            "bookings": len(day_bookings),
            "revenue": round(day_revenue, 2)
        })

    # Recent bookings
    recent_bookings = []
    sorted_bookings = sorted(all_bookings, key=lambda b: b.created_at or datetime.datetime.min, reverse=True)[:10]
    for b in sorted_bookings:
        recent_bookings.append({
            "id": b.id,
            "reference": b.booking_reference,
            "type": b.booking_type,
            "status": b.status,
            "amount": float(b.final_payable),
            "customer_name": b.user.full_name if b.user else "Customer",
            "created_at": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
            "items_count": len(b.items)
        })

    return PartnerAnalyticsResponse(
        partner_type=current_partner.partner_type,
        business_name=current_partner.business_name,
        status=current_partner.status,
        commission_rate=float(current_partner.commission_rate),
        total_listings=total_listings,
        total_bookings=total_count,
        confirmed_bookings=confirmed_count,
        pending_bookings=pending_count,
        cancelled_bookings=cancelled_count,
        refunded_bookings=refunded_count,
        total_revenue=financials["partner_settlements_payable"],
        gross_revenue=financials["gross_confirmed_booking_value"],
        platform_fee=financials["actual_platform_revenue"],
        partner_payout=financials["partner_settlements_payable"],
        daily_stats=daily_stats,
        recent_bookings=recent_bookings
    )


@router.get("/financials", response_model=PartnerFinancialsResponse)
def get_partner_financials(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """
    Returns verified revenue, captured payments, platform fee and partner payouts
    strictly computed via revenue calculation service.
    """
    partner_b_ids = get_partner_booking_ids(db, current_partner.id)
    financials = calculate_revenue_metrics(db, booking_ids=partner_b_ids)

    # Build transaction-level ledger
    transactions = []
    if partner_b_ids:
        bookings = db.query(Booking).filter(Booking.id.in_(partner_b_ids)).order_by(Booking.created_at.desc()).limit(100).all()
        # Pre-fetch refunds
        all_refunds = db.query(Refund).filter(Refund.booking_id.in_(partner_b_ids)).all()
        refunds_by_booking = {}
        for r in all_refunds:
            refunds_by_booking.setdefault(r.booking_id, []).append(r)

        for b in bookings:
            captured_dec = quantize_currency(sum((p.amount for p in b.payments if p.status in ["CAPTURED", "SUCCESS"]), Decimal("0.00")))
            b_refunds = refunds_by_booking.get(b.id, [])
            refunded_dec = quantize_currency(sum((r.amount for r in b_refunds if r.status in ["PROCESSED", "SUCCESS"]), Decimal("0.00")))
            net_dec = quantize_currency(captured_dec - refunded_dec)
            comm_rate_dec = Decimal(str(current_partner.commission_rate)) if current_partner.commission_rate is not None else Decimal("0.1000")
            fee_dec = quantize_currency(net_dec * comm_rate_dec) if net_dec > 0 else Decimal("0.00")
            payout_dec = quantize_currency(net_dec - fee_dec) if net_dec > 0 else Decimal("0.00")

            transactions.append(PartnerFinancialTransaction(
                booking_id=b.id,
                booking_reference=b.booking_reference,
                booking_type=b.booking_type,
                status=b.status,
                created_at=b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
                gross_amount=float(quantize_currency(b.final_payable)),
                captured_amount=float(captured_dec),
                refund_amount=float(refunded_dec),
                net_collected=float(net_dec),
                commission_rate=float(comm_rate_dec),
                platform_fee=float(fee_dec),
                partner_payout=float(payout_dec)
            ))

    return PartnerFinancialsResponse(
        partner_id=current_partner.id,
        business_name=current_partner.business_name,
        partner_type=current_partner.partner_type,
        commission_rate=float(current_partner.commission_rate),
        gross_confirmed_booking_value=financials["gross_confirmed_booking_value"],
        total_captured_payments=financials["total_captured_payments"],
        total_refunded_amount=financials["total_refunded_amount"],
        net_collected_amount=financials["net_collected_amount"],
        actual_platform_revenue=financials["actual_platform_revenue"],
        partner_settlements_payable=financials["partner_settlements_payable"],
        total_over_refunded_amount=financials["total_over_refunded_amount"],
        requires_financial_reconciliation=financials["requires_financial_reconciliation"],
        transactions=transactions
    )


# ==============================================================================
# 3. BOOKINGS & CUSTOMER RESERVATIONS
# ==============================================================================

@router.get("/bookings")
def get_partner_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """
    Returns customer bookings for this partner's catalog with filters and pagination.
    Strict tenant isolation is enforced.
    """
    partner_b_ids = get_partner_booking_ids(db, current_partner.id)
    if not partner_b_ids:
        return {"total": 0, "page": page, "page_size": page_size, "bookings": []}

    query = db.query(Booking).filter(Booking.id.in_(partner_b_ids))

    if status_filter:
        query = query.filter(Booking.status == status_filter.upper())

    if search:
        search_term = f"%{search.strip()}%"
        query = query.join(User).filter(
            (Booking.booking_reference.ilike(search_term)) |
            (User.full_name.ilike(search_term)) |
            (User.phone.ilike(search_term)) |
            (User.email.ilike(search_term))
        )

    if start_date:
        try:
            s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Booking.created_at >= s_date)
        except ValueError:
            pass

    if end_date:
        try:
            e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
            query = query.filter(Booking.created_at < e_date)
        except ValueError:
            pass

    total = query.count()
    bookings = query.order_by(Booking.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for b in bookings:
        result.append({
            "id": b.id,
            "booking_reference": b.booking_reference,
            "booking_type": b.booking_type,
            "customer_name": b.user.full_name if b.user else "Customer",
            "customer_email": b.user.email if b.user else "",
            "customer_phone": b.user.phone if b.user else "",
            "status": b.status,
            "amount": float(b.final_payable),
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "qr_code_token": b.qr_code_token,
            "items": [
                {
                    "id": item.id,
                    "item_type": item.item_type,
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "subtotal": float(item.subtotal),
                    "details": item.details or {}
                }
                for item in b.items
            ]
        })

    return {"total": total, "page": page, "page_size": page_size, "bookings": result}


@router.get("/bookings/{booking_reference}", response_model=PartnerBookingDetail)
def get_partner_booking_detail(
    booking_reference: str,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """
    Returns full details for a single booking.
    Strictly verifies that the booking belongs to this partner.
    """
    booking = db.query(Booking).filter(Booking.booking_reference == booking_reference).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    partner_b_ids = get_partner_booking_ids(db, current_partner.id)
    if booking.id not in partner_b_ids:
        raise HTTPException(status_code=403, detail="Access denied. Booking belongs to another establishment.")

    items_list = [
        BookingItemDetail(
            id=item.id,
            item_type=item.item_type,
            name=item.name,
            quantity=item.quantity,
            unit_price=float(item.unit_price),
            subtotal=float(item.subtotal),
            details=item.details or {}
        )
        for item in booking.items
    ]

    payments_summary = [
        {
            "id": p.id,
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status,
            "gateway": p.gateway,
            "gateway_payment_id": p.gateway_payment_id,
            "created_at": p.created_at.isoformat() if p.created_at else ""
        }
        for p in booking.payments
    ]

    b_refunds = db.query(Refund).filter(Refund.booking_id == booking.id).all()
    refunds_summary = [
        {
            "id": r.id,
            "amount": float(r.amount),
            "status": r.status,
            "reason": r.reason,
            "gateway_refund_id": r.gateway_refund_id,
            "created_at": r.created_at.isoformat() if r.created_at else ""
        }
        for r in b_refunds
    ]

    return PartnerBookingDetail(
        id=booking.id,
        booking_reference=booking.booking_reference,
        booking_type=booking.booking_type,
        status=booking.status,
        customer_id=booking.user_id,
        customer_name=booking.user.full_name if booking.user else "Customer",
        customer_email=booking.user.email if booking.user else "",
        customer_phone=booking.user.phone if booking.user else "",
        total_amount=float(booking.total_amount),
        discount_amount=float(booking.discount_amount),
        tax_amount=float(booking.tax_amount),
        final_payable=float(booking.final_payable),
        created_at=booking.created_at.isoformat() if booking.created_at else "",
        qr_code_token=booking.qr_code_token,
        items=items_list,
        payments_summary=payments_summary,
        refunds_summary=refunds_summary
    )


# ==============================================================================
# 4. QR GATE SCANNER TOOL
# ==============================================================================

@router.post("/verify-qr-pass", response_model=QRVerificationResponse)
def verify_qr_pass(
    req: QRVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gate scanner verification tool used by organizers/cinemas/turfs or pass holders.
    Strictly verifies that partner scanners can only grant entry to their own establishment's bookings.
    """
    token = req.qr_token.strip()
    booking = db.query(Booking).filter(
        (Booking.qr_code_token == token) | (Booking.booking_reference == token)
    ).first()

    if not booking:
        return QRVerificationResponse(
            valid=False,
            booking_reference="UNKNOWN",
            booking_type="UNKNOWN",
            customer_name="Unknown",
            status="INVALID",
            items=[],
            message="Invalid QR pass or booking token. No matching booking found."
        )

    user_role_names = [r.name.lower() for r in current_user.roles]
    is_admin = "super_admin" in user_role_names or "admin" in user_role_names
    partner = db.query(Partner).filter(Partner.user_id == current_user.id).first()

    establishment_name = "GO BEYOND Experience"

    if partner:
        establishment_name = partner.business_name
        partner_b_ids = get_partner_booking_ids(db, partner.id)
        if booking.id not in partner_b_ids:
            return QRVerificationResponse(
                valid=False,
                booking_reference=booking.booking_reference,
                booking_type=booking.booking_type,
                customer_name="Access Denied",
                status="UNAUTHORIZED_PARTNER",
                items=[],
                message="Access Denied. This booking pass belongs to a different establishment."
            )
    elif not is_admin:
        if booking.user_id != current_user.id:
            return QRVerificationResponse(
                valid=False,
                booking_reference=booking.booking_reference,
                booking_type=booking.booking_type,
                customer_name="Access Denied",
                status="UNAUTHORIZED_PARTNER",
                items=[],
                message="Access Denied. This booking pass belongs to a different customer/establishment."
            )

    items_data = []
    for item in booking.items:
        items_data.append({
            "name": item.name,
            "quantity": item.quantity,
            "details": item.details
        })

    if booking.status != "CONFIRMED":
        return QRVerificationResponse(
            valid=False,
            booking_reference=booking.booking_reference,
            booking_type=booking.booking_type,
            customer_name=booking.user.full_name if booking.user else "Customer",
            status=booking.status,
            items=items_data,
            message=f"Access Denied. Pass status is {booking.status}."
        )

    db.add(AuditLog(
        user_id=current_user.id,
        action="QR_PASS_SCANNED",
        resource_type="BOOKING",
        resource_id=booking.booking_reference,
        details={"scanned_by": partner.business_name if partner else current_user.email}
    ))
    db.commit()

    return QRVerificationResponse(
        valid=True,
        booking_reference=booking.booking_reference,
        booking_type=booking.booking_type,
        customer_name=booking.user.full_name if booking.user else "Customer",
        status="VERIFIED_ENTRY_GRANTED",
        items=items_data,
        message=f"Valid Pass! Entry Granted to {establishment_name}."
    )


# ==============================================================================
# 5. NOTIFICATIONS ENDPOINTS
# ==============================================================================

@router.get("/notifications")
def get_partner_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns notifications for the authenticated partner user."""
    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()

    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "is_read": n.is_read,
            "data": n.data or {},
            "created_at": n.created_at.isoformat() if n.created_at else ""
        }
        for n in notifs
    ]


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks a single notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notif.is_read = True
    db.commit()
    return {"success": True, "message": "Notification marked as read."}


@router.put("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks all notifications for this partner as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"success": True, "message": "All notifications marked as read."}


# ==============================================================================
# 6. VERTICAL: RESTAURANT MANAGEMENT
# ==============================================================================

@router.get("/restaurant/profile")
def get_restaurant_profile(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Returns restaurant establishment details for this restaurant partner."""
    if current_partner.partner_type != "RESTAURANT":
        raise HTTPException(status_code=403, detail="Endpoint exclusive to Restaurant Partners.")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found for this partner.")
    return {
        "id": rest.id,
        "name": rest.name,
        "slug": rest.slug,
        "cuisines": rest.cuisines or [],
        "cost_for_two": rest.cost_for_two,
        "address": rest.address,
        "phone": rest.phone,
        "timings": rest.timings,
        "images": rest.images or [],
        "rating": rest.rating,
        "review_count": rest.review_count,
        "has_buffet": rest.has_buffet,
        "has_alcohol": rest.has_alcohol,
        "is_pure_veg": rest.is_pure_veg,
        "is_active": rest.is_active
    }


@router.put("/restaurant/profile")
def update_restaurant_profile(
    req: RestaurantProfileUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates restaurant details, timings, cuisines, and operating attributes."""
    if current_partner.partner_type != "RESTAURANT":
        raise HTTPException(status_code=403, detail="Endpoint exclusive to Restaurant Partners.")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    if req.name is not None and req.name.strip():
        rest.name = req.name.strip()
    if req.cuisines is not None:
        rest.cuisines = req.cuisines
    if req.cost_for_two is not None:
        rest.cost_for_two = req.cost_for_two
    if req.address is not None:
        rest.address = req.address
    if req.phone is not None:
        rest.phone = req.phone
    if req.timings is not None:
        rest.timings = req.timings
    if req.images is not None:
        rest.images = req.images
    if req.has_buffet is not None:
        rest.has_buffet = req.has_buffet
    if req.has_alcohol is not None:
        rest.has_alcohol = req.has_alcohol
    if req.is_pure_veg is not None:
        rest.is_pure_veg = req.is_pure_veg
    if req.is_active is not None:
        rest.is_active = req.is_active

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="RESTAURANT_PROFILE_UPDATED",
        resource_type="RESTAURANT",
        resource_id=str(rest.id),
        details={"name": rest.name, "cost_for_two": rest.cost_for_two}
    ))
    db.commit()
    db.refresh(rest)
    return {
        "id": rest.id,
        "name": rest.name,
        "slug": rest.slug,
        "cuisines": rest.cuisines or [],
        "cost_for_two": rest.cost_for_two,
        "address": rest.address,
        "phone": rest.phone,
        "timings": rest.timings,
        "images": rest.images or [],
        "has_buffet": rest.has_buffet,
        "has_alcohol": rest.has_alcohol,
        "is_pure_veg": rest.is_pure_veg,
        "is_active": rest.is_active
    }


@router.get("/restaurant/menus")
def get_restaurant_menus(
    category: Optional[str] = Query(None),
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Returns the menu catalog of the restaurant."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        return []
    q = db.query(RestaurantMenu).filter(RestaurantMenu.restaurant_id == rest.id)
    if category:
        q = q.filter(RestaurantMenu.category == category)
    items = q.order_by(RestaurantMenu.category, RestaurantMenu.item_name).all()
    return [
        {
            "id": item.id,
            "restaurant_id": item.restaurant_id,
            "category": item.category,
            "item_name": item.item_name,
            "description": item.description,
            "price": float(item.price),
            "is_veg": item.is_veg,
            "is_bestseller": item.is_bestseller,
            "image_url": item.image_url,
            "is_available": item.is_available
        }
        for item in items
    ]


@router.post("/restaurant/menus", status_code=status.HTTP_201_CREATED)
def create_menu_item(
    req: RestaurantMenuCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Adds a new dish / item to the restaurant menu."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    item = RestaurantMenu(
        restaurant_id=rest.id,
        category=req.category.strip(),
        item_name=req.item_name.strip(),
        description=req.description,
        price=Decimal(str(req.price)),
        is_veg=req.is_veg,
        is_bestseller=req.is_bestseller,
        image_url=req.image_url,
        is_available=req.is_available
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="MENU_ITEM_CREATED",
        resource_type="RESTAURANT_MENU",
        resource_id=str(item.id),
        details={"name": item.item_name, "price": str(item.price)}
    ))
    db.commit()
    return {
        "id": item.id,
        "restaurant_id": item.restaurant_id,
        "category": item.category,
        "item_name": item.item_name,
        "description": item.description,
        "price": float(item.price),
        "is_veg": item.is_veg,
        "is_bestseller": item.is_bestseller,
        "image_url": item.image_url,
        "is_available": item.is_available
    }


@router.put("/restaurant/menus/{menu_id}")
def update_menu_item(
    menu_id: int,
    req: RestaurantMenuUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates pricing, description or availability for a menu item."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    item = db.query(RestaurantMenu).filter(
        RestaurantMenu.id == menu_id,
        RestaurantMenu.restaurant_id == rest.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found or unauthorized.")

    if req.category is not None:
        item.category = req.category.strip()
    if req.item_name is not None:
        item.item_name = req.item_name.strip()
    if req.description is not None:
        item.description = req.description
    if req.price is not None:
        item.price = Decimal(str(req.price))
    if req.is_veg is not None:
        item.is_veg = req.is_veg
    if req.is_bestseller is not None:
        item.is_bestseller = req.is_bestseller
    if req.image_url is not None:
        item.image_url = req.image_url
    if req.is_available is not None:
        item.is_available = req.is_available

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="MENU_ITEM_UPDATED",
        resource_type="RESTAURANT_MENU",
        resource_id=str(item.id),
        details={"name": item.item_name, "is_available": item.is_available}
    ))
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "restaurant_id": item.restaurant_id,
        "category": item.category,
        "item_name": item.item_name,
        "description": item.description,
        "price": float(item.price),
        "is_veg": item.is_veg,
        "is_bestseller": item.is_bestseller,
        "image_url": item.image_url,
        "is_available": item.is_available
    }


@router.delete("/restaurant/menus/{menu_id}")
def delete_menu_item(
    menu_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Deletes a menu item from the restaurant catalog."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    item = db.query(RestaurantMenu).filter(
        RestaurantMenu.id == menu_id,
        RestaurantMenu.restaurant_id == rest.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found or unauthorized.")

    db.delete(item)
    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="MENU_ITEM_DELETED",
        resource_type="RESTAURANT_MENU",
        resource_id=str(menu_id)
    ))
    db.commit()
    return {"success": True, "message": "Menu item deleted successfully."}


@router.get("/restaurant/tables")
def get_restaurant_tables(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists dining tables and seating capacity."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        return []
    tables = db.query(DiningTable).filter(DiningTable.restaurant_id == rest.id).order_by(DiningTable.table_number).all()
    return [
        {
            "id": t.id,
            "restaurant_id": t.restaurant_id,
            "table_number": t.table_number,
            "capacity": t.capacity,
            "zone": t.zone,
            "is_active": t.is_active
        }
        for t in tables
    ]


@router.post("/restaurant/tables", status_code=status.HTTP_201_CREATED)
def create_dining_table(
    req: DiningTableCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Creates a new dining table in the restaurant floor plan."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    table = DiningTable(
        restaurant_id=rest.id,
        table_number=req.table_number.strip(),
        capacity=req.capacity,
        zone=req.zone.strip(),
        is_active=req.is_active
    )
    db.add(table)
    db.commit()
    db.refresh(table)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="DINING_TABLE_CREATED",
        resource_type="DINING_TABLE",
        resource_id=str(table.id),
        details={"table_number": table.table_number, "capacity": table.capacity}
    ))
    db.commit()
    return {
        "id": table.id,
        "restaurant_id": table.restaurant_id,
        "table_number": table.table_number,
        "capacity": table.capacity,
        "zone": table.zone,
        "is_active": table.is_active
    }


@router.put("/restaurant/tables/{table_id}")
def update_dining_table(
    table_id: int,
    req: DiningTableUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates dining table capacity, zone or active status."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    table = db.query(DiningTable).filter(
        DiningTable.id == table_id,
        DiningTable.restaurant_id == rest.id
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found or unauthorized.")

    if req.table_number is not None:
        table.table_number = req.table_number.strip()
    if req.capacity is not None:
        table.capacity = req.capacity
    if req.zone is not None:
        table.zone = req.zone.strip()
    if req.is_active is not None:
        table.is_active = req.is_active

    db.commit()
    db.refresh(table)
    return {
        "id": table.id,
        "restaurant_id": table.restaurant_id,
        "table_number": table.table_number,
        "capacity": table.capacity,
        "zone": table.zone,
        "is_active": table.is_active
    }


@router.delete("/restaurant/tables/{table_id}")
def delete_dining_table(
    table_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Deletes a dining table from the restaurant."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    table = db.query(DiningTable).filter(
        DiningTable.id == table_id,
        DiningTable.restaurant_id == rest.id
    ).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found or unauthorized.")

    db.delete(table)
    db.commit()
    return {"success": True, "message": "Dining table deleted successfully."}


@router.get("/restaurant/reservations")
def get_restaurant_reservations(
    status_filter: Optional[str] = Query(None, alias="status"),
    date_filter: Optional[str] = Query(None, alias="date"),
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists table reservations with guest details and status."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        return []

    q = db.query(DiningReservation).filter(DiningReservation.restaurant_id == rest.id)
    if status_filter:
        q = q.filter(DiningReservation.status == status_filter.upper())
    if date_filter:
        try:
            d_val = datetime.datetime.strptime(date_filter, "%Y-%m-%d").date()
            q = q.filter(DiningReservation.reservation_date == d_val)
        except ValueError:
            pass

    reservations = q.order_by(DiningReservation.reservation_date.desc(), DiningReservation.reservation_time.desc()).all()

    return [
        {
            "id": r.id,
            "table_id": r.table_id,
            "table_number": r.table.table_number if r.table else "Unassigned",
            "table_zone": r.table.zone if r.table else "",
            "guest_count": r.guest_count,
            "customer_name": r.user.full_name if r.user else "Guest",
            "customer_phone": r.user.phone if r.user else "",
            "reservation_date": r.reservation_date.isoformat() if r.reservation_date else "",
            "reservation_time": r.reservation_time.strftime("%H:%M") if r.reservation_time else "",
            "duration_minutes": r.duration_minutes,
            "special_requests": r.special_requests,
            "status": r.status,
            "booking_reference": r.booking.booking_reference if r.booking else None
        }
        for r in reservations
    ]


@router.put("/restaurant/reservations/{reservation_id}/status")
def update_reservation_status(
    reservation_id: int,
    req: ReservationStatusUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates guest reservation status (CONFIRMED, SEATED, CANCELLED, NO_SHOW)."""
    _ensure_partner_type(current_partner, ["RESTAURANT"], "Restaurant Partners")
    rest = db.query(Restaurant).filter(Restaurant.partner_id == current_partner.id).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant profile not found.")

    res = db.query(DiningReservation).filter(
        DiningReservation.id == reservation_id,
        DiningReservation.restaurant_id == rest.id
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found or unauthorized.")

    new_status = req.status.upper()
    if new_status not in ["CONFIRMED", "SEATED", "CANCELLED", "NO_SHOW"]:
        raise HTTPException(status_code=400, detail="Invalid reservation status.")

    res.status = new_status
    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="RESERVATION_STATUS_UPDATED",
        resource_type="DINING_RESERVATION",
        resource_id=str(res.id),
        details={"new_status": new_status, "customer_id": res.user_id}
    ))
    db.commit()
    db.refresh(res)
    return {"success": True, "reservation_id": res.id, "status": res.status}


# ==============================================================================
# 7. VERTICAL: CINEMA MANAGEMENT
# ==============================================================================

@router.get("/cinema/profile")
def get_cinema_profile(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Returns cinema multiplex details."""
    if current_partner.partner_type != "CINEMA":
        raise HTTPException(status_code=403, detail="Endpoint exclusive to Cinema Partners.")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema establishment not found.")
    return {
        "id": cin.id,
        "name": cin.name,
        "address": cin.address,
        "city": cin.city,
        "amenities": cin.amenities or [],
        "is_active": cin.is_active
    }


@router.put("/cinema/profile")
def update_cinema_profile(
    req: CinemaProfileUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates cinema name, address, amenities and active status."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema establishment not found.")

    if req.name is not None and req.name.strip():
        cin.name = req.name.strip()
    if req.address is not None:
        cin.address = req.address
    if req.amenities is not None:
        cin.amenities = req.amenities
    if req.is_active is not None:
        cin.is_active = req.is_active

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="CINEMA_PROFILE_UPDATED",
        resource_type="CINEMA",
        resource_id=str(cin.id)
    ))
    db.commit()
    db.refresh(cin)
    return {
        "id": cin.id,
        "name": cin.name,
        "address": cin.address,
        "city": cin.city,
        "amenities": cin.amenities or [],
        "is_active": cin.is_active
    }


@router.get("/cinema/screens")
def get_cinema_screens(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists screens and their total seat configurations."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        return []
    screens = db.query(Screen).filter(Screen.cinema_id == cin.id).all()
    return [
        {
            "id": s.id,
            "cinema_id": s.cinema_id,
            "name": s.name,
            "screen_type": s.screen_type,
            "total_seats": s.total_seats
        }
        for s in screens
    ]


@router.post("/cinema/screens", status_code=status.HTTP_201_CREATED)
def create_cinema_screen(
    req: ScreenCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Adds a new screen with auto-generated seats according to row and column layout."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema establishment not found.")

    total_seats = req.rows * req.seats_per_row
    screen = Screen(
        cinema_id=cin.id,
        name=req.name.strip(),
        screen_type=req.screen_type.strip(),
        total_seats=total_seats
    )
    db.add(screen)
    db.commit()
    db.refresh(screen)

    # Generate seats
    row_letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"]
    seats_to_add = []
    for r_idx in range(min(req.rows, len(row_letters))):
        row_char = row_letters[r_idx]
        tier = "CLASSIC"
        if r_idx == 0:
            tier = "RECLINER"
        elif r_idx <= 2:
            tier = "PREMIUM"

        for s_idx in range(1, req.seats_per_row + 1):
            seats_to_add.append(Seat(
                screen_id=screen.id,
                row_code=row_char,
                seat_number=s_idx,
                tier=tier,
                base_price=Decimal(str(req.default_price)),
                is_accessible=(s_idx == 1 and r_idx == 0)
            ))

    db.add_all(seats_to_add)
    db.commit()

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="SCREEN_CREATED",
        resource_type="SCREEN",
        resource_id=str(screen.id),
        details={"name": screen.name, "total_seats": total_seats}
    ))
    db.commit()
    return {
        "id": screen.id,
        "cinema_id": screen.cinema_id,
        "name": screen.name,
        "screen_type": screen.screen_type,
        "total_seats": screen.total_seats
    }


@router.get("/cinema/screens/{screen_id}/seats")
def get_screen_seats(
    screen_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Returns seat configuration for a screen."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema not found.")
    screen = db.query(Screen).filter(Screen.id == screen_id, Screen.cinema_id == cin.id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found or unauthorized.")
    seats = db.query(Seat).filter(Seat.screen_id == screen_id).order_by(Seat.row_code, Seat.seat_number).all()
    return [
        {
            "id": s.id,
            "screen_id": s.screen_id,
            "row_code": s.row_code,
            "seat_number": s.seat_number,
            "tier": s.tier,
            "base_price": float(s.base_price),
            "is_accessible": s.is_accessible
        }
        for s in seats
    ]


@router.put("/cinema/screens/{screen_id}/seats/{seat_id}")
def update_seat(
    screen_id: int,
    seat_id: int,
    req: SeatUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates seat tier and base price."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema not found.")
    screen = db.query(Screen).filter(Screen.id == screen_id, Screen.cinema_id == cin.id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found or unauthorized.")

    seat = db.query(Seat).filter(Seat.id == seat_id, Seat.screen_id == screen.id).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found.")

    if req.tier is not None:
        seat.tier = req.tier.upper()
    if req.base_price is not None:
        seat.base_price = Decimal(str(req.base_price))
    if req.is_accessible is not None:
        seat.is_accessible = req.is_accessible

    db.commit()
    db.refresh(seat)
    return {
        "id": seat.id,
        "screen_id": seat.screen_id,
        "row_code": seat.row_code,
        "seat_number": seat.seat_number,
        "tier": seat.tier,
        "base_price": float(seat.base_price),
        "is_accessible": seat.is_accessible
    }


@router.get("/cinema/shows")
def get_cinema_shows(
    show_date: Optional[str] = Query(None),
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists scheduled movie shows across screens."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        return []
    screen_ids = [s.id for s in cin.screens]
    if not screen_ids:
        return []

    q = db.query(MovieShow).filter(MovieShow.screen_id.in_(screen_ids))
    if show_date:
        try:
            d_val = datetime.datetime.strptime(show_date, "%Y-%m-%d").date()
            q = q.filter(MovieShow.show_date == d_val)
        except ValueError:
            pass

    shows = q.order_by(MovieShow.show_date.desc(), MovieShow.start_time.asc()).all()

    return [
        {
            "id": s.id,
            "movie_id": s.movie_id,
            "movie_title": s.movie.title if s.movie else "Unknown Movie",
            "screen_id": s.screen_id,
            "screen_name": s.screen.name if s.screen else "Screen",
            "screen_type": s.screen.screen_type if s.screen else "2D",
            "show_date": s.show_date.isoformat(),
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "price_multiplier": float(s.price_multiplier),
            "status": s.status
        }
        for s in shows
    ]


@router.post("/cinema/shows", status_code=status.HTTP_201_CREATED)
def schedule_movie_show(
    req: MovieShowCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Schedules a new movie show on a screen."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema establishment not found.")

    screen = db.query(Screen).filter(Screen.id == req.screen_id, Screen.cinema_id == cin.id).first()
    if not screen:
        raise HTTPException(status_code=404, detail="Screen not found or belongs to another cinema.")

    movie = db.query(Movie).filter(Movie.id == req.movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    try:
        s_date = datetime.datetime.strptime(req.show_date, "%Y-%m-%d").date()
        s_time = datetime.datetime.strptime(req.start_time, "%H:%M" if len(req.start_time) == 5 else "%H:%M:%S").time()
        e_time = datetime.datetime.strptime(req.end_time, "%H:%M" if len(req.end_time) == 5 else "%H:%M:%S").time()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date or time format: {str(e)}")

    show = MovieShow(
        movie_id=movie.id,
        screen_id=screen.id,
        show_date=s_date,
        start_time=s_time,
        end_time=e_time,
        price_multiplier=Decimal(str(req.price_multiplier)),
        status="SCHEDULED"
    )
    db.add(show)
    db.commit()
    db.refresh(show)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="SHOW_SCHEDULED",
        resource_type="MOVIE_SHOW",
        resource_id=str(show.id),
        details={"movie": movie.title, "screen": screen.name, "date": str(s_date)}
    ))
    db.commit()
    return {
        "id": show.id,
        "movie_id": show.movie_id,
        "movie_title": movie.title,
        "screen_id": show.screen_id,
        "screen_name": screen.name,
        "show_date": show.show_date.isoformat(),
        "start_time": show.start_time.strftime("%H:%M"),
        "end_time": show.end_time.strftime("%H:%M"),
        "price_multiplier": float(show.price_multiplier),
        "status": show.status
    }


@router.put("/cinema/shows/{show_id}")
def update_movie_show(
    show_id: int,
    req: MovieShowUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates show status (SCHEDULED, HOUSEFULL, CANCELLED, COMPLETED) or price multiplier."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema not found.")

    screen_ids = [s.id for s in cin.screens]
    show = db.query(MovieShow).filter(MovieShow.id == show_id, MovieShow.screen_id.in_(screen_ids)).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found or unauthorized.")

    if req.status is not None:
        show.status = req.status.upper()
    if req.price_multiplier is not None:
        show.price_multiplier = Decimal(str(req.price_multiplier))

    db.commit()
    db.refresh(show)
    return {
        "id": show.id,
        "movie_id": show.movie_id,
        "screen_id": show.screen_id,
        "show_date": show.show_date.isoformat(),
        "start_time": show.start_time.strftime("%H:%M"),
        "end_time": show.end_time.strftime("%H:%M"),
        "price_multiplier": float(show.price_multiplier),
        "status": show.status
    }


@router.delete("/cinema/shows/{show_id}")
def cancel_movie_show(
    show_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Cancels/deletes a movie show."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    cin = db.query(Cinema).filter(Cinema.partner_id == current_partner.id).first()
    if not cin:
        raise HTTPException(status_code=404, detail="Cinema not found.")

    screen_ids = [s.id for s in cin.screens]
    show = db.query(MovieShow).filter(MovieShow.id == show_id, MovieShow.screen_id.in_(screen_ids)).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found or unauthorized.")

    db.delete(show)
    db.commit()
    return {"success": True, "message": "Show cancelled successfully."}


@router.get("/cinema/movies")
def get_available_movies(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Returns active movies available for cinema scheduling."""
    _ensure_partner_type(current_partner, ["CINEMA"], "Cinema Partners")
    return db.query(Movie).filter(Movie.is_active == True).order_by(Movie.title).all()


# ==============================================================================
# 8. VERTICAL: EVENTS MANAGEMENT
# ==============================================================================

@router.get("/events")
def get_partner_events(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists events organized by the authenticated event partner."""
    if current_partner.partner_type != "EVENT":
        raise HTTPException(status_code=403, detail="Endpoint exclusive to Event Organizers.")
    events = db.query(Event).filter(Event.partner_id == current_partner.id).order_by(Event.start_datetime.desc()).all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "slug": e.slug,
            "category": e.category,
            "venue_name": e.venue_name,
            "venue_address": e.venue_address,
            "start_datetime": e.start_datetime.isoformat(),
            "end_datetime": e.end_datetime.isoformat(),
            "banner_url": e.banner_url,
            "artist_names": e.artist_names,
            "is_featured": e.is_featured,
            "is_active": e.is_active
        }
        for e in events
    ]


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(
    req: EventCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Creates a new live event or concert."""
    if current_partner.partner_type != "EVENT":
        raise HTTPException(status_code=403, detail="Endpoint exclusive to Event Organizers.")

    loc_id = req.location_id
    if not loc_id:
        loc = db.query(Location).filter(Location.slug == "hyderabad").first()
        loc_id = loc.id if loc else 1

    try:
        s_dt = datetime.datetime.fromisoformat(req.start_datetime.replace("Z", "+00:00"))
        e_dt = datetime.datetime.fromisoformat(req.end_datetime.replace("Z", "+00:00"))
    except Exception:
        s_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        e_dt = s_dt + datetime.timedelta(hours=4)

    slug = _generate_slug(req.title)

    event = Event(
        partner_id=current_partner.id,
        location_id=loc_id,
        title=req.title.strip(),
        slug=slug,
        category=req.category.upper(),
        description=req.description,
        artist_names=req.artist_names,
        venue_name=req.venue_name.strip(),
        venue_address=req.venue_address.strip(),
        start_datetime=s_dt,
        end_datetime=e_dt,
        banner_url=req.banner_url,
        is_featured=req.is_featured,
        is_active=True
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="EVENT_CREATED",
        resource_type="EVENT",
        resource_id=str(event.id),
        details={"title": event.title, "venue": event.venue_name}
    ))
    db.commit()
    return {
        "id": event.id,
        "title": event.title,
        "slug": event.slug,
        "category": event.category,
        "venue_name": event.venue_name,
        "venue_address": event.venue_address,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat(),
        "banner_url": event.banner_url,
        "artist_names": event.artist_names,
        "is_featured": event.is_featured,
        "is_active": event.is_active
    }


@router.get("/events/{event_id}")
def get_event_detail(
    event_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Returns event details with ticket categories and capacity stats."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    event = db.query(Event).filter(Event.id == event_id, Event.partner_id == current_partner.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found or unauthorized.")

    return {
        "id": event.id,
        "title": event.title,
        "slug": event.slug,
        "category": event.category,
        "description": event.description,
        "artist_names": event.artist_names,
        "venue_name": event.venue_name,
        "venue_address": event.venue_address,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat(),
        "banner_url": event.banner_url,
        "is_featured": event.is_featured,
        "is_active": event.is_active,
        "ticket_types": [
            {
                "id": tt.id,
                "name": tt.name,
                "description": tt.description,
                "price": float(tt.price),
                "total_quantity": tt.total_quantity,
                "available_quantity": tt.available_quantity,
                "sold_quantity": tt.total_quantity - tt.available_quantity,
                "max_per_booking": tt.max_per_booking
            }
            for tt in event.ticket_types
        ]
    }


@router.put("/events/{event_id}")
def update_event(
    event_id: int,
    req: EventUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates event information and schedule."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    event = db.query(Event).filter(Event.id == event_id, Event.partner_id == current_partner.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found or unauthorized.")

    if req.title is not None and req.title.strip():
        event.title = req.title.strip()
    if req.category is not None:
        event.category = req.category.upper()
    if req.venue_name is not None:
        event.venue_name = req.venue_name.strip()
    if req.venue_address is not None:
        event.venue_address = req.venue_address.strip()
    if req.description is not None:
        event.description = req.description
    if req.artist_names is not None:
        event.artist_names = req.artist_names
    if req.banner_url is not None:
        event.banner_url = req.banner_url
    if req.is_featured is not None:
        event.is_featured = req.is_featured
    if req.is_active is not None:
        event.is_active = req.is_active

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="EVENT_UPDATED",
        resource_type="EVENT",
        resource_id=str(event.id)
    ))
    db.commit()
    db.refresh(event)
    return {
        "id": event.id,
        "title": event.title,
        "slug": event.slug,
        "category": event.category,
        "venue_name": event.venue_name,
        "venue_address": event.venue_address,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat(),
        "banner_url": event.banner_url,
        "artist_names": event.artist_names,
        "is_featured": event.is_featured,
        "is_active": event.is_active
    }


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Cancels and deactivates an event."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    event = db.query(Event).filter(Event.id == event_id, Event.partner_id == current_partner.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found or unauthorized.")

    event.is_active = False
    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="EVENT_DEACTIVATED",
        resource_type="EVENT",
        resource_id=str(event.id)
    ))
    db.commit()
    return {"success": True, "message": "Event deactivated successfully."}


@router.post("/events/{event_id}/tickets", status_code=status.HTTP_201_CREATED)
def create_event_ticket_type(
    event_id: int,
    req: EventTicketTypeCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Adds a ticket tier (Early Bird, VIP, General) to an event."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    event = db.query(Event).filter(Event.id == event_id, Event.partner_id == current_partner.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found or unauthorized.")

    tt = EventTicketType(
        event_id=event.id,
        name=req.name.strip(),
        description=req.description,
        price=Decimal(str(req.price)),
        total_quantity=req.total_quantity,
        available_quantity=req.total_quantity,
        max_per_booking=req.max_per_booking
    )
    db.add(tt)
    db.commit()
    db.refresh(tt)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="TICKET_TIER_CREATED",
        resource_type="EVENT_TICKET_TYPE",
        resource_id=str(tt.id),
        details={"name": tt.name, "price": str(tt.price), "quantity": tt.total_quantity}
    ))
    db.commit()
    return {
        "id": tt.id,
        "event_id": tt.event_id,
        "name": tt.name,
        "description": tt.description,
        "price": float(tt.price),
        "total_quantity": tt.total_quantity,
        "available_quantity": tt.available_quantity,
        "max_per_booking": tt.max_per_booking
    }


@router.put("/events/tickets/{ticket_id}")
def update_event_ticket_type(
    ticket_id: int,
    req: EventTicketTypeUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates ticket tier pricing and inventory allocation."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    tt = db.query(EventTicketType).join(Event).filter(
        EventTicketType.id == ticket_id,
        Event.partner_id == current_partner.id
    ).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Ticket type not found or unauthorized.")

    if req.name is not None:
        tt.name = req.name.strip()
    if req.description is not None:
        tt.description = req.description
    if req.price is not None:
        tt.price = Decimal(str(req.price))
    if req.total_quantity is not None:
        diff = req.total_quantity - tt.total_quantity
        tt.total_quantity = req.total_quantity
        tt.available_quantity = max(0, tt.available_quantity + diff)
    if req.available_quantity is not None:
        tt.available_quantity = min(req.available_quantity, tt.total_quantity)
    if req.max_per_booking is not None:
        tt.max_per_booking = req.max_per_booking

    db.commit()
    db.refresh(tt)
    return {
        "id": tt.id,
        "event_id": tt.event_id,
        "name": tt.name,
        "description": tt.description,
        "price": float(tt.price),
        "total_quantity": tt.total_quantity,
        "available_quantity": tt.available_quantity,
        "max_per_booking": tt.max_per_booking
    }


@router.delete("/events/tickets/{ticket_id}")
def delete_event_ticket_type(
    ticket_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Deletes a ticket tier from an event."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    tt = db.query(EventTicketType).join(Event).filter(
        EventTicketType.id == ticket_id,
        Event.partner_id == current_partner.id
    ).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Ticket type not found or unauthorized.")

    db.delete(tt)
    db.commit()
    return {"success": True, "message": "Ticket category deleted."}


@router.get("/events/{event_id}/attendees")
def get_event_attendees(
    event_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists attendees with ticket details and admission status."""
    _ensure_partner_type(current_partner, ["EVENT"], "Event Organizers")
    event = db.query(Event).filter(Event.id == event_id, Event.partner_id == current_partner.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found or unauthorized.")

    ticket_ids = [tt.id for tt in event.ticket_types]
    if not ticket_ids:
        return []

    items = db.query(BookingItem).join(Booking).filter(
        BookingItem.item_type == "TICKET",
        BookingItem.item_id.in_(ticket_ids),
        Booking.status == "CONFIRMED"
    ).all()

    attendees = []
    for item in items:
        attendees.append({
            "booking_reference": item.booking.booking_reference,
            "attendee_name": item.booking.user.full_name if item.booking.user else "Attendee",
            "attendee_phone": item.booking.user.phone if item.booking.user else "",
            "attendee_email": item.booking.user.email if item.booking.user else "",
            "ticket_type": item.name,
            "quantity": item.quantity,
            "booked_at": item.booking.created_at.strftime("%Y-%m-%d %H:%M") if item.booking.created_at else "",
            "qr_token": item.booking.qr_code_token
        })
    return attendees


# ==============================================================================
# 9. VERTICAL: SPORTS & ACTIVITIES MANAGEMENT
# ==============================================================================

@router.get("/sports/venues")
def get_sports_venues(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists sports arenas and turfs owned by this partner."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    venues = db.query(SportsVenue).filter(SportsVenue.partner_id == current_partner.id).all()
    return [
        {
            "id": v.id,
            "name": v.name,
            "sport_types": v.sport_types or [],
            "address": v.address,
            "amenities": v.amenities or [],
            "images": v.images or [],
            "rating": v.rating,
            "is_active": v.is_active
        }
        for v in venues
    ]


@router.post("/sports/venues", status_code=status.HTTP_201_CREATED)
def create_sports_venue(
    req: SportsVenueCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Creates a new sports arena or turf complex."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    loc_id = req.location_id
    if not loc_id:
        loc = db.query(Location).filter(Location.slug == "hyderabad").first()
        loc_id = loc.id if loc else 1

    venue = SportsVenue(
        partner_id=current_partner.id,
        location_id=loc_id,
        name=req.name.strip(),
        sport_types=req.sport_types,
        address=req.address.strip(),
        amenities=req.amenities,
        images=req.images,
        rating=4.5,
        is_active=True
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="SPORTS_VENUE_CREATED",
        resource_type="SPORTS_VENUE",
        resource_id=str(venue.id),
        details={"name": venue.name, "sport_types": venue.sport_types}
    ))
    db.commit()
    return {
        "id": venue.id,
        "name": venue.name,
        "sport_types": venue.sport_types,
        "address": venue.address,
        "amenities": venue.amenities,
        "images": venue.images,
        "is_active": venue.is_active
    }


@router.put("/sports/venues/{venue_id}")
def update_sports_venue(
    venue_id: int,
    req: SportsVenueUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates sports facility details and amenities."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    venue = db.query(SportsVenue).filter(SportsVenue.id == venue_id, SportsVenue.partner_id == current_partner.id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="Sports venue not found or unauthorized.")

    if req.name is not None and req.name.strip():
        venue.name = req.name.strip()
    if req.sport_types is not None:
        venue.sport_types = req.sport_types
    if req.address is not None:
        venue.address = req.address.strip()
    if req.amenities is not None:
        venue.amenities = req.amenities
    if req.images is not None:
        venue.images = req.images
    if req.is_active is not None:
        venue.is_active = req.is_active

    db.commit()
    db.refresh(venue)
    return {
        "id": venue.id,
        "name": venue.name,
        "sport_types": venue.sport_types,
        "address": venue.address,
        "amenities": venue.amenities,
        "images": venue.images,
        "is_active": venue.is_active
    }


@router.get("/activities")
def get_partner_activities(
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists activities and sport court listings."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    venue_ids = [v.id for v in current_partner.sports_venues]
    acts = db.query(Activity).filter(
        (Activity.partner_id == current_partner.id) | 
        (Activity.venue_id.in_(venue_ids) if venue_ids else False)
    ).all()
    return [
        {
            "id": a.id,
            "venue_id": a.venue_id,
            "title": a.title,
            "slug": a.slug,
            "category": a.category,
            "base_price": float(a.base_price),
            "duration_minutes": a.duration_minutes,
            "min_age": a.min_age,
            "description": a.description,
            "image_url": a.image_url,
            "is_active": a.is_active
        }
        for a in acts
    ]


@router.post("/activities", status_code=status.HTTP_201_CREATED)
def create_activity(
    req: ActivityCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Creates a new activity or turf court listing."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    if req.venue_id is not None:
        venue = db.query(SportsVenue).filter(SportsVenue.id == req.venue_id).first()
        if not venue:
            raise HTTPException(status_code=404, detail="Sports venue not found.")
        if venue.partner_id != current_partner.id:
            raise HTTPException(status_code=403, detail="Unauthorized: Sports venue belongs to another partner.")

    loc_id = req.location_id
    if not loc_id:
        loc = db.query(Location).filter(Location.slug == "hyderabad").first()
        loc_id = loc.id if loc else 1

    slug = _generate_slug(req.title)

    act = Activity(
        partner_id=current_partner.id,
        location_id=loc_id,
        venue_id=req.venue_id,
        title=req.title.strip(),
        slug=slug,
        category=req.category.upper(),
        description=req.description,
        base_price=Decimal(str(req.base_price)),
        duration_minutes=req.duration_minutes,
        image_url=req.image_url,
        min_age=req.min_age,
        is_active=True
    )
    db.add(act)
    db.commit()
    db.refresh(act)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="ACTIVITY_CREATED",
        resource_type="ACTIVITY",
        resource_id=str(act.id),
        details={"title": act.title, "base_price": str(act.base_price)}
    ))
    db.commit()
    return {
        "id": act.id,
        "venue_id": act.venue_id,
        "title": act.title,
        "slug": act.slug,
        "category": act.category,
        "base_price": float(act.base_price),
        "duration_minutes": act.duration_minutes,
        "min_age": act.min_age,
        "description": act.description,
        "image_url": act.image_url,
        "is_active": act.is_active
    }


@router.put("/activities/{activity_id}")
def update_activity(
    activity_id: int,
    req: ActivityUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates activity details, duration, pricing or active status."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    act = db.query(Activity).filter(Activity.id == activity_id, Activity.partner_id == current_partner.id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found or unauthorized.")

    if req.title is not None and req.title.strip():
        act.title = req.title.strip()
    if req.category is not None:
        act.category = req.category.upper()
    if req.base_price is not None:
        act.base_price = Decimal(str(req.base_price))
    if req.duration_minutes is not None:
        act.duration_minutes = req.duration_minutes
    if req.min_age is not None:
        act.min_age = req.min_age
    if req.description is not None:
        act.description = req.description
    if req.image_url is not None:
        act.image_url = req.image_url
    if req.is_active is not None:
        act.is_active = req.is_active

    db.commit()
    db.refresh(act)
    return {
        "id": act.id,
        "venue_id": act.venue_id,
        "title": act.title,
        "slug": act.slug,
        "category": act.category,
        "base_price": float(act.base_price),
        "duration_minutes": act.duration_minutes,
        "min_age": act.min_age,
        "description": act.description,
        "image_url": act.image_url,
        "is_active": act.is_active
    }


@router.delete("/activities/{activity_id}")
def delete_activity(
    activity_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Deactivates an activity listing."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    act = db.query(Activity).filter(Activity.id == activity_id, Activity.partner_id == current_partner.id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found or unauthorized.")

    act.is_active = False
    db.commit()
    return {"success": True, "message": "Activity listing deactivated."}


@router.get("/activities/{activity_id}/slots")
def get_activity_slots(
    activity_id: int,
    slot_date: Optional[str] = Query(None),
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Lists time slots and booked count for an activity."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    act = db.query(Activity).filter(Activity.id == activity_id, Activity.partner_id == current_partner.id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found or unauthorized.")

    q = db.query(ActivitySlot).filter(ActivitySlot.activity_id == act.id)
    if slot_date:
        try:
            d_val = datetime.datetime.strptime(slot_date, "%Y-%m-%d").date()
            q = q.filter(ActivitySlot.slot_date == d_val)
        except ValueError:
            pass

    slots = q.order_by(ActivitySlot.slot_date.desc(), ActivitySlot.start_time.asc()).all()

    return [
        {
            "id": s.id,
            "activity_id": s.activity_id,
            "slot_date": s.slot_date.isoformat(),
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "capacity": s.capacity,
            "booked_count": s.booked_count,
            "available_count": max(0, s.capacity - s.booked_count),
            "price_override": float(s.price_override) if s.price_override is not None else None,
            "effective_price": float(s.price_override if s.price_override is not None else act.base_price),
            "is_available": s.is_available
        }
        for s in slots
    ]


@router.post("/activities/{activity_id}/slots", status_code=status.HTTP_201_CREATED)
def create_activity_slot(
    activity_id: int,
    req: ActivitySlotCreate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Creates a new time slot for an activity."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    act = db.query(Activity).filter(Activity.id == activity_id, Activity.partner_id == current_partner.id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found or unauthorized.")

    try:
        s_date = datetime.datetime.strptime(req.slot_date, "%Y-%m-%d").date()
        s_time = datetime.datetime.strptime(req.start_time, "%H:%M" if len(req.start_time) == 5 else "%H:%M:%S").time()
        e_time = datetime.datetime.strptime(req.end_time, "%H:%M" if len(req.end_time) == 5 else "%H:%M:%S").time()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time format: {str(e)}")

    slot = ActivitySlot(
        activity_id=act.id,
        slot_date=s_date,
        start_time=s_time,
        end_time=e_time,
        capacity=req.capacity,
        booked_count=0,
        price_override=Decimal(str(req.price_override)) if req.price_override is not None else None,
        is_available=req.is_available
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    db.add(AuditLog(
        user_id=current_partner.user_id,
        action="ACTIVITY_SLOT_CREATED",
        resource_type="ACTIVITY_SLOT",
        resource_id=str(slot.id),
        details={"activity": act.title, "date": str(s_date), "start_time": str(s_time)}
    ))
    db.commit()
    return {
        "id": slot.id,
        "activity_id": slot.activity_id,
        "slot_date": slot.slot_date.isoformat(),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "capacity": slot.capacity,
        "booked_count": slot.booked_count,
        "price_override": float(slot.price_override) if slot.price_override is not None else None,
        "is_available": slot.is_available
    }


@router.put("/activities/slots/{slot_id}")
def update_activity_slot(
    slot_id: int,
    req: ActivitySlotUpdate,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Updates slot capacity, availability or price override."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    slot = db.query(ActivitySlot).join(Activity).filter(
        ActivitySlot.id == slot_id,
        Activity.partner_id == current_partner.id
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found or unauthorized.")

    if req.capacity is not None:
        if req.capacity < slot.booked_count:
            raise HTTPException(status_code=400, detail="Capacity cannot be less than already booked count.")
        slot.capacity = req.capacity
    if req.price_override is not None:
        slot.price_override = Decimal(str(req.price_override))
    if req.is_available is not None:
        slot.is_available = req.is_available

    db.commit()
    db.refresh(slot)
    return {
        "id": slot.id,
        "activity_id": slot.activity_id,
        "slot_date": slot.slot_date.isoformat(),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "capacity": slot.capacity,
        "booked_count": slot.booked_count,
        "price_override": float(slot.price_override) if slot.price_override is not None else None,
        "is_available": slot.is_available
    }


@router.delete("/activities/slots/{slot_id}")
def delete_activity_slot(
    slot_id: int,
    current_partner: Partner = Depends(get_current_approved_partner),
    db: Session = Depends(get_db)
):
    """Deletes an activity slot if no bookings have been made."""
    _ensure_partner_type(current_partner, ["SPORTS", "ACTIVITIES"], "Sports & Activity Partners")
    slot = db.query(ActivitySlot).join(Activity).filter(
        ActivitySlot.id == slot_id,
        Activity.partner_id == current_partner.id
    ).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found or unauthorized.")

    if slot.booked_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete slot with active bookings. Set is_available=False instead.")

    db.delete(slot)
    db.commit()
    return {"success": True, "message": "Activity slot deleted successfully."}
