import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class NotificationPreference(Base, TimestampMixin):
    """
    Customer notification preferences.
    Distinguishes transactional alerts (booking, payment, security) from marketing communications.
    """
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    email_enabled = Column(Boolean, default=True, nullable=False)
    sms_enabled = Column(Boolean, default=True, nullable=False)
    push_enabled = Column(Boolean, default=True, nullable=False)
    in_app_enabled = Column(Boolean, default=True, nullable=False)
    booking_alerts = Column(Boolean, default=True, nullable=False)
    payment_alerts = Column(Boolean, default=True, nullable=False)
    marketing_enabled = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="notification_preference")


class NotificationOutbox(Base, TimestampMixin):
    """
    Durable PostgreSQL Outbox table for asynchronous notification dispatch.
    Ensures zero notification loss during Redis or worker downtime.
    Supports idempotency, exponential backoff retries, and dead-letter queuing.
    """
    __tablename__ = "notification_outbox"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(50), nullable=False, index=True)  # EMAIL, SMS, PUSH, IN_APP
    recipient = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False, index=True)  # PENDING, PROCESSING, DELIVERED, FAILED, DEAD_LETTER, SKIPPED
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    provider_name = Column(String(100), default="MOCK_PROVIDER", nullable=False)
    provider_metadata = Column(JSON, default=dict)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    is_marketing = Column(Boolean, default=False, nullable=False)
    payload = Column(JSON, default=dict)

    user = relationship("User", back_populates="outbox_notifications")

    __table_args__ = (
        Index("ix_notification_outbox_status_next_retry", "status", "next_retry_at"),
    )

