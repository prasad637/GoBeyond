from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(120), unique=True, index=True, nullable=False)
    type = Column(String(20), default="LOCALITY", nullable=False)  # 'CITY' or 'LOCALITY'
    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    state = Column(String(100), default="Telangana", nullable=False)
    country = Column(String(100), default="India", nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    parent = relationship("Location", remote_side=[id], backref="sub_locations")

