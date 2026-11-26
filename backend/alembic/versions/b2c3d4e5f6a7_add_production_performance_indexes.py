"""add_production_performance_indexes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-09 02:40:00.000000

Phase 1 Module 10 migration: Adds justified performance indexes on foreign keys
and frequently queried filter columns across bookings, payments, and all five verticals.
Fully reversible.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES_TO_CREATE = [
    # Bookings & Items
    ("ix_bookings_user_id", "bookings", ["user_id"]),
    ("ix_bookings_status", "bookings", ["status"]),
    ("ix_bookings_created_at", "bookings", ["created_at"]),
    ("ix_bookings_user_id_status", "bookings", ["user_id", "status"]),
    ("ix_booking_items_booking_id", "booking_items", ["booking_id"]),

    # Payments
    ("ix_payments_booking_id", "payments", ["booking_id"]),
    ("ix_payments_status", "payments", ["status"]),

    # Discovery & Vertical Listings
    ("ix_restaurants_location_id", "restaurants", ["location_id"]),
    ("ix_restaurants_partner_id", "restaurants", ["partner_id"]),
    ("ix_cinemas_location_id", "cinemas", ["location_id"]),
    ("ix_cinemas_partner_id", "cinemas", ["partner_id"]),
    ("ix_events_location_id", "events", ["location_id"]),
    ("ix_events_partner_id", "events", ["partner_id"]),
    ("ix_events_start_datetime", "events", ["start_datetime"]),
    ("ix_sports_venues_location_id", "sports_venues", ["location_id"]),
    ("ix_sports_venues_partner_id", "sports_venues", ["partner_id"]),
    ("ix_activities_location_id", "activities", ["location_id"]),
    ("ix_activities_partner_id", "activities", ["partner_id"]),
    ("ix_movie_shows_movie_id", "movie_shows", ["movie_id"]),
    ("ix_movie_shows_screen_id", "movie_shows", ["screen_id"]),
    ("ix_movie_shows_show_date", "movie_shows", ["show_date"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for idx_name, table_name, columns in INDEXES_TO_CREATE:
        existing_indexes = [idx["name"] for idx in insp.get_indexes(table_name)]
        if idx_name not in existing_indexes:
            try:
                op.create_index(idx_name, table_name, columns, unique=False)
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for idx_name, table_name, _ in reversed(INDEXES_TO_CREATE):
        existing_indexes = [idx["name"] for idx in insp.get_indexes(table_name)]
        if idx_name in existing_indexes:
            try:
                op.drop_index(idx_name, table_name=table_name)
            except Exception:
                pass

