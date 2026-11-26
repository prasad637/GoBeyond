from decimal import Decimal
from sqlalchemy import Column, Integer, String, Boolean, Float, Numeric, ForeignKey, Date, Time, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Movie(Base, TimestampMixin):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(280), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    language = Column(String(50), nullable=False)  # Telugu, Hindi, English, Tamil
    genre = Column(String(100), nullable=False)  # Action, Drama, Sci-Fi, Thriller
    censor_rating = Column(String(10), default="UA", nullable=False)  # U, UA, A
    release_date = Column(Date, nullable=False)
    poster_url = Column(String(500), nullable=True)
    backdrop_url = Column(String(500), nullable=True)
    trailer_url = Column(String(500), nullable=True)
    rating = Column(Float, default=0.0, nullable=False)
    vote_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    shows = relationship("MovieShow", back_populates="movie", cascade="all, delete-orphan")


class Cinema(Base, TimestampMixin):
    __tablename__ = "cinemas"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    city = Column(String(100), default="Hyderabad", nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    amenities = Column(JSON, default=list)  # ["Dolby Atmos", "4K Projection", "Recliners", "Food Court"]
    is_active = Column(Boolean, default=True, nullable=False)

    partner = relationship("Partner", back_populates="cinemas")
    location = relationship("Location")
    screens = relationship("Screen", back_populates="cinema", cascade="all, delete-orphan")


class Screen(Base, TimestampMixin):
    __tablename__ = "screens"

    id = Column(Integer, primary_key=True, index=True)
    cinema_id = Column(Integer, ForeignKey("cinemas.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)  # Screen 1, Audi 2 IMAX
    screen_type = Column(String(50), default="2D", nullable=False)  # 2D, 3D, IMAX 3D, 4DX
    total_seats = Column(Integer, default=0, nullable=False)

    cinema = relationship("Cinema", back_populates="screens")
    seats = relationship("Seat", back_populates="screen", cascade="all, delete-orphan")
    shows = relationship("MovieShow", back_populates="screen", cascade="all, delete-orphan")


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    screen_id = Column(Integer, ForeignKey("screens.id", ondelete="CASCADE"), nullable=False)
    row_code = Column(String(5), nullable=False)  # A, B, C, ...
    seat_number = Column(Integer, nullable=False)  # 1, 2, 3, ...
    tier = Column(String(50), default="CLASSIC", nullable=False)  # CLASSIC, PREMIUM, RECLINER
    base_price = Column(Numeric(12, 2), default=Decimal("200.00"), nullable=False)
    is_accessible = Column(Boolean, default=False, nullable=False)

    screen = relationship("Screen", back_populates="seats")


class MovieShow(Base, TimestampMixin):
    __tablename__ = "movie_shows"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    screen_id = Column(Integer, ForeignKey("screens.id", ondelete="CASCADE"), nullable=False)
    show_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    price_multiplier = Column(Numeric(4, 2), default=Decimal("1.00"), nullable=False)
    status = Column(String(50), default="SCHEDULED", nullable=False)  # SCHEDULED, HOUSEFULL, CANCELLED, COMPLETED

    movie = relationship("Movie", back_populates="shows")
    screen = relationship("Screen", back_populates="shows")

