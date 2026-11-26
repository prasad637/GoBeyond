import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, Role
from app.models.sports import Activity, ActivitySlot
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.audit import AuditLog, Notification
from app.models.notification import NotificationOutbox
from app.core.security import get_password_hash


def test_production_settings_reject_missing_or_insecure_secrets():
    """
    Production mode MUST fail fast when SECRET_KEY is empty, short, or uses known placeholder markers,
    and MUST reject live Razorpay mode without credentials.
    """
    # 1. Missing SECRET_KEY in production
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="")

    # 2. Known insecure placeholder marker in production
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="gobeyond-super-secret-jwt-key-for-development-change-in-production-2026",
        )

    # 3. Too short SECRET_KEY in production
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="short-key")

    # 4. Non-sandbox Razorpay in production without credentials
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="x" * 48,
            RAZORPAY_SANDBOX_MODE=False,
            RAZORPAY_KEY_ID="",
            RAZORPAY_KEY_SECRET="",
        )

    # 5. Valid production configuration passes
    prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="v" * 48,
        RAZORPAY_SANDBOX_MODE=True,
        RAZORPAY_KEY_ID="rzp_test_valid_id",
        RAZORPAY_KEY_SECRET="valid_test_secret_value",
    )
    assert prod.SECRET_KEY == "v" * 48


def test_sports_activity_slot_pricing_not_doubled():
    """
    Regression test for Module 11 fix in BookingEngineService:
    Ensures SPORTS / ACTIVITY slot bookings charge exactly 1x (unit_price * quantity) + 18% GST,
    matching booking_items.subtotal and frontend checkout preview.
    """
    db: Session = SessionLocal()
    created_booking_id = None
    slot = None
    orig_booked = 0
    user = None
    try:
        role = db.query(Role).filter(Role.name == "customer").first()
        uid = uuid.uuid4().hex[:8]
        user = User(
            email=f"pricing_{uid}@gobeyond.test",
            phone=f"+9196{uid[:8].ljust(8, '4')}",
            full_name="Pricing Check User",
            hashed_password=get_password_hash("Password@123"),
            is_active=True,
            account_status="ACTIVE",
        )
        if role:
            user.roles.append(role)
        db.add(user)
        db.commit()
        db.refresh(user)

        slot = (
            db.query(ActivitySlot)
            .join(Activity)
            .filter(ActivitySlot.is_available == True, (ActivitySlot.capacity - ActivitySlot.booked_count) >= 1)
            .first()
        )
        assert slot is not None, "Expected at least one available ActivitySlot in database"
        orig_booked = slot.booked_count
        expected_unit = Decimal(str(slot.price_override if slot.price_override is not None else slot.activity.base_price)).quantize(Decimal("0.01"))
        expected_subtotal = expected_unit * 1
        expected_tax = (expected_subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        expected_final = (expected_subtotal + expected_tax).quantize(Decimal("0.01"))

        token = create_access_token(subject=str(user.id), role="customer")
        with TestClient(app) as client:
            res = client.post(
                "/api/v1/bookings/",
                json={
                    "booking_type": "ACTIVITY",
                    "items": [
                        {
                            "item_type": "SLOT",
                            "item_id": slot.id,
                            "name": f"{slot.activity.title}",
                            "quantity": 1,
                            "unit_price": float(expected_unit),
                            "details": {"activity_id": slot.activity_id},
                        }
                    ],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        assert res.status_code in [200, 201], res.text
        data = res.json()
        created_booking_id = data["id"]

        assert Decimal(str(data["total_amount"])).quantize(Decimal("0.01")) == expected_subtotal
        assert Decimal(str(data["tax_amount"])).quantize(Decimal("0.01")) == expected_tax
        assert Decimal(str(data["final_payable"])).quantize(Decimal("0.01")) == expected_final
    finally:
        if created_booking_id:
            db.query(BookingItem).filter(BookingItem.booking_id == created_booking_id).delete()
            db.query(Booking).filter(Booking.id == created_booking_id).delete()
        if slot:
            slot_row = db.query(ActivitySlot).filter(ActivitySlot.id == slot.id).first()
            if slot_row:
                slot_row.booked_count = orig_booked
        if user:
            db.query(SeatLock).filter(SeatLock.user_id == user.id).delete()
            db.query(NotificationOutbox).filter(NotificationOutbox.user_id == user.id).delete()
            db.query(Notification).filter(Notification.user_id == user.id).delete()
            db.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
            db.refresh(user)
            user.roles.clear()
            db.delete(user)
        db.commit()
        db.close()

