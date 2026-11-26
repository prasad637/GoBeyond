import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String(50), nullable=False)  # RESTAURANT, MOVIE, EVENT, SPORTS, ACTIVITY
    target_id = Column(Integer, nullable=False)
    rating = Column(Float, nullable=False)  # 1.0 to 5.0
    comment = Column(Text, nullable=True)

    user = relationship("User", back_populates="reviews")


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="INFO", nullable=False)  # BOOKING_CONFIRMATION, PAYMENT_UPDATE, REMINDER, PROMOTION
    is_read = Column(Boolean, default=False, nullable=False)
    data = Column(JSON, default=dict)

    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # PARTNER_APPROVAL, PRICE_UPDATE, BOOKING_REFUND, etc.
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    user = relationship("User")

