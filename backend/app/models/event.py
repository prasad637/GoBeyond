from sqlalchemy import Column, Integer, String, Boolean, Float, Numeric, ForeignKey, DateTime, Text, JSON, CheckConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    title = Column(String(255), nullable=False)
    slug = Column(String(280), unique=True, index=True, nullable=False)
    category = Column(String(100), nullable=False)  # CONCERT, COMEDY, FESTIVAL, THEATRE, WORKSHOP
    description = Column(Text, nullable=True)
    artist_names = Column(String(255), nullable=True)
    venue_name = Column(String(255), nullable=False)
    venue_address = Column(String(500), nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    banner_url = Column(String(500), nullable=True)
    is_featured = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    partner = relationship("Partner", back_populates="events")
    location = relationship("Location")
    ticket_types = relationship("EventTicketType", back_populates="event", cascade="all, delete-orphan")


class EventTicketType(Base, TimestampMixin):
    __tablename__ = "event_ticket_types"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)  # Early Bird, General Admission, VIP Lounge
    description = Column(String(255), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    total_quantity = Column(Integer, nullable=False)
    available_quantity = Column(Integer, nullable=False)
    max_per_booking = Column(Integer, default=10, nullable=False)

    event = relationship("Event", back_populates="ticket_types")

    __table_args__ = (
        CheckConstraint("available_quantity >= 0 AND available_quantity <= total_quantity", name="chk_ticket_quantity_valid"),
    )

