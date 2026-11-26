import uuid
import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    account_status = Column(String(50), default="ACTIVE", server_default="ACTIVE", nullable=False)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    partner = relationship("Partner", back_populates="user", uselist=False, foreign_keys="[Partner.user_id]")
    bookings = relationship("Booking", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    notification_preference = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    outbox_notifications = relationship("NotificationOutbox", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    city_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    locality_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    preferred_language = Column(String(50), default="English")
    bio = Column(Text, nullable=True)
    emergency_phone = Column(String(20), nullable=True)

    user = relationship("User", back_populates="profile")
    city = relationship("Location", foreign_keys=[city_id])
    locality = relationship("Location", foreign_keys=[locality_id])


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)  # customer, partner_restaurant, etc.
    description = Column(String(255), nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(String(255), nullable=True)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    family_id = Column(String(36), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="refresh_tokens")
