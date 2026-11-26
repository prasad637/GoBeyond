import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Boolean, Float, Numeric, ForeignKey, DateTime, Text, JSON, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_reference = Column(String(50), unique=True, index=True, nullable=False)  # e.g. GB-2026-HYD-12345
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    booking_type = Column(String(50), nullable=False)  # MOVIE, DINING, EVENT, SPORTS, ACTIVITY
    total_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    tax_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    final_payable = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)
    # PENDING, LOCKED, PAYMENT_PENDING, CONFIRMED, FAILED, CANCELLED, EXPIRED, REFUND_PENDING, REFUNDED
    qr_code_token = Column(String(255), unique=True, index=True, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="bookings")
    coupon = relationship("Coupon")
    items = relationship("BookingItem", back_populates="booking", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")


class BookingItem(Base, TimestampMixin):
    __tablename__ = "booking_items"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String(50), nullable=False)  # SEAT, TICKET, TABLE, SLOT
    item_id = Column(Integer, nullable=False)  # ID in source table (e.g. seat_id, ticket_type_id, table_id, slot_id)
    name = Column(String(255), nullable=False)  # "A12 - Classic", "VIP Lounge Pass", etc.
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    subtotal = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    details = Column(JSON, default=dict)  # Metadata, e.g. row, seat_no, show_time, event_title

    booking = relationship("Booking", back_populates="items")


class SeatLock(Base):
    __tablename__ = "seat_locks"

    id = Column(Integer, primary_key=True, index=True)
    resource_type = Column(String(50), nullable=False)  # MOVIE_SHOW, DINING_TABLE, ACTIVITY_SLOT
    resource_id = Column(Integer, nullable=False)  # show_id, table_id, slot_id
    identifier = Column(String(100), nullable=False)  # e.g. "A12" or "Table_4"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lock_token = Column(String(100), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_released = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    __table_args__ = (
        Index(
            "uq_active_resource_lock",
            "resource_type",
            "resource_id",
            "identifier",
            unique=True,
            postgresql_where=(Column("is_released") == False),
            sqlite_where=(Column("is_released") == False),
        ),
    )

