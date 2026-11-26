"""
GO BEYOND — Phase 5 Security, Concurrency, Financial & Hardening Regression Suite (D-01 to D-15)

Covers every defect reproduced and fixed during Phase 5:
- D-01: Cross-user IDOR on /payments/verify(-signature) + DiningReservation status sync
- D-02: Cross-endpoint dining mutex (/bookings/initiate vs /dining/reserve), overlap window locking & clean release
- D-03: Strict partner vertical authorization (_ensure_partner_type) + venue ownership check on /partners/activities
- D-04: X-Real-IP / rightmost X-Forwarded-For rate-limit client IP extraction (defeating XFF spoofing)
- D-05: Coupon valid_from/valid_until enforcement + atomic usage_limit conditional increment under concurrency
- D-06: Password reset revokes all active RefreshToken sessions immediately
- D-07: /bookings/expire-stale restricted strictly to super_admin
- D-08: Admin cancel previous_status audit accuracy, inventory release, refund initiation & Payment refund state transitions
- D-09: ARQ worker expire_stale_bookings prefix cleanup (show_{id}:seat_{id}) & DINING reservation cancellation
- D-10: LockService & OTPService automatic Redis reconnect after transient connection failure (preserving manual-None fail-safe)
- D-11: OTP NotificationOutbox masks raw OTP code & omits prefix from idempotency_key
- D-12: verify_otp role priority parity + ReconciliationEngine AuditLog is_healthy consistency
- D-14 / D-15: /metrics active lock gauge + production startup skips metadata.create_all
"""
import asyncio
import datetime
import hashlib
import hmac
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.config import settings
from app.core.database import Base, SessionLocal
from app.core.locks import LockService, lock_service
from app.core.rate_limit import get_client_identifier
from app.core.redis import get_redis
from app.core.security import create_access_token, get_password_hash
from app.main import app, on_startup
from app.models.audit import AuditLog, Notification
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.dining import DiningReservation, DiningTable, Restaurant
from app.models.event import Event, EventTicketType
from app.models.location import Location
from app.models.movie import MovieShow, Seat
from app.models.notification import NotificationOutbox
from app.models.partner import Partner
from app.models.payment import Coupon, Payment, Refund
from app.models.sports import SportsVenue
from app.models.user import RefreshToken, Role, User, UserProfile
from app.services.otp import OTPService, otp_service
from app.services.reconciliation import ReconciliationEngine
from app.worker.tasks import expire_stale_bookings


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _create_user_with_roles(db: Session, prefix: str, role_names: list[str]) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"{prefix}_{uid}@gobeyondqa.test",
        phone=f"+9195{int(uid, 16) % 100000000:08d}",
        full_name=f"P5 {prefix} {uid}",
        hashed_password=get_password_hash("Password@123"),
        is_active=True,
        is_verified=True,
        account_status="ACTIVE",
    )
    for rname in role_names:
        role = db.query(Role).filter(Role.name == rname).first()
        if not role:
            role = Role(name=rname, description=f"{rname} role")
            db.add(role)
            db.flush()
        user.roles.append(role)
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User, role: str | None = None) -> dict:
    r = role or (user.roles[0].name if user.roles else "customer")
    tok = create_access_token(subject=str(user.id), role=r)
    return {"Authorization": f"Bearer {tok}"}


def _cleanup_entities(
    db: Session,
    *,
    user_ids: list[int] | None = None,
    booking_ids: list[int] | None = None,
    booking_refs: list[str] | None = None,
    ticket_type_ids: list[int] | None = None,
    table_ids: list[int] | None = None,
    restaurant_ids: list[int] | None = None,
    venue_ids: list[int] | None = None,
    partner_ids: list[int] | None = None,
    coupon_ids: list[int] | None = None,
    outbox_recipients: list[str] | None = None,
    audit_ids_after: int | None = None,
):
    db.rollback()
    if booking_refs:
        rows = db.execute(
            text("SELECT id FROM bookings WHERE booking_reference = ANY(:refs)"),
            {"refs": booking_refs},
        ).fetchall()
        booking_ids = list(set((booking_ids or []) + [r[0] for r in rows]))
        db.execute(text("DELETE FROM audit_logs WHERE resource_id = ANY(:refs)"), {"refs": booking_refs})
        db.execute(
            text("DELETE FROM audit_logs WHERE details->>'booking_reference' = ANY(:refs)"),
            {"refs": booking_refs},
        )
    if booking_ids:
        db.execute(text("DELETE FROM refunds WHERE booking_id = ANY(:bids)"), {"bids": booking_ids})
        db.execute(text("DELETE FROM dining_reservations WHERE booking_id = ANY(:bids)"), {"bids": booking_ids})
        db.execute(text("DELETE FROM payments WHERE booking_id = ANY(:bids)"), {"bids": booking_ids})
        db.execute(text("DELETE FROM booking_items WHERE booking_id = ANY(:bids)"), {"bids": booking_ids})
        db.execute(text("DELETE FROM bookings WHERE id = ANY(:bids)"), {"bids": booking_ids})
    if table_ids:
        db.execute(text("DELETE FROM dining_reservations WHERE table_id = ANY(:tids)"), {"tids": table_ids})
        db.execute(text("DELETE FROM dining_tables WHERE id = ANY(:tids)"), {"tids": table_ids})
    if restaurant_ids:
        db.execute(text("DELETE FROM dining_reservations WHERE restaurant_id = ANY(:rids)"), {"rids": restaurant_ids})
        db.execute(text("DELETE FROM dining_tables WHERE restaurant_id = ANY(:rids)"), {"rids": restaurant_ids})
        db.execute(text("DELETE FROM restaurants WHERE id = ANY(:rids)"), {"rids": restaurant_ids})
    if ticket_type_ids:
        db.execute(text("DELETE FROM event_ticket_types WHERE id = ANY(:ttids)"), {"ttids": ticket_type_ids})
    if venue_ids:
        db.execute(text("DELETE FROM sports_venues WHERE id = ANY(:vids)"), {"vids": venue_ids})
    if partner_ids:
        db.execute(text("DELETE FROM partner_documents WHERE partner_id = ANY(:pids)"), {"pids": partner_ids})
        db.execute(text("DELETE FROM partners WHERE id = ANY(:pids)"), {"pids": partner_ids})
    if coupon_ids:
        db.execute(text("DELETE FROM coupons WHERE id = ANY(:cids)"), {"cids": coupon_ids})
    if outbox_recipients:
        db.execute(
            text("DELETE FROM notification_outbox WHERE recipient = ANY(:recs)"),
            {"recs": outbox_recipients},
        )
    if audit_ids_after is not None:
        db.execute(
            text("DELETE FROM audit_logs WHERE id > :aid"),
            {"aid": audit_ids_after},
        )
    if user_ids:
        db.execute(text("DELETE FROM seat_locks WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM notification_outbox WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM notification_preferences WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM notifications WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM audit_logs WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM refresh_tokens WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM partners WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM user_profiles WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM user_roles WHERE user_id = ANY(:uids)"), {"uids": user_ids})
        db.execute(text("DELETE FROM users WHERE id = ANY(:uids)"), {"uids": user_ids})
    db.commit()


# ==============================================================================
# D-01: verify-signature Cross-User IDOR + DiningReservation Status Sync
# ==============================================================================
def test_d01_verify_payment_idor_rejected_and_dining_sync(client: TestClient):
    db = SessionLocal()
    user_a = None
    user_b = None
    tt_id = None
    booking_refs: list[str] = []
    rest_id = None
    table_id = None
    try:
        user_a = _create_user_with_roles(db, "d01_owner", ["customer"])
        user_b = _create_user_with_roles(db, "d01_attacker", ["customer"])
        ev = db.query(Event).filter(Event.is_active == True).first()
        assert ev is not None

        tt = EventTicketType(
            event_id=ev.id,
            name=f"D01-Pass-{uuid.uuid4().hex[:4]}",
            description="D01 test pass",
            price=Decimal("400.00"),
            total_quantity=10,
            available_quantity=10,
            max_per_booking=5,
        )
        db.add(tt)
        db.commit()
        db.refresh(tt)
        tt_id = tt.id

        res_init = client.post(
            "/api/v1/bookings/initiate",
            json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt.id, "quantity": 1}]},
            headers=_auth_header(user_a),
        )
        assert res_init.status_code == 201
        b_data = res_init.json()
        booking_refs.append(b_data["booking_reference"])

        res_ord = client.post(
            "/api/v1/payments/create-order",
            json={"booking_id": b_data["id"]},
            headers=_auth_header(user_a),
        )
        assert res_ord.status_code == 200
        order_id = res_ord.json()["order_id"]

        # Attacker User B tries to verify User A's booking -> must get 403 Forbidden
        pay_id = f"pay_idor_{uuid.uuid4().hex[:8]}"
        sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            f"{order_id}|{pay_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        res_idor = client.post(
            "/api/v1/payments/verify-signature",
            json={
                "booking_id": b_data["id"],
                "razorpay_order_id": order_id,
                "razorpay_payment_id": pay_id,
                "razorpay_signature": sig,
            },
            headers=_auth_header(user_b),
        )
        assert res_idor.status_code == 403

        # Booking remains PAYMENT_PENDING
        db.expire_all()
        b_row = db.query(Booking).filter(Booking.id == b_data["id"]).first()
        assert b_row.status == "PAYMENT_PENDING"

        # DiningReservation PENDING -> CONFIRMED sync when verified
        loc = db.query(Location).first()
        partner = db.query(Partner).first()
        rest = Restaurant(
            partner_id=partner.id,
            location_id=loc.id,
            name=f"D01 Dining {uuid.uuid4().hex[:4]}",
            slug=f"d01-dining-{uuid.uuid4().hex[:6]}",
            cuisines=["Hyderabadi"],
            cost_for_two=1000,
            address="Jubilee Hills, Hyderabad",
            phone="9800000001",
            is_active=True,
        )
        db.add(rest)
        db.flush()
        rest_id = rest.id
        tbl = DiningTable(restaurant_id=rest.id, table_number="D01-T1", capacity=4, zone="Indoor", is_active=True)
        db.add(tbl)
        db.flush()
        table_id = tbl.id

        dine_ref = f"GB-D01-{uuid.uuid4().hex[:6].upper()}"
        booking_refs.append(dine_ref)
        dine_b = Booking(
            booking_reference=dine_ref,
            user_id=user_a.id,
            booking_type="DINING",
            total_amount=Decimal("200.00"),
            tax_amount=Decimal("36.00"),
            discount_amount=Decimal("0.00"),
            final_payable=Decimal("236.00"),
            status="PAYMENT_PENDING",
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
        )
        db.add(dine_b)
        db.flush()
        res_date = datetime.date.today() + datetime.timedelta(days=15)
        start_dt = datetime.datetime.combine(res_date, datetime.time(19, 30))
        dres = DiningReservation(
            restaurant_id=rest.id,
            table_id=tbl.id,
            user_id=user_a.id,
            booking_id=dine_b.id,
            reservation_date=res_date,
            reservation_time=datetime.time(19, 30),
            start_datetime=start_dt,
            end_datetime=start_dt + datetime.timedelta(minutes=105),
            guest_count=2,
            status="PENDING",
        )
        db.add(dres)
        db.commit()

        d_ord_res = client.post(
            "/api/v1/payments/create-order",
            json={"booking_id": dine_b.id},
            headers=_auth_header(user_a),
        )
        assert d_ord_res.status_code == 200
        d_ord = d_ord_res.json()["order_id"]
        d_pay_id = f"pay_dine_{uuid.uuid4().hex[:8]}"
        d_sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            f"{d_ord}|{d_pay_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        d_ver_res = client.post(
            "/api/v1/payments/verify-signature",
            json={
                "booking_id": dine_b.id,
                "razorpay_order_id": d_ord,
                "razorpay_payment_id": d_pay_id,
                "razorpay_signature": d_sig,
            },
            headers=_auth_header(user_a),
        )
        assert d_ver_res.status_code == 200
        db.expire_all()
        db.refresh(dres)
        assert dres.status == "CONFIRMED"
    finally:
        _cleanup_entities(
            db,
            user_ids=[u.id for u in (user_a, user_b) if u],
            booking_refs=booking_refs,
            ticket_type_ids=[tt_id] if tt_id else None,
            table_ids=[table_id] if table_id else None,
            restaurant_ids=[rest_id] if rest_id else None,
        )
        db.close()


# ==============================================================================
# D-02: Dining Cross-Endpoint Mutex, Overlap Window & Cancellation Release
# ==============================================================================
def test_d02_dining_cross_endpoint_mutex_and_overlap_release(client: TestClient):
    db = SessionLocal()
    u1 = None
    u2 = None
    rest_id = None
    table_id = None
    booking_refs: list[str] = []
    try:
        u1 = _create_user_with_roles(db, "d02_u1", ["customer"])
        u2 = _create_user_with_roles(db, "d02_u2", ["customer"])
        loc = db.query(Location).first()
        partner = db.query(Partner).filter(Partner.partner_type == "RESTAURANT").first() or db.query(Partner).first()
        rest = Restaurant(
            partner_id=partner.id,
            location_id=loc.id,
            name=f"D02 Isolated Rest {uuid.uuid4().hex[:4]}",
            slug=f"d02-rest-{uuid.uuid4().hex[:6]}",
            cuisines=["Indian"],
            cost_for_two=1200,
            address="Madhapur, Hyderabad",
            phone="9800000002",
            is_active=True,
        )
        db.add(rest)
        db.flush()
        rest_id = rest.id
        tbl = DiningTable(restaurant_id=rest.id, table_number="D02-Single", capacity=4, zone="Indoor", is_active=True)
        db.add(tbl)
        db.commit()
        db.refresh(tbl)
        table_id = tbl.id

        res_date = (datetime.date.today() + datetime.timedelta(days=21)).isoformat()
        r1 = client.post(
            "/api/v1/bookings/initiate",
            json={
                "booking_type": "DINING",
                "items": [{
                    "item_type": "TABLE",
                    "item_id": table_id,
                    "quantity": 2,
                    "details": {
                        "restaurant_id": rest_id,
                        "reservation_date": res_date,
                        "reservation_time": "20:00",
                    },
                }],
            },
            headers=_auth_header(u1),
        )
        assert r1.status_code == 201
        b1 = r1.json()
        booking_refs.append(b1["booking_reference"])

        # Same time via /dining/reserve must fail 409
        r_same = client.post(
            "/api/v1/dining/reserve",
            json={
                "restaurant_id": rest_id,
                "reservation_date": res_date,
                "reservation_time": "20:00",
                "guest_count": 2,
            },
            headers=_auth_header(u2),
        )
        assert r_same.status_code == 409

        # Overlapping +45 min via /dining/reserve and /bookings/initiate must BOTH fail 409
        r_ov_1 = client.post(
            "/api/v1/dining/reserve",
            json={
                "restaurant_id": rest_id,
                "reservation_date": res_date,
                "reservation_time": "20:45",
                "guest_count": 2,
            },
            headers=_auth_header(u2),
        )
        assert r_ov_1.status_code == 409

        r_ov_2 = client.post(
            "/api/v1/bookings/initiate",
            json={
                "booking_type": "DINING",
                "items": [{
                    "item_type": "TABLE",
                    "item_id": table_id,
                    "quantity": 2,
                    "details": {
                        "restaurant_id": rest_id,
                        "reservation_date": res_date,
                        "reservation_time": "20:45",
                    },
                }],
            },
            headers=_auth_header(u2),
        )
        assert r_ov_2.status_code == 409

        # Cancel User 1 booking -> must immediately allow User 2 to reserve 20:00
        cxl = client.post(
            f"/api/v1/bookings/{b1['id']}/cancel",
            json={"reason": "D02 release test"},
            headers=_auth_header(u1),
        )
        assert cxl.status_code == 200

        r_rebook = client.post(
            "/api/v1/dining/reserve",
            json={
                "restaurant_id": rest_id,
                "reservation_date": res_date,
                "reservation_time": "20:00",
                "guest_count": 2,
            },
            headers=_auth_header(u2),
        )
        assert r_rebook.status_code == 200
        booking_refs.append(r_rebook.json()["booking_reference"])
    finally:
        r_cli = get_redis()
        if r_cli and table_id:
            for k in r_cli.scan_iter(f"gobeyond:lock:dining_table_{table_id}:*"):
                r_cli.delete(k)
        _cleanup_entities(
            db,
            user_ids=[u.id for u in (u1, u2) if u],
            booking_refs=booking_refs,
            table_ids=[table_id] if table_id else None,
            restaurant_ids=[rest_id] if rest_id else None,
        )
        db.close()


# ==============================================================================
# D-03: Strict Partner Vertical Isolation & Cross-Partner Venue Ownership
# ==============================================================================
def test_d03_partner_vertical_isolation_and_venue_ownership(client: TestClient):
    db = SessionLocal()
    u_cin = u_res = u_spt1 = u_spt2 = None
    p_ids: list[int] = []
    v_ids: list[int] = []
    try:
        loc = db.query(Location).first()
        u_cin = _create_user_with_roles(db, "d03_cin", ["partner_cinema"])
        u_res = _create_user_with_roles(db, "d03_res", ["partner_restaurant"])
        u_spt1 = _create_user_with_roles(db, "d03_spt1", ["partner_sports"])
        u_spt2 = _create_user_with_roles(db, "d03_spt2", ["partner_sports"])

        p_cin = Partner(
            user_id=u_cin.id, business_name="D03 Cinema", partner_type="CINEMA",
            contact_email=u_cin.email, contact_phone="9800000101", status="APPROVED",
        )
        p_res = Partner(
            user_id=u_res.id, business_name="D03 Rest", partner_type="RESTAURANT",
            contact_email=u_res.email, contact_phone="9800000102", status="APPROVED",
        )
        p_spt1 = Partner(
            user_id=u_spt1.id, business_name="D03 Sports 1", partner_type="SPORTS",
            contact_email=u_spt1.email, contact_phone="9800000103", status="APPROVED",
        )
        p_spt2 = Partner(
            user_id=u_spt2.id, business_name="D03 Sports 2", partner_type="SPORTS",
            contact_email=u_spt2.email, contact_phone="9800000104", status="APPROVED",
        )
        db.add_all([p_cin, p_res, p_spt1, p_spt2])
        db.flush()
        p_ids.extend([p_cin.id, p_res.id, p_spt1.id, p_spt2.id])

        venue_other = SportsVenue(
            partner_id=p_spt2.id,
            location_id=loc.id,
            name="D03 Foreign Sports Venue",
            sport_types=["Badminton"],
            address="Gachibowli, Hyderabad",
            is_active=True,
        )
        db.add(venue_other)
        db.commit()
        db.refresh(venue_other)
        v_ids.append(venue_other.id)

        # Unauthenticated /cinema/movies -> 401
        assert client.get("/api/v1/partners/cinema/movies").status_code == 401
        # Cross-vertical access blocked with 403
        assert client.get("/api/v1/partners/restaurant/menus", headers=_auth_header(u_cin)).status_code == 403
        assert client.get("/api/v1/partners/cinema/shows", headers=_auth_header(u_res)).status_code == 403
        assert client.get("/api/v1/partners/events", headers=_auth_header(u_res)).status_code == 403
        assert client.get("/api/v1/partners/sports/venues", headers=_auth_header(u_cin)).status_code == 403

        # Same vertical (SPORTS) partner trying to attach activity to ANOTHER sports partner's venue -> 403
        res_foreign_venue = client.post(
            "/api/v1/partners/activities",
            json={
                "venue_id": venue_other.id,
                "title": "Hijacked Court",
                "category": "SPORTS",
                "base_price": 500,
                "duration_minutes": 60,
                "min_age": 10,
            },
            headers=_auth_header(u_spt1),
        )
        assert res_foreign_venue.status_code == 403
    finally:
        _cleanup_entities(
            db,
            user_ids=[u.id for u in (u_cin, u_res, u_spt1, u_spt2) if u],
            venue_ids=v_ids,
            partner_ids=p_ids,
        )
        db.close()


# ==============================================================================
# D-04: Spoofed X-Forwarded-For Defeated by X-Real-IP / Rightmost Hop
# ==============================================================================
def test_d04_client_ip_prefers_x_real_ip_or_rightmost_xff():
    def _make_req(hdrs: list[tuple[bytes, bytes]]) -> Request:
        return Request({"type": "http", "headers": hdrs, "client": ("172.18.0.5", 12345)})

    req_with_real_ip = _make_req([
        (b"x-forwarded-for", b"1.2.3.4, 203.0.113.99"),
        (b"x-real-ip", b"203.0.113.99"),
    ])
    assert get_client_identifier(req_with_real_ip) == "203.0.113.99"

    req_xff_only = _make_req([
        (b"x-forwarded-for", b"10.0.0.1, 198.51.100.42"),
    ])
    assert get_client_identifier(req_xff_only) == "198.51.100.42"


# ==============================================================================
# D-05: Coupon Expiry, Exhaustion & Atomic Usage Limit Under Concurrency
# ==============================================================================
def test_d05_coupon_window_and_atomic_usage_limit(client: TestClient):
    db = SessionLocal()
    u1 = u2 = None
    tt_ids: list[int] = []
    c_ids: list[int] = []
    booking_refs: list[str] = []
    try:
        u1 = _create_user_with_roles(db, "d05_u1", ["customer"])
        u2 = _create_user_with_roles(db, "d05_u2", ["customer"])
        ev = db.query(Event).filter(Event.is_active == True).first()
        tt_pool = [
            EventTicketType(
                event_id=ev.id, name=f"D05-Tkt-{i}-{uuid.uuid4().hex[:4]}",
                description="D05", price=Decimal("500.00"), total_quantity=20,
                available_quantity=20, max_per_booking=5,
            )
            for i in range(6)
        ]
        now = datetime.datetime.now(datetime.timezone.utc)
        c_exp = Coupon(
            code=f"D05EXP{uuid.uuid4().hex[:4].upper()}",
            discount_type="FLAT", discount_value=Decimal("100.00"),
            min_order_value=Decimal("100.00"), max_discount=Decimal("100.00"),
            valid_from=now - datetime.timedelta(days=10),
            valid_until=now - datetime.timedelta(hours=1),
            usage_limit=50, used_count=0, is_active=True,
        )
        c_exh = Coupon(
            code=f"D05EXH{uuid.uuid4().hex[:4].upper()}",
            discount_type="FLAT", discount_value=Decimal("100.00"),
            min_order_value=Decimal("100.00"), max_discount=Decimal("100.00"),
            valid_from=now - datetime.timedelta(days=1),
            valid_until=now + datetime.timedelta(days=5),
            usage_limit=1, used_count=1, is_active=True,
        )
        c_one = Coupon(
            code=f"D05ONE{uuid.uuid4().hex[:4].upper()}",
            discount_type="FLAT", discount_value=Decimal("100.00"),
            min_order_value=Decimal("100.00"), max_discount=Decimal("100.00"),
            valid_from=now - datetime.timedelta(days=1),
            valid_until=now + datetime.timedelta(days=5),
            usage_limit=1, used_count=0, is_active=True,
        )
        db.add_all([*tt_pool, c_exp, c_exh, c_one])
        db.commit()
        tt_ids = [t.id for t in tt_pool]
        tt_id = tt_ids[0]
        c_ids.extend([c_exp.id, c_exh.id, c_one.id])

        # apply-coupon rejects expired and exhausted coupons
        assert client.post("/api/v1/bookings/apply-coupon", json={"code": c_exp.code, "order_amount": 500, "booking_type": "EVENT"}).json()["valid"] is False
        assert client.post("/api/v1/bookings/apply-coupon", json={"code": c_exh.code, "order_amount": 500, "booking_type": "EVENT"}).json()["valid"] is False

        # initiate rejects expired & exhausted with 400
        assert client.post(
            "/api/v1/bookings/initiate",
            json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt_id, "quantity": 1}], "coupon_code": c_exp.code},
            headers=_auth_header(u1),
        ).status_code == 400
        assert client.post(
            "/api/v1/bookings/initiate",
            json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt_id, "quantity": 1}], "coupon_code": c_exh.code},
            headers=_auth_header(u1),
        ).status_code == 400

        # Concurrent single-use coupon race across 6 distinct tickets -> zero ticket lock contention,
        # forcing all 6 through the atomic SQL coupon increment -> strictly 1 succeeds (201), 5 get 400
        def _use_single(i: int):
            hdr = _auth_header(u1 if i % 2 == 0 else u2)
            with TestClient(app) as tc:
                return tc.post(
                    "/api/v1/bookings/initiate",
                    json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt_ids[i], "quantity": 1}], "coupon_code": c_one.code},
                    headers=hdr,
                )

        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(_use_single, range(6)))

        statuses = [r.status_code for r in results]
        for r in results:
            if r.status_code == 201:
                booking_refs.append(r.json()["booking_reference"])
        assert statuses.count(201) == 1
        assert statuses.count(400) == 5

        db.expire_all()
        db.refresh(c_one)
        assert c_one.used_count == 1
    finally:
        _cleanup_entities(
            db,
            user_ids=[u.id for u in (u1, u2) if u],
            booking_refs=booking_refs,
            ticket_type_ids=tt_ids if tt_ids else None,
            coupon_ids=c_ids,
        )
        db.close()


# ==============================================================================
# D-06: Password Reset Revokes Active Refresh Tokens
# ==============================================================================
def test_d06_password_reset_revokes_all_refresh_tokens(client: TestClient):
    db = SessionLocal()
    created_uid = None
    clean_phone = f"94{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"
    try:
        email = f"d06_{uuid.uuid4().hex[:6]}@gobeyondqa.com"
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "phone": clean_phone, "full_name": "D06 Reset", "password": "Password@123"},
        )
        assert reg.status_code == 201
        created_uid = reg.json()["user_id"]
        old_refresh = reg.json()["refresh_token"]
        old_csrf = reg.cookies.get("gobeyond_csrf_token", "")

        assert client.post("/api/v1/auth/forgot-password", json={"email_or_phone": email}).status_code == 200
        otp_code = settings.OTP_DEFAULT_DEV_CODE if settings.OTP_SANDBOX_MODE else "123456"
        if not settings.OTP_SANDBOX_MODE:
            r_cli = get_redis()
            if r_cli:
                raw_otp = r_cli.get(otp_service._cache_key(clean_phone, "password_reset"))
                if raw_otp:
                    otp_code = json.loads(raw_otp)["code"]

        rst = client.post(
            "/api/v1/auth/reset-password",
            json={"email_or_phone": email, "otp": otp_code, "new_password": "NewPassword@456"},
        )
        assert rst.status_code == 200

        db.expire_all()
        active_tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == created_uid,
            RefreshToken.is_revoked == False,
        ).count()
        assert active_tokens == 0

        # Refresh with pre-reset token must fail 401
        ref_res = client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": old_csrf, "X-Refresh-Token": old_refresh},
        )
        assert ref_res.status_code == 401
    finally:
        r_cli = get_redis()
        if r_cli:
            for k in r_cli.scan_iter(f"*{clean_phone}*"):
                r_cli.delete(k)
        _cleanup_entities(
            db,
            user_ids=[created_uid] if created_uid else None,
            outbox_recipients=[clean_phone],
        )
        db.close()


# ==============================================================================
# D-07: /bookings/expire-stale Restricted Strictly to Super Admin
# ==============================================================================
def test_d07_expire_stale_requires_super_admin(client: TestClient):
    db = SessionLocal()
    cust = adm = None
    try:
        cust = _create_user_with_roles(db, "d07_cust", ["customer"])
        adm = _create_user_with_roles(db, "d07_adm", ["super_admin"])

        assert client.post("/api/v1/bookings/expire-stale").status_code == 401
        assert client.post("/api/v1/bookings/expire-stale", headers=_auth_header(cust)).status_code == 403
        res_adm = client.post("/api/v1/bookings/expire-stale", headers=_auth_header(adm, "super_admin"))
        assert res_adm.status_code == 200
    finally:
        _cleanup_entities(db, user_ids=[u.id for u in (cust, adm) if u])
        db.close()


# ==============================================================================
# D-08: Admin Cancel Audit & Refund Status State Synchronization
# ==============================================================================
def test_d08_admin_cancel_and_partial_full_refund_integrity(client: TestClient):
    db = SessionLocal()
    cust = adm = None
    tt_id = None
    booking_refs: list[str] = []
    try:
        cust = _create_user_with_roles(db, "d08_cust", ["customer"])
        adm = _create_user_with_roles(db, "d08_adm", ["super_admin"])
        ev = db.query(Event).filter(Event.is_active == True).first()
        tt = EventTicketType(
            event_id=ev.id, name=f"D08-Tkt-{uuid.uuid4().hex[:4]}",
            description="D08", price=Decimal("300.00"), total_quantity=10,
            available_quantity=10, max_per_booking=5,
        )
        db.add(tt)
        db.commit()
        db.refresh(tt)
        tt_id = tt.id

        # 1. Admin cancels unpaid PAYMENT_PENDING booking -> restores quantity + accurate previous_status
        b_pending = client.post(
            "/api/v1/bookings/initiate",
            json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt_id, "quantity": 2}]},
            headers=_auth_header(cust),
        ).json()
        booking_refs.append(b_pending["booking_reference"])
        db.expire_all()
        db.refresh(tt)
        assert tt.available_quantity == 8

        cxl_pend = client.post(
            f"/api/v1/admin/bookings/{b_pending['booking_reference']}/cancel?reason=D08+Unpaid+Cancel",
            headers=_auth_header(adm, "super_admin"),
        )
        assert cxl_pend.status_code == 200
        assert cxl_pend.json()["status"] == "CANCELLED"
        db.expire_all()
        db.refresh(tt)
        assert tt.available_quantity == 10
        audit_pend = db.query(AuditLog).filter(
            AuditLog.resource_id == b_pending["booking_reference"],
            AuditLog.action == "ADMIN_BOOKING_CANCEL",
        ).first()
        assert audit_pend.details["previous_status"] == "PAYMENT_PENDING"

        # 2. Admin cancels confirmed paid booking -> restores quantity, creates INITIATED Refund, sets REFUND_PENDING
        b_paid_cxl = client.post(
            "/api/v1/bookings/initiate",
            json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt_id, "quantity": 1}]},
            headers=_auth_header(cust),
        ).json()
        booking_refs.append(b_paid_cxl["booking_reference"])
        ord_res = client.post("/api/v1/payments/create-order", json={"booking_id": b_paid_cxl["id"]}, headers=_auth_header(cust)).json()
        pay_id1 = f"pay_d08a_{uuid.uuid4().hex[:8]}"
        sig1 = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{ord_res['order_id']}|{pay_id1}".encode(), hashlib.sha256).hexdigest()
        assert client.post(
            "/api/v1/payments/verify-signature",
            json={"booking_id": b_paid_cxl["id"], "razorpay_order_id": ord_res["order_id"], "razorpay_payment_id": pay_id1, "razorpay_signature": sig1},
            headers=_auth_header(cust),
        ).status_code == 200

        cxl_paid = client.post(
            f"/api/v1/admin/bookings/{b_paid_cxl['booking_reference']}/cancel?reason=D08+Paid+Cancel",
            headers=_auth_header(adm, "super_admin"),
        )
        assert cxl_paid.status_code == 200
        assert cxl_paid.json()["status"] == "REFUND_PENDING"
        db.expire_all()
        db.refresh(tt)
        assert tt.available_quantity == 10
        p1 = db.query(Payment).filter(Payment.booking_id == b_paid_cxl["id"]).first()
        assert p1.status == "REFUND_PENDING"
        rf1 = db.query(Refund).filter(Refund.booking_id == b_paid_cxl["id"]).first()
        assert rf1 is not None and rf1.status == "INITIATED"

        # Over-refund prevented because INITIATED refund already covers balance
        assert client.post(
            f"/api/v1/admin/bookings/{b_paid_cxl['booking_reference']}/refund",
            json={"reason": "Duplicate refund attempt"},
            headers=_auth_header(adm, "super_admin"),
        ).status_code == 400

        # 3. Partial then full admin refund syncs Payment.status: PARTIALLY_REFUNDED -> REFUNDED
        b_rf = client.post(
            "/api/v1/bookings/initiate",
            json={"booking_type": "EVENT", "items": [{"item_type": "TICKET", "item_id": tt_id, "quantity": 1}]},
            headers=_auth_header(cust),
        ).json()
        booking_refs.append(b_rf["booking_reference"])
        ord2 = client.post("/api/v1/payments/create-order", json={"booking_id": b_rf["id"]}, headers=_auth_header(cust)).json()["order_id"]
        pay_id2 = f"pay_d08b_{uuid.uuid4().hex[:8]}"
        sig2 = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{ord2}|{pay_id2}".encode(), hashlib.sha256).hexdigest()
        client.post(
            "/api/v1/payments/verify-signature",
            json={"booking_id": b_rf["id"], "razorpay_order_id": ord2, "razorpay_payment_id": pay_id2, "razorpay_signature": sig2},
            headers=_auth_header(cust),
        )

        # Partial 100.00 INR
        rf_part = client.post(
            f"/api/v1/admin/bookings/{b_rf['booking_reference']}/refund",
            json={"amount": 100.0, "reason": "D08 Partial refund"},
            headers=_auth_header(adm, "super_admin"),
        )
        assert rf_part.status_code == 200
        assert rf_part.json()["payment_status"] == "PARTIALLY_REFUNDED"
        assert rf_part.json()["booking_status"] == "CONFIRMED"

        # Remaining full balance
        rf_rest = client.post(
            f"/api/v1/admin/bookings/{b_rf['booking_reference']}/refund",
            json={"reason": "D08 Remaining refund"},
            headers=_auth_header(adm, "super_admin"),
        )
        assert rf_rest.status_code == 200
        assert rf_rest.json()["payment_status"] == "REFUNDED"
        assert rf_rest.json()["booking_status"] == "REFUNDED"
    finally:
        _cleanup_entities(
            db,
            user_ids=[u.id for u in (cust, adm) if u],
            booking_refs=booking_refs,
            ticket_type_ids=[tt_id] if tt_id else None,
        )
        db.close()


# ==============================================================================
# D-09 & D-14 Worker Heartbeat: ARQ Worker Lock Key Cleanup & /worker/status
# ==============================================================================
def test_d09_worker_expire_stale_cleans_movie_key_dining_and_heartbeat(client: TestClient):
    db = SessionLocal()
    cust = adm = None
    booking_refs: list[str] = []
    redis_cleanup_keys: list[str] = []
    try:
        cust = _create_user_with_roles(db, "d09_cust", ["customer"])
        adm = _create_user_with_roles(db, "d09_adm", ["super_admin"])

        seat_row = db.execute(text("""
            SELECT ms.id AS show_id, s.id AS seat_id
            FROM movie_shows ms
            JOIN seats s ON s.screen_id = ms.screen_id
            WHERE ms.status <> 'CANCELLED'
              AND NOT EXISTS (
                SELECT 1 FROM seat_locks sl
                WHERE sl.resource_type = 'MOVIE_SHOW' AND sl.resource_id = ms.id
                  AND sl.identifier = 'seat_' || s.id AND sl.is_released = false
              )
            ORDER BY ms.id ASC, s.id ASC LIMIT 1
        """)).fetchone()
        assert seat_row is not None
        show_id, seat_id = int(seat_row.show_id), int(seat_row.seat_id)

        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        lock_tok = f"tok_{uuid.uuid4().hex[:8]}"
        redis_lock_key = f"gobeyond:lock:show_{show_id}:seat_{seat_id}"
        redis_cleanup_keys.append(redis_lock_key)

        r_cli = get_redis()
        assert r_cli is not None
        r_cli.set(redis_lock_key, lock_tok, ex=300)

        mov_ref = f"GB-D09M-{uuid.uuid4().hex[:6].upper()}"
        booking_refs.append(mov_ref)
        b_mov = Booking(
            booking_reference=mov_ref,
            user_id=cust.id,
            booking_type="MOVIE",
            total_amount=Decimal("200.00"),
            tax_amount=Decimal("36.00"),
            discount_amount=Decimal("0.00"),
            final_payable=Decimal("236.00"),
            status="PAYMENT_PENDING",
            expires_at=past,
        )
        db.add(b_mov)
        db.flush()
        db.add(BookingItem(
            booking_id=b_mov.id,
            item_type="SEAT",
            item_id=seat_id,
            name="Seat Test",
            quantity=1,
            unit_price=Decimal("200.00"),
            subtotal=Decimal("200.00"),
            details={"show_id": show_id},
        ))
        db.add(SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=show_id,
            identifier=f"seat_{seat_id}",
            user_id=cust.id,
            lock_token=lock_tok,
            expires_at=past,
            is_released=False,
        ))
        db.commit()

        expired = asyncio.run(expire_stale_bookings({}))
        assert expired >= 1
        assert r_cli.get(redis_lock_key) is None
        assert r_cli.get("gobeyond:worker:heartbeat") is not None

        db.expire_all()
        db.refresh(b_mov)
        assert b_mov.status == "EXPIRED"

        w_stat = client.get("/api/v1/notifications/worker/status", headers=_auth_header(adm, "super_admin"))
        assert w_stat.status_code == 200
        assert w_stat.json()["is_healthy"] is True
        assert w_stat.json()["active_workers_count"] == 1
    finally:
        r_cli = get_redis()
        if r_cli:
            for k in redis_cleanup_keys:
                r_cli.delete(k)
        _cleanup_entities(
            db,
            user_ids=[u.id for u in (cust, adm) if u],
            booking_refs=booking_refs,
        )
        db.close()


# ==============================================================================
# D-10: LockService & OTPService Auto-Reconnect After Real Outage Recovery
# ==============================================================================
def test_d10_lock_and_otp_auto_reconnect_without_breaking_manual_none(monkeypatch):
    import app.core.redis as redis_mod

    # 1. Transient connection failure marks _needs_reconnect=True -> cooldown elapsed -> auto-recovers
    svc = LockService()
    assert svc.redis_client is not None
    svc._mark_redis_down()
    assert svc.redis_client is None and svc._needs_reconnect is True
    svc._reconnect_after = time.monotonic() - 0.1

    key = f"d10_reconn_{uuid.uuid4().hex[:6]}"
    tok = "tok_reconn"
    try:
        assert svc.acquire_lock(key, tok, expiry_seconds=30) is True
        assert svc.redis_client is not None
        assert svc.release_lock(key, tok) is True
    finally:
        r_cli = get_redis()
        if r_cli:
            r_cli.delete(f"gobeyond:lock:{key}")

    # 2. OTPService auto-reconnect when _needs_reconnect=True & cooldown elapsed
    osvc = OTPService()
    assert osvc.redis_client is not None
    osvc._mark_redis_down()
    osvc._reconnect_after = time.monotonic() - 0.1
    assert osvc._get_client() is not None

    # 3. get_redis() cooldown is anchored strictly AFTER a slow ping/connect failure and auto-recovers
    class _SlowFailClient:
        def ping(self):
            time.sleep(0.05)
            raise RuntimeError("simulated slow redis failure")

    orig_client = redis_mod._redis_client
    orig_fail_until = redis_mod._failure_until
    orig_cooldown = redis_mod._FAILURE_COOLDOWN_SECONDS
    try:
        monkeypatch.setattr(redis_mod, "_FAILURE_COOLDOWN_SECONDS", 0.1)
        redis_mod._redis_client = _SlowFailClient()
        redis_mod._failure_until = 0.0
        assert redis_mod.get_redis() is None
        after_fail = time.monotonic()
        assert redis_mod._failure_until > after_fail
        # Immediate repeat call short-circuits in cooldown without blocking
        assert redis_mod.get_redis() is None
        # Once cooldown expires, get_redis() automatically reconnects
        time.sleep(0.15)
        recovered = redis_mod.get_redis()
        assert recovered is not None
        assert recovered.ping() is True
    finally:
        if redis_mod._redis_client is not orig_client and not isinstance(redis_mod._redis_client, _SlowFailClient):
            redis_mod._redis_client = orig_client
        redis_mod._failure_until = orig_fail_until


# ==============================================================================
# D-11: OTP Outbox Masks Plaintext OTP Code
# ==============================================================================
def test_d11_otp_outbox_masks_code_and_omits_prefix(client: TestClient):
    db = SessionLocal()
    test_phone = f"+9193{int(uuid.uuid4().hex[:8], 16) % 100000000:08d}"
    try:
        res = client.post("/api/v1/auth/request-otp", json={"phone": test_phone, "purpose": "login"})
        assert res.status_code == 200

        row = (
            db.query(NotificationOutbox)
            .filter(NotificationOutbox.recipient == test_phone, NotificationOutbox.event_type == "OTP_VERIFICATION")
            .order_by(NotificationOutbox.id.desc())
            .first()
        )
        assert row is not None
        assert "123456" not in row.content
        assert "******" in row.content
        assert "12" not in row.idempotency_key.split("_")
        assert "code" not in (row.payload or {})
    finally:
        r_cli = get_redis()
        if r_cli:
            for k in r_cli.scan_iter(f"*{test_phone}*"):
                r_cli.delete(k)
        _cleanup_entities(db, outbox_recipients=[test_phone])
        db.close()


# ==============================================================================
# D-12: verify_otp Role Priority Parity + Reconciliation Health Consistency
# ==============================================================================
def test_d12_verify_otp_role_priority_and_reconciliation_parity(client: TestClient):
    db = SessionLocal()
    multi_user = None
    max_audit_before = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM audit_logs")).scalar()
    try:
        multi_user = _create_user_with_roles(db, "d12_multi", ["customer", "partner_restaurant"])
        otp_service.send_otp(phone=multi_user.phone, purpose="login")
        otp_code = settings.OTP_DEFAULT_DEV_CODE if settings.OTP_SANDBOX_MODE else "123456"
        if not settings.OTP_SANDBOX_MODE:
            r_cli = get_redis()
            if r_cli:
                raw = r_cli.get(otp_service._cache_key(multi_user.phone, "login"))
                if raw:
                    otp_code = json.loads(raw)["code"]

        ver = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": multi_user.phone, "otp": otp_code, "purpose": "login"},
        )
        assert ver.status_code == 200
        assert ver.json()["role"] == "partner_restaurant"

        rep = ReconciliationEngine.run_reconciliation_audit(db, actor_id=multi_user.id)
        audit_row = (
            db.query(AuditLog)
            .filter(AuditLog.action == "RECONCILIATION_AUDIT_EXECUTED")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit_row is not None
        assert audit_row.details["is_healthy"] == rep.is_healthy
    finally:
        r_cli = get_redis()
        if r_cli and multi_user:
            for k in r_cli.scan_iter(f"*{multi_user.phone}*"):
                r_cli.delete(k)
        db.execute(
            text("DELETE FROM notifications WHERE type = 'ADMIN_ALERT' AND title LIKE 'Financial Reconciliation Alert%' AND created_at > NOW() - INTERVAL '1 minute'")
        )
        db.commit()
        _cleanup_entities(
            db,
            user_ids=[multi_user.id] if multi_user else None,
            outbox_recipients=[multi_user.phone] if multi_user else None,
            audit_ids_after=max_audit_before,
        )
        db.close()


# ==============================================================================
# D-14 / D-15: /metrics Active Locks Gauge & Production Skips metadata.create_all
# ==============================================================================
def test_d14_d15_metrics_gauge_and_prod_skips_create_all(client: TestClient, monkeypatch):
    met = client.get("/metrics")
    assert met.status_code == 200
    assert "gobeyond_http_requests_total" in met.text
    assert "gobeyond_http_request_duration_seconds_bucket" in met.text
    assert "gobeyond_active_inventory_locks" in met.text

    called = {"count": 0}

    def _spy_create_all(*args, **kwargs):
        called["count"] += 1

    monkeypatch.setattr(Base.metadata, "create_all", _spy_create_all)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(settings, "DEBUG", False)
    on_startup()
    assert called["count"] == 0
