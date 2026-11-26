import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Partner(Base, TimestampMixin):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    business_name = Column(String(255), nullable=False)
    partner_type = Column(String(50), nullable=False)  # RESTAURANT, CINEMA, EVENT, SPORTS, ACTIVITIES
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    gstin = Column(String(50), nullable=True)
    pan_number = Column(String(20), nullable=True)
    commission_rate = Column(Numeric(5, 4), default=Decimal("0.1000"), server_default="0.1000", nullable=False)
    status = Column(String(50), default="PENDING_VERIFICATION", nullable=False)  # PENDING_VERIFICATION, APPROVED, REJECTED, SUSPENDED
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="partner")
    verifier = relationship("User", foreign_keys=[verified_by])
    documents = relationship("PartnerDocument", back_populates="partner", cascade="all, delete-orphan")
    restaurants = relationship("Restaurant", back_populates="partner")
    cinemas = relationship("Cinema", back_populates="partner")
    events = relationship("Event", back_populates="partner")
    sports_venues = relationship("SportsVenue", back_populates="partner")
    activities = relationship("Activity", back_populates="partner")


class PartnerDocument(Base, TimestampMixin):
    __tablename__ = "partner_documents"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(50), nullable=False)  # GST, PAN, FSSAI, TRADE_LICENSE, ID_PROOF
    document_url = Column(String(500), nullable=False)
    status = Column(String(50), default="SUBMITTED", nullable=False)  # SUBMITTED, VERIFIED, REJECTED
    uploaded_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

    partner = relationship("Partner", back_populates="documents")

