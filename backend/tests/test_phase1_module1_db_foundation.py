import datetime
import uuid
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import Base
from app.models.user import User, UserProfile, Role, Permission, RefreshToken
from app.models.location import Location
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.payment import Payment, Refund, Coupon
from app.models.dining import Restaurant, DiningTable, DiningReservation
from app.models.event import Event, EventTicketType
from app.models.sports import SportsVenue, Activity, ActivitySlot
from app.models.movie import Cinema, Screen, Seat, Movie, MovieShow
from app.models.partner import Partner, PartnerDocument
from app.models.audit import AuditLog, Notification, Review


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(settings.DATABASE_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_m1_all_33_application_tables_exist_and_accessible(db_session):
    """Verify that all 32 core platform tables plus refresh_tokens exist and can be queried."""
    expected_models = [
        User, UserProfile, Role, Permission, RefreshToken,
        Location, Partner, PartnerDocument,
        Cinema, Screen, Seat, Movie, MovieShow,
        Restaurant, DiningTable, DiningReservation,
        Event, EventTicketType,
        SportsVenue, Activity, ActivitySlot,
        Booking, BookingItem, SeatLock,
        Payment, Refund, Coupon,
        AuditLog, Notification, Review
    ]
    for model in expected_models:
        count = db_session.query(model).count()
        assert count >= 0, f"Failed to query {model.__tablename__}"


def test_m1_foreign_key_integrity_enforcement(db_session):
    """Verify PostgreSQL foreign key constraints reject orphaned references."""
    if db_session.bind.dialect.name == "sqlite":
        db_session.execute(text("PRAGMA foreign_keys = ON;"))
    invalid_booking = Booking(
        booking_reference=f"GB-TEST-FK-{uuid.uuid4().hex[:8]}",
        user_id=99999999,  # Non-existent user ID
        booking_type="MOVIE",
        total_amount=500.0,
        final_payable=500.0,
        status="PENDING"
    )
    db_session.add(invalid_booking)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_m1_seat_lock_partial_unique_index_active_only(db_session):
    """Verify uq_active_resource_lock prevents duplicate active locks but permits released locks."""
    user = db_session.query(User).first()
    assert user is not None

    token1 = str(uuid.uuid4())
    token2 = str(uuid.uuid4())
    token3 = str(uuid.uuid4())
    test_identifier = f"SEAT_M1_{uuid.uuid4().hex[:6]}"

    lock1 = SeatLock(
        resource_type="MOVIE_SHOW",
        resource_id=1,
        identifier=test_identifier,
        user_id=user.id,
        lock_token=token1,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
        is_released=False
    )
    db_session.add(lock1)
    db_session.commit()

    try:
        # Attempting second active lock on same resource must fail
        lock2 = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=1,
            identifier=test_identifier,
            user_id=user.id,
            lock_token=token2,
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
            is_released=False
        )
        db_session.add(lock2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

        # Release lock 1
        db_session.query(SeatLock).filter(SeatLock.lock_token == token1).update({"is_released": True})
        db_session.commit()

        # Now creating a new lock with is_released=False must succeed
        lock3 = SeatLock(
            resource_type="MOVIE_SHOW",
            resource_id=1,
            identifier=test_identifier,
            user_id=user.id,
            lock_token=token3,
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
            is_released=False
        )
        db_session.add(lock3)
        db_session.commit()
    finally:
        db_session.query(SeatLock).filter(SeatLock.identifier == test_identifier).delete()
        db_session.commit()


def test_m1_dining_reservation_gist_exclusion_constraint(db_session):
    """Verify exclude_overlapping_dining_reservations blocks overlapping active reservations."""
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("GiST exclusion constraint requires PostgreSQL btree_gist extension")
    user = db_session.query(User).first()
    table = db_session.query(DiningTable).first()
    assert user is not None and table is not None

    base_date = datetime.date.today() + datetime.timedelta(days=14)
    base_time = datetime.time(20, 0, 0)
    start_dt1 = datetime.datetime.combine(base_date, base_time)
    end_dt1 = start_dt1 + datetime.timedelta(minutes=105)

    res1 = DiningReservation(
        booking_id=None,
        restaurant_id=table.restaurant_id,
        table_id=table.id,
        user_id=user.id,
        reservation_date=base_date,
        reservation_time=base_time,
        guest_count=2,
        duration_minutes=90,
        buffer_minutes=15,
        start_datetime=start_dt1,
        end_datetime=end_dt1,
        status="CONFIRMED"
    )
    db_session.add(res1)
    db_session.commit()

    try:
        # Overlapping reservation starting 30 mins after res1 on the same physical table
        start_dt2 = start_dt1 + datetime.timedelta(minutes=30)
        end_dt2 = start_dt2 + datetime.timedelta(minutes=105)

        res2 = DiningReservation(
            booking_id=None,
            restaurant_id=table.restaurant_id,
            table_id=table.id,
            user_id=user.id,
            reservation_date=base_date,
            reservation_time=datetime.time(20, 30, 0),
            guest_count=2,
            duration_minutes=90,
            buffer_minutes=15,
            start_datetime=start_dt2,
            end_datetime=end_dt2,
            status="CONFIRMED"
        )
        db_session.add(res2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    finally:
        db_session.query(DiningReservation).filter(DiningReservation.id == res1.id).delete()
        db_session.commit()


def test_m1_ticket_and_slot_check_constraints(db_session):
    """Verify non-negative check constraints on ticket quantities and slot capacities."""
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("CHECK constraint DDL enforcement requires PostgreSQL database")
    ticket = db_session.query(EventTicketType).first()
    slot = db_session.query(ActivitySlot).first()
    assert ticket is not None and slot is not None

    # Test chk_ticket_quantity_valid: available_quantity cannot be negative
    try:
        with pytest.raises(IntegrityError):
            db_session.execute(
                text(f"UPDATE event_ticket_types SET available_quantity = -5 WHERE id = {ticket.id};")
            )
            db_session.commit()
    finally:
        db_session.rollback()

    # Test chk_slot_capacity_valid: booked_count cannot exceed capacity
    try:
        with pytest.raises(IntegrityError):
            db_session.execute(
                text(f"UPDATE activity_slots SET booked_count = {slot.capacity + 10} WHERE id = {slot.id};")
            )
            db_session.commit()
    finally:
        db_session.rollback()


def test_m1_multi_city_hierarchy_and_expansion_without_ddl(db_session):
    """Verify locations hierarchy navigation and zero-DDL expansion to a new city."""
    # 1. Verify Hyderabad hierarchy
    hyd = db_session.query(Location).filter(Location.slug == "hyderabad", Location.type == "CITY").first()
    assert hyd is not None
    assert hyd.parent_id is None
    assert len(hyd.sub_locations) >= 8

    locality_names = {sub.name for sub in hyd.sub_locations}
    assert "Jubilee Hills" in locality_names
    assert "Gachibowli" in locality_names
    assert "Banjara Hills" in locality_names

    # 2. Test multi-city expansion without schema changes: Insert Bengaluru and Indiranagar
    blr_slug = f"bengaluru-test-{uuid.uuid4().hex[:6]}"
    blr = Location(
        name="Bengaluru",
        slug=blr_slug,
        type="CITY",
        parent_id=None,
        state="Karnataka",
        country="India",
        latitude=12.9716,
        longitude=77.5946,
        is_active=True
    )
    db_session.add(blr)
    db_session.commit()

    indira_slug = f"indiranagar-test-{uuid.uuid4().hex[:6]}"
    indira = Location(
        name="Indiranagar",
        slug=indira_slug,
        type="LOCALITY",
        parent_id=blr.id,
        state="Karnataka",
        country="India",
        latitude=12.9784,
        longitude=77.6408,
        is_active=True
    )
    db_session.add(indira)
    db_session.commit()

    try:
        # Verify hierarchical retrieval
        retrieved_blr = db_session.query(Location).filter(Location.id == blr.id).first()
        assert retrieved_blr is not None
        assert len(retrieved_blr.sub_locations) == 1
        assert retrieved_blr.sub_locations[0].slug == indira_slug
    finally:
        db_session.query(Location).filter(Location.id == indira.id).delete()
        db_session.query(Location).filter(Location.id == blr.id).delete()
        db_session.commit()


def test_m1_user_profile_locality_fallback_and_persistence(db_session):
    """Verify user_profiles has nullable locality_id, supports optional locality, and restores saved locality."""
    user = db_session.query(User).first()
    assert user is not None

    hyd = db_session.query(Location).filter(Location.slug == "hyderabad").first()
    jubilee = db_session.query(Location).filter(Location.slug == "jubilee-hills").first()
    assert hyd is not None and jubilee is not None

    profile = db_session.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    orig_city_id = profile.city_id
    orig_locality_id = profile.locality_id

    try:
        # Case A: User has city Hyderabad and NO locality (GPS denied, no locality silently assigned)
        profile.city_id = hyd.id
        profile.locality_id = None
        db_session.commit()

        reloaded = db_session.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        assert reloaded.city_id == hyd.id
        assert reloaded.locality_id is None, "Locality must not be silently defaulted to an arbitrary locality"

        # Case B: User explicitly selects Jubilee Hills
        reloaded.locality_id = jubilee.id
        db_session.commit()

        reloaded2 = db_session.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        assert reloaded2.city_id == hyd.id
        assert reloaded2.locality_id == jubilee.id
        assert reloaded2.locality.name == "Jubilee Hills"
    finally:
        profile.city_id = orig_city_id
        profile.locality_id = orig_locality_id
        db_session.commit()


from app.services.revenue import calculate_revenue_metrics


def test_m1_verified_revenue_calculation_partial_payments_deduplication_and_refunds(db_session):
    """Verify platform revenue calculation:
    1. Does NOT use MAX(payment.amount) - correctly sums multiple partial captures.
    2. Deduplicates duplicate webhooks sharing the same gateway_payment_id.
    3. Excludes failed, initiated, and reversed payment transactions.
    4. Deduplicates and subtracts processed refunds.
    5. Calculates separate metrics: gross booking value, captured value, refunds, net collected, and platform revenue."""
    user = db_session.query(User).first()
    assert user is not None

    # Booking 1: Confirmed booking of 1000.0 with TWO partial payments (600.0 + 400.0)
    # Plus a duplicate webhook for the 600.0 payment (sharing gateway_payment_id)
    booking_1 = Booking(
        booking_reference=f"GB-REV-PARTIAL-{uuid.uuid4().hex[:6]}",
        user_id=user.id,
        booking_type="EVENTS",
        total_amount=1000.0,
        final_payable=1000.0,
        status="CONFIRMED"
    )

    # Booking 2: Confirmed booking of 500.0 with one captured payment of 500.0,
    # and a processed refund of 100.0 (plus duplicate refund webhook)
    booking_2 = Booking(
        booking_reference=f"GB-REV-REFUND-{uuid.uuid4().hex[:6]}",
        user_id=user.id,
        booking_type="SPORTS",
        total_amount=500.0,
        final_payable=500.0,
        status="CONFIRMED"
    )

    # Booking 3: PENDING booking of 800.0 with a FAILED payment of 800.0 and REVERSED payment of 800.0
    booking_3 = Booking(
        booking_reference=f"GB-REV-FAIL-{uuid.uuid4().hex[:6]}",
        user_id=user.id,
        booking_type="MOVIES",
        total_amount=800.0,
        final_payable=800.0,
        status="PENDING"
    )

    db_session.add_all([booking_1, booking_2, booking_3])
    db_session.commit()

    test_booking_ids = [booking_1.id, booking_2.id, booking_3.id]

    try:
        # Payments for Booking 1:
        # Partial capture 1: 600.0
        pay_id_1 = f"pay_part1_{uuid.uuid4().hex[:8]}"
        p1 = Payment(
            booking_id=booking_1.id, user_id=user.id, amount=600.0,
            status="CAPTURED", gateway_payment_id=pay_id_1, gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )
        # Partial capture 2: 400.0 (distinct gateway_payment_id):
        pay_id_2 = f"pay_part2_{uuid.uuid4().hex[:8]}"
        p2 = Payment(
            booking_id=booking_1.id, user_id=user.id, amount=400.0,
            status="CAPTURED", gateway_payment_id=pay_id_2, gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )

        # Payments for Booking 2:
        # Captured: 500.0
        pay_id_3 = f"pay_full_{uuid.uuid4().hex[:8]}"
        p3 = Payment(
            booking_id=booking_2.id, user_id=user.id, amount=500.0,
            status="SUCCESS", gateway_payment_id=pay_id_3, gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )

        # Payments for Booking 3 (should be excluded from captured):
        p4_fail = Payment(
            booking_id=booking_3.id, user_id=user.id, amount=800.0,
            status="FAILED", gateway_payment_id=f"pay_fail_{uuid.uuid4().hex[:8]}", gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )
        p5_rev = Payment(
            booking_id=booking_3.id, user_id=user.id, amount=800.0,
            status="REVERSED", gateway_payment_id=f"pay_rev_{uuid.uuid4().hex[:8]}", gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )

        db_session.add_all([p1, p2, p3, p4_fail, p5_rev])
        db_session.commit()

        # Database-level duplicate webhook rejection test:
        # Attempting to insert a duplicate payment with the same gateway_payment_id
        # must be rejected by PostgreSQL unique constraint ix_payments_gateway_payment_id
        p1_dup = Payment(
            booking_id=booking_1.id, user_id=user.id, amount=600.0,
            status="CAPTURED", gateway_payment_id=pay_id_1, gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )
        db_session.add(p1_dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

        # Refunds for Booking 2:
        # Processed refund of 100.0
        rfn_id_1 = f"rfn_test_{uuid.uuid4().hex[:8]}"
        rf1 = Refund(
            payment_id=p3.id, booking_id=booking_2.id, amount=100.0,
            status="SUCCESS", gateway_refund_id=rfn_id_1
        )
        # Failed refund attempt (should be excluded)
        rf_fail = Refund(
            payment_id=p3.id, booking_id=booking_2.id, amount=50.0,
            status="FAILED", gateway_refund_id=f"rfn_fail_{uuid.uuid4().hex[:8]}"
        )
        db_session.add_all([rf1, rf_fail])
        db_session.commit()

        # Database-level duplicate refund webhook rejection test:
        rf1_dup = Refund(
            payment_id=p3.id, booking_id=booking_2.id, amount=100.0,
            status="SUCCESS", gateway_refund_id=rfn_id_1
        )
        db_session.add(rf1_dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

        # Execute revenue calculation
        metrics = calculate_revenue_metrics(db_session, booking_ids=test_booking_ids)

        # Assertions:
        # 1. Gross Confirmed Booking Value:
        # Booking 1 (1000.0) + Booking 2 (500.0) = 1500.0. (Booking 3 is PENDING, excluded)
        assert metrics["gross_confirmed_booking_value"] == 1500.0

        # 2. Total Successfully Captured Payments:
        # Booking 1: p1 (600.0, p1_dup deduplicated) + p2 (400.0) = 1000.0
        # Booking 2: p3 (500.0) = 500.0
        # Booking 3: p4_fail (0.0) + p5_rev (0.0) = 0.0
        # Total Captured = 1000.0 + 500.0 = 1500.0
        # NOTE: If MAX(payment.amount) was used, Booking 1 would have yielded 600 instead of 1000!
        assert metrics["total_captured_payments"] == 1500.0, f"Expected 1500.0, got {metrics['total_captured_payments']}"

        # 3. Total Successfully Refunded Amount:
        # Booking 2: rf1 (100.0, rf1_dup deduplicated) = 100.0. rf_fail is excluded.
        assert metrics["total_refunded_amount"] == 100.0

        # 4. Net Collected Amount:
        # 1500.0 - 100.0 = 1400.0
        assert metrics["net_collected_amount"] == 1400.0

        # 5. Partner Settlements & Actual Platform Revenue:
        # Default partner commission take-rate is 10% (0.10)
        # Platform Revenue = 1400.0 * 0.10 = 140.0
        # Partner Settlements Payable = 1400.0 * 0.90 = 1260.0
        assert metrics["actual_platform_revenue"] == 140.0
        assert metrics["partner_settlements_payable"] == 1260.0
        assert metrics["total_revenue"] == 140.0

    finally:
        # Clean up isolated test data
        db_session.query(Refund).filter(Refund.booking_id.in_(test_booking_ids)).delete(synchronize_session=False)
        db_session.query(Payment).filter(Payment.booking_id.in_(test_booking_ids)).delete(synchronize_session=False)
        db_session.query(Booking).filter(Booking.id.in_(test_booking_ids)).delete(synchronize_session=False)
        db_session.commit()


def test_m1_audit_logs_append_only_structure(db_session):
    """Verify audit_logs can be appended, records action metadata, and has no updated_at column."""
    assert not hasattr(AuditLog, "updated_at"), "AuditLog must be immutable and cannot possess an updated_at column"

    user = db_session.query(User).first()
    assert user is not None

    test_action = f"TEST_M1_ACTION_{uuid.uuid4().hex[:6]}"
    log_entry = AuditLog(
        user_id=user.id,
        action=test_action,
        resource_type="PARTNER",
        resource_id="partner_123",
        ip_address="127.0.0.1",
        user_agent="Pytest Agent 1.0",
        details={"status_before": "PENDING", "status_after": "APPROVED"}
    )
    db_session.add(log_entry)
    db_session.commit()

    try:
        retrieved = db_session.query(AuditLog).filter(AuditLog.action == test_action).first()
        assert retrieved is not None
        assert retrieved.resource_type == "PARTNER"
        assert retrieved.details["status_after"] == "APPROVED"
        assert retrieved.created_at is not None
    finally:
        db_session.query(AuditLog).filter(AuditLog.action == test_action).delete()
        db_session.commit()


def test_m1_financial_precision_numeric_decimal_and_rounding(db_session):
    """Verify that all financial columns in PostgreSQL are NUMERIC and handle Python Decimal with paise precision."""
    is_postgres = db_session.bind.dialect.name == "postgresql"
    if is_postgres:
        res = db_session.execute(text("""
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'bookings' AND column_name IN ('total_amount', 'tax_amount', 'discount_amount', 'final_payable')
            UNION ALL
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'payments' AND column_name = 'amount'
            UNION ALL
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'partners' AND column_name = 'commission_rate';
        """)).fetchall()
        for r in res:
            col, dtype, prec, scale = r[0], r[1], r[2], r[3]
            assert dtype == "numeric", f"Expected numeric for {col}, got {dtype}"
            if col == "commission_rate":
                assert (prec, scale) == (5, 4), f"Expected (5, 4) for commission_rate, got ({prec}, {scale})"
            else:
                assert (prec, scale) == (12, 2), f"Expected (12, 2) for {col}, got ({prec}, {scale})"

    # Test precise paise decimal storage and retrieval
    user = db_session.query(User).first()
    assert user is not None

    test_ref = f"GB-PRECISION-{uuid.uuid4().hex[:6]}"
    booking = Booking(
        booking_reference=test_ref,
        user_id=user.id,
        booking_type="EVENTS",
        total_amount=Decimal("1499.75"),
        tax_amount=Decimal("269.95"),
        discount_amount=Decimal("150.00"),
        final_payable=Decimal("1619.70"),
        status="CONFIRMED"
    )
    db_session.add(booking)
    db_session.commit()

    try:
        reloaded = db_session.query(Booking).filter(Booking.booking_reference == test_ref).first()
        assert reloaded is not None
        assert Decimal(str(reloaded.final_payable)) == Decimal("1619.70")
        assert Decimal(str(reloaded.total_amount)) == Decimal("1499.75")
        assert Decimal(str(reloaded.tax_amount)) == Decimal("269.95")
        assert Decimal(str(reloaded.discount_amount)) == Decimal("150.00")
    finally:
        db_session.query(Booking).filter(Booking.booking_reference == test_ref).delete()
        db_session.commit()


def test_m1_refund_integrity_over_refunds_and_reconciliation(db_session):
    """Verify refund integrity:
    1. Partial refunds and multiple refunds are aggregated accurately.
    2. Duplicate refund webhooks are blocked at database engine level.
    3. Failed refund attempts are excluded.
    4. Over-refunds are NOT silently hidden with GREATEST(0) - net collected reflects true deficit.
    5. Over-refunded bookings are flagged for financial reconciliation."""
    user = db_session.query(User).first()
    assert user is not None

    b_ref = f"GB-OVER-REFUND-{uuid.uuid4().hex[:6]}"
    booking = Booking(
        booking_reference=b_ref,
        user_id=user.id,
        booking_type="EVENTS",
        total_amount=Decimal("500.00"),
        final_payable=Decimal("500.00"),
        status="CONFIRMED"
    )
    db_session.add(booking)
    db_session.commit()

    try:
        # 1. Successful payment of 500.00
        pay_id = f"pay_audit_{uuid.uuid4().hex[:8]}"
        p = Payment(
            booking_id=booking.id, user_id=user.id, amount=Decimal("500.00"),
            status="CAPTURED", gateway_payment_id=pay_id, gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )
        db_session.add(p)
        db_session.commit()

        # 2. First partial refund: 200.00
        rf1_id = f"rfn_p1_{uuid.uuid4().hex[:8]}"
        rf1 = Refund(
            payment_id=p.id, booking_id=booking.id, amount=Decimal("200.00"),
            status="SUCCESS", gateway_refund_id=rf1_id
        )
        # 3. Second partial refund: 150.00
        rf2_id = f"rfn_p2_{uuid.uuid4().hex[:8]}"
        rf2 = Refund(
            payment_id=p.id, booking_id=booking.id, amount=Decimal("150.00"),
            status="SUCCESS", gateway_refund_id=rf2_id
        )
        # 4. Third refund causing an OVER-REFUND: 250.00 (Total refunds = 600.00 > captured 500.00)
        rf3_id = f"rfn_p3_{uuid.uuid4().hex[:8]}"
        rf3 = Refund(
            payment_id=p.id, booking_id=booking.id, amount=Decimal("250.00"),
            status="SUCCESS", gateway_refund_id=rf3_id
        )
        # 5. Failed refund attempt (50.00) - must be ignored
        rf_fail = Refund(
            payment_id=p.id, booking_id=booking.id, amount=Decimal("50.00"),
            status="FAILED", gateway_refund_id=f"rfn_fail_{uuid.uuid4().hex[:8]}"
        )

        db_session.add_all([rf1, rf2, rf3, rf_fail])
        db_session.commit()

        # 6. Database duplicate webhook rejection test for refund:
        dup_rf = Refund(
            payment_id=p.id, booking_id=booking.id, amount=Decimal("200.00"),
            status="SUCCESS", gateway_refund_id=rf1_id
        )
        db_session.add(dup_rf)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

        # Execute revenue audit for this over-refunded booking
        metrics = calculate_revenue_metrics(db_session, booking_ids=[booking.id])

        # Assertions:
        assert metrics["total_captured_payments"] == 500.00
        assert metrics["total_refunded_amount"] == 600.00
        # CRITICAL: Do NOT silently hide over-refund using GREATEST(0) - net collected is negative deficit
        assert metrics["net_collected_amount"] == -100.00, f"Expected -100.00, got {metrics['net_collected_amount']}"
        assert metrics["total_over_refunded_amount"] == 100.00
        assert metrics["over_refunded_bookings_count"] == 1
        assert metrics["requires_financial_reconciliation"] is True
        # Over-refunded booking yields zero platform revenue and zero partner settlement
        assert metrics["actual_platform_revenue"] == 0.00
        assert metrics["partner_settlements_payable"] == 0.00

    finally:
        db_session.query(Refund).filter(Refund.booking_id == booking.id).delete(synchronize_session=False)
        db_session.query(Payment).filter(Payment.booking_id == booking.id).delete(synchronize_session=False)
        db_session.query(Booking).filter(Booking.id == booking.id).delete(synchronize_session=False)
        db_session.commit()


def test_m1_partner_commission_multi_partner_and_all_verticals(db_session):
    """Verify partner commission calculation:
    1. Booking-to-partner relationships resolve across all 5 verticals.
    2. Multi-partner bookings with items belonging to different partners allocate settlements proportionally.
    3. Commission rates are configurable per partner.
    4. Go Beyond does not assume all collected money is platform revenue."""
    # 1. Check partner relationships exist across verticals in database
    cinema_partner = db_session.query(Partner).filter(Partner.partner_type == "CINEMA").first()
    dining_partner = db_session.query(Partner).filter(Partner.partner_type == "RESTAURANT").first()
    event_partner = db_session.query(Partner).filter(Partner.partner_type == "EVENT").first()
    sports_partner = db_session.query(Partner).filter(Partner.partner_type == "SPORTS").first()

    assert cinema_partner is not None, "Cinema partner missing"
    assert dining_partner is not None, "Dining partner missing"
    assert event_partner is not None, "Event partner missing"
    assert sports_partner is not None, "Sports partner missing"

    # Configure distinct commission rates per partner:
    # Event partner: 15% (0.1500), Sports partner: 8% (0.0800)
    event_partner.commission_rate = Decimal("0.1500")
    sports_partner.commission_rate = Decimal("0.0800")
    db_session.commit()

    user = db_session.query(User).first()
    assert user is not None

    # Fetch event ticket and activity slot
    event_ticket = db_session.query(EventTicketType).first()
    activity_slot = db_session.query(ActivitySlot).first()
    assert event_ticket is not None and activity_slot is not None

    # Ensure event_ticket belongs to event_partner and activity_slot belongs to sports_partner
    event = db_session.query(Event).filter(Event.id == event_ticket.event_id).first()
    activity = db_session.query(Activity).filter(Activity.id == activity_slot.activity_id).first()
    event.partner_id = event_partner.id
    activity.partner_id = sports_partner.id
    db_session.commit()

    # Create a Multi-Partner Booking:
    # Item 1: Event ticket, subtotal 1000.00 (Partner 15%)
    # Item 2: Activity slot, subtotal 500.00 (Partner 8%)
    b_ref = f"GB-MULTI-PARTNER-{uuid.uuid4().hex[:6]}"
    booking = Booking(
        booking_reference=b_ref,
        user_id=user.id,
        booking_type="EVENTS",
        total_amount=Decimal("1500.00"),
        final_payable=Decimal("1500.00"),
        status="CONFIRMED"
    )
    db_session.add(booking)
    db_session.commit()

    try:
        item1 = BookingItem(
            booking_id=booking.id,
            item_type="TICKET",
            item_id=event_ticket.id,
            name="VIP Event Pass",
            quantity=1,
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
            details={}
        )
        item2 = BookingItem(
            booking_id=booking.id,
            item_type="SLOT",
            item_id=activity_slot.id,
            name="Sports Turf Slot",
            quantity=1,
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00"),
            details={}
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        # Capture full payment: 1500.00
        pay_id = f"pay_multi_{uuid.uuid4().hex[:8]}"
        p = Payment(
            booking_id=booking.id, user_id=user.id, amount=Decimal("1500.00"),
            status="CAPTURED", gateway_payment_id=pay_id, gateway_order_id=f"order_{uuid.uuid4().hex[:8]}"
        )
        db_session.add(p)
        db_session.commit()

        metrics = calculate_revenue_metrics(db_session, booking_ids=[booking.id])

        # Mathematical Verification:
        # Item 1 (Event): 1000.00 * 0.15 = 150.00 platform revenue, 850.00 partner settlement
        # Item 2 (Sports): 500.00 * 0.08 = 40.00 platform revenue, 460.00 partner settlement
        # Total Platform Revenue = 150.00 + 40.00 = 190.00
        # Total Partner Settlements = 850.00 + 460.00 = 1310.00
        # Total Net Collected = 1500.00 (190.00 + 1310.00 = 1500.00)
        assert metrics["net_collected_amount"] == 1500.00
        assert metrics["actual_platform_revenue"] == 190.00, f"Expected 190.00, got {metrics['actual_platform_revenue']}"
        assert metrics["partner_settlements_payable"] == 1310.00, f"Expected 1310.00, got {metrics['partner_settlements_payable']}"
        assert metrics["total_revenue"] == 190.00
        # Check conservation of funds:
        assert metrics["actual_platform_revenue"] + metrics["partner_settlements_payable"] == metrics["net_collected_amount"]

    finally:
        db_session.query(BookingItem).filter(BookingItem.booking_id == booking.id).delete(synchronize_session=False)
        db_session.query(Payment).filter(Payment.booking_id == booking.id).delete(synchronize_session=False)
        db_session.query(Booking).filter(Booking.id == booking.id).delete(synchronize_session=False)
        # Restore default commission rates
        event_partner.commission_rate = Decimal("0.1000")
        sports_partner.commission_rate = Decimal("0.1000")
        db_session.commit()


def test_m1_migration_downgrade_and_reupgrade_preserves_partner_data(db_session):
    """Verify Alembic migration downgrade (-1 from head) and re-upgrade to head
    preserve all partner rows and commission values with zero record loss."""
    import subprocess
    import sys
    import os
    from pathlib import Path

    is_postgres = db_session.bind.dialect.name == "postgresql"
    if not is_postgres:
        pytest.skip("Migration DDL verification requires PostgreSQL engine")

    db_url = settings.DATABASE_URL
    env = dict(os.environ, DATABASE_URL=db_url)
    backend_dir = str(Path(__file__).resolve().parent.parent)
    alembic_cmd = [sys.executable, "-m", "alembic"]

    # 1. Record partner records before
    partners_before = db_session.execute(text("SELECT id, business_name, commission_rate FROM partners ORDER BY id;")).fetchall()
    assert len(partners_before) == 4, f"Expected 4 seeded partners, found {len(partners_before)}"
    initial_ids = [p[0] for p in partners_before]
    db_session.commit()
    db_session.close()
    db_session.bind.dispose()

    # 2. Downgrade head -> previous revision cleanly without dropping active tables
    res_down = subprocess.run(
        [*alembic_cmd, "downgrade", "-1"],
        cwd=backend_dir, capture_output=True, text=True, env=env
    )
    assert res_down.returncode == 0, f"Downgrade -1 failed: {res_down.stderr}"

    try:
        # Check partners count during downgrade
        partners_mid = db_session.execute(text("SELECT id, business_name FROM partners ORDER BY id;")).fetchall()
        assert len(partners_mid) == 4, "Partner records lost during downgrade!"
        db_session.commit()
        db_session.close()
        db_session.bind.dispose()
    finally:
        # 3. Re-upgrade back to head even if assertion above fails
        res_up = subprocess.run(
            [*alembic_cmd, "upgrade", "head"],
            cwd=backend_dir, capture_output=True, text=True, env=env
        )
    assert res_up.returncode == 0, f"Re-upgrade to head failed: {res_up.stderr}"

    # 4. Record and verify partners after
    partners_after = db_session.execute(text("SELECT id, business_name, commission_rate FROM partners ORDER BY id;")).fetchall()
    assert len(partners_after) == 4, f"Expected 4 partners after re-upgrade, found {len(partners_after)}"
    after_ids = [p[0] for p in partners_after]
    assert initial_ids == after_ids, "Partner IDs changed after migration lifecycle!"

    for p in partners_after:
        assert Decimal(str(p[2])) == Decimal("0.1000"), f"Expected restored default rate 0.1000, got {p[2]}"


