"""initial_schema_32_tables

Revision ID: 120cd1ac8c2f
Revises: 
Create Date: 2026-11-05 13:55:47.453622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '120cd1ac8c2f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('phone', sa.String(length=20), nullable=False),
            sa.Column('full_name', sa.String(length=255), nullable=False),
            sa.Column('hashed_password', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
        op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)

    if 'roles' not in tables:
        op.create_table(
            'roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_roles_id'), 'roles', ['id'], unique=False)
        op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    if 'permissions' not in tables:
        op.create_table(
            'permissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_permissions_id'), 'permissions', ['id'], unique=False)
        op.create_index(op.f('ix_permissions_code'), 'permissions', ['code'], unique=True)

    if 'user_roles' not in tables:
        op.create_table(
            'user_roles',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('user_id', 'role_id'),
        )

    if 'role_permissions' not in tables:
        op.create_table(
            'role_permissions',
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('permission_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('role_id', 'permission_id'),
        )

    if 'locations' not in tables:
        op.create_table(
            'locations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('slug', sa.String(length=120), nullable=False),
            sa.Column('type', sa.String(length=20), nullable=False),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('state', sa.String(length=100), nullable=False),
            sa.Column('country', sa.String(length=100), nullable=False),
            sa.Column('latitude', sa.Float(), nullable=True),
            sa.Column('longitude', sa.Float(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['parent_id'], ['locations.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_locations_id'), 'locations', ['id'], unique=False)
        op.create_index(op.f('ix_locations_slug'), 'locations', ['slug'], unique=True)

    if 'user_profiles' not in tables:
        op.create_table(
            'user_profiles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('avatar_url', sa.String(length=500), nullable=True),
            sa.Column('city_id', sa.Integer(), nullable=True),
            sa.Column('preferred_language', sa.String(length=50), nullable=True),
            sa.Column('bio', sa.Text(), nullable=True),
            sa.Column('emergency_phone', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['city_id'], ['locations.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id'),
        )
        op.create_index(op.f('ix_user_profiles_id'), 'user_profiles', ['id'], unique=False)

    if 'partners' not in tables:
        op.create_table(
            'partners',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('business_name', sa.String(length=255), nullable=False),
            sa.Column('partner_type', sa.String(length=50), nullable=False),
            sa.Column('contact_email', sa.String(length=255), nullable=False),
            sa.Column('contact_phone', sa.String(length=20), nullable=False),
            sa.Column('gstin', sa.String(length=50), nullable=True),
            sa.Column('pan_number', sa.String(length=20), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('verified_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id'),
        )
        op.create_index(op.f('ix_partners_id'), 'partners', ['id'], unique=False)

    if 'partner_documents' not in tables:
        op.create_table(
            'partner_documents',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('partner_id', sa.Integer(), nullable=False),
            sa.Column('document_type', sa.String(length=50), nullable=False),
            sa.Column('document_url', sa.String(length=500), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('uploaded_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_partner_documents_id'), 'partner_documents', ['id'], unique=False)

    if 'movies' not in tables:
        op.create_table(
            'movies',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=280), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('duration_minutes', sa.Integer(), nullable=False),
            sa.Column('language', sa.String(length=50), nullable=False),
            sa.Column('genre', sa.String(length=100), nullable=False),
            sa.Column('censor_rating', sa.String(length=10), nullable=False),
            sa.Column('release_date', sa.Date(), nullable=False),
            sa.Column('poster_url', sa.String(length=500), nullable=True),
            sa.Column('backdrop_url', sa.String(length=500), nullable=True),
            sa.Column('trailer_url', sa.String(length=500), nullable=True),
            sa.Column('rating', sa.Float(), nullable=False),
            sa.Column('vote_count', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_movies_id'), 'movies', ['id'], unique=False)
        op.create_index(op.f('ix_movies_slug'), 'movies', ['slug'], unique=True)

    if 'cinemas' not in tables:
        op.create_table(
            'cinemas',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('partner_id', sa.Integer(), nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('address', sa.String(length=500), nullable=False),
            sa.Column('city', sa.String(length=100), nullable=False),
            sa.Column('latitude', sa.Float(), nullable=True),
            sa.Column('longitude', sa.Float(), nullable=True),
            sa.Column('amenities', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
            sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_cinemas_id'), 'cinemas', ['id'], unique=False)

    if 'screens' not in tables:
        op.create_table(
            'screens',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('cinema_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('screen_type', sa.String(length=50), nullable=False),
            sa.Column('total_seats', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['cinema_id'], ['cinemas.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_screens_id'), 'screens', ['id'], unique=False)

    if 'seats' not in tables:
        op.create_table(
            'seats',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('screen_id', sa.Integer(), nullable=False),
            sa.Column('row_code', sa.String(length=5), nullable=False),
            sa.Column('seat_number', sa.Integer(), nullable=False),
            sa.Column('tier', sa.String(length=50), nullable=False),
            sa.Column('base_price', sa.Float(), nullable=False),
            sa.Column('is_accessible', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.ForeignKeyConstraint(['screen_id'], ['screens.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_seats_id'), 'seats', ['id'], unique=False)

    if 'movie_shows' not in tables:
        op.create_table(
            'movie_shows',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('movie_id', sa.Integer(), nullable=False),
            sa.Column('screen_id', sa.Integer(), nullable=False),
            sa.Column('show_date', sa.Date(), nullable=False),
            sa.Column('start_time', sa.Time(), nullable=False),
            sa.Column('end_time', sa.Time(), nullable=False),
            sa.Column('price_multiplier', sa.Float(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['movie_id'], ['movies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['screen_id'], ['screens.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_movie_shows_id'), 'movie_shows', ['id'], unique=False)

    if 'restaurants' not in tables:
        op.create_table(
            'restaurants',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('partner_id', sa.Integer(), nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=280), nullable=False),
            sa.Column('cuisines', sa.JSON(), nullable=True),
            sa.Column('cost_for_two', sa.Integer(), nullable=False),
            sa.Column('address', sa.String(length=500), nullable=False),
            sa.Column('phone', sa.String(length=20), nullable=False),
            sa.Column('timings', sa.String(length=100), nullable=False),
            sa.Column('images', sa.JSON(), nullable=True),
            sa.Column('rating', sa.Float(), nullable=False),
            sa.Column('review_count', sa.Integer(), nullable=False),
            sa.Column('has_buffet', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('has_alcohol', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_pure_veg', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
            sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_restaurants_id'), 'restaurants', ['id'], unique=False)
        op.create_index(op.f('ix_restaurants_slug'), 'restaurants', ['slug'], unique=True)

    if 'restaurant_menus' not in tables:
        op.create_table(
            'restaurant_menus',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('restaurant_id', sa.Integer(), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('item_name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('price', sa.Float(), nullable=False),
            sa.Column('is_veg', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('is_bestseller', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('image_url', sa.String(length=500), nullable=True),
            sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_restaurant_menus_id'), 'restaurant_menus', ['id'], unique=False)

    if 'dining_tables' not in tables:
        op.create_table(
            'dining_tables',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('restaurant_id', sa.Integer(), nullable=False),
            sa.Column('table_number', sa.String(length=50), nullable=False),
            sa.Column('capacity', sa.Integer(), nullable=False),
            sa.Column('zone', sa.String(length=100), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_dining_tables_id'), 'dining_tables', ['id'], unique=False)

    if 'coupons' not in tables:
        op.create_table(
            'coupons',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('discount_type', sa.String(length=20), nullable=False),
            sa.Column('discount_value', sa.Float(), nullable=False),
            sa.Column('min_order_value', sa.Float(), nullable=False),
            sa.Column('max_discount', sa.Float(), nullable=False),
            sa.Column('valid_from', sa.DateTime(), nullable=True),
            sa.Column('valid_until', sa.DateTime(), nullable=True),
            sa.Column('usage_limit', sa.Integer(), nullable=False),
            sa.Column('used_count', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_coupons_id'), 'coupons', ['id'], unique=False)
        op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=True)

    if 'bookings' not in tables:
        op.create_table(
            'bookings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('booking_reference', sa.String(length=50), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('booking_type', sa.String(length=50), nullable=False),
            sa.Column('total_amount', sa.Float(), nullable=False),
            sa.Column('tax_amount', sa.Float(), nullable=False),
            sa.Column('discount_amount', sa.Float(), nullable=False),
            sa.Column('final_payable', sa.Float(), nullable=False),
            sa.Column('coupon_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('qr_code_token', sa.String(length=255), nullable=True),
            sa.Column('cancellation_reason', sa.Text(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['coupon_id'], ['coupons.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_bookings_id'), 'bookings', ['id'], unique=False)
        op.create_index(op.f('ix_bookings_booking_reference'), 'bookings', ['booking_reference'], unique=True)
        op.create_index(op.f('ix_bookings_qr_code_token'), 'bookings', ['qr_code_token'], unique=True)

    if 'dining_reservations' not in tables:
        op.create_table(
            'dining_reservations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('restaurant_id', sa.Integer(), nullable=False),
            sa.Column('table_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('booking_id', sa.Integer(), nullable=True),
            sa.Column('reservation_date', sa.Date(), nullable=False),
            sa.Column('reservation_time', sa.Time(), nullable=False),
            sa.Column('guest_count', sa.Integer(), nullable=False),
            sa.Column('special_requests', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['table_id'], ['dining_tables.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_dining_reservations_id'), 'dining_reservations', ['id'], unique=False)

    if 'booking_items' not in tables:
        op.create_table(
            'booking_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('booking_id', sa.Integer(), nullable=False),
            sa.Column('item_type', sa.String(length=50), nullable=False),
            sa.Column('item_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.Column('unit_price', sa.Float(), nullable=False),
            sa.Column('subtotal', sa.Float(), nullable=False),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_booking_items_id'), 'booking_items', ['id'], unique=False)

    if 'seat_locks' not in tables:
        op.create_table(
            'seat_locks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('resource_type', sa.String(length=50), nullable=False),
            sa.Column('resource_id', sa.Integer(), nullable=False),
            sa.Column('identifier', sa.String(length=100), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('lock_token', sa.String(length=100), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('is_released', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_seat_locks_id'), 'seat_locks', ['id'], unique=False)

    if 'events' not in tables:
        op.create_table(
            'events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('partner_id', sa.Integer(), nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=280), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('artist_names', sa.String(length=255), nullable=True),
            sa.Column('venue_name', sa.String(length=255), nullable=False),
            sa.Column('venue_address', sa.String(length=500), nullable=False),
            sa.Column('start_datetime', sa.DateTime(), nullable=False),
            sa.Column('end_datetime', sa.DateTime(), nullable=False),
            sa.Column('banner_url', sa.String(length=500), nullable=True),
            sa.Column('is_featured', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
            sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_events_id'), 'events', ['id'], unique=False)
        op.create_index(op.f('ix_events_slug'), 'events', ['slug'], unique=True)

    if 'event_ticket_types' not in tables:
        op.create_table(
            'event_ticket_types',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('event_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('price', sa.Float(), nullable=False),
            sa.Column('total_quantity', sa.Integer(), nullable=False),
            sa.Column('available_quantity', sa.Integer(), nullable=False),
            sa.Column('max_per_booking', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_event_ticket_types_id'), 'event_ticket_types', ['id'], unique=False)

    if 'sports_venues' not in tables:
        op.create_table(
            'sports_venues',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('partner_id', sa.Integer(), nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('sport_types', sa.JSON(), nullable=True),
            sa.Column('address', sa.String(length=500), nullable=False),
            sa.Column('amenities', sa.JSON(), nullable=True),
            sa.Column('images', sa.JSON(), nullable=True),
            sa.Column('rating', sa.Float(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
            sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_sports_venues_id'), 'sports_venues', ['id'], unique=False)

    if 'activities' not in tables:
        op.create_table(
            'activities',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('partner_id', sa.Integer(), nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=False),
            sa.Column('venue_id', sa.Integer(), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=280), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('base_price', sa.Float(), nullable=False),
            sa.Column('duration_minutes', sa.Integer(), nullable=False),
            sa.Column('image_url', sa.String(length=500), nullable=True),
            sa.Column('min_age', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
            sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['venue_id'], ['sports_venues.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_activities_id'), 'activities', ['id'], unique=False)
        op.create_index(op.f('ix_activities_slug'), 'activities', ['slug'], unique=True)

    if 'activity_slots' not in tables:
        op.create_table(
            'activity_slots',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('activity_id', sa.Integer(), nullable=False),
            sa.Column('slot_date', sa.Date(), nullable=False),
            sa.Column('start_time', sa.Time(), nullable=False),
            sa.Column('end_time', sa.Time(), nullable=False),
            sa.Column('capacity', sa.Integer(), nullable=False),
            sa.Column('booked_count', sa.Integer(), nullable=False),
            sa.Column('price_override', sa.Float(), nullable=True),
            sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_activity_slots_id'), 'activity_slots', ['id'], unique=False)

    if 'payments' not in tables:
        op.create_table(
            'payments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('booking_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('payment_gateway', sa.String(length=50), nullable=False),
            sa.Column('gateway_order_id', sa.String(length=100), nullable=True),
            sa.Column('gateway_payment_id', sa.String(length=100), nullable=True),
            sa.Column('gateway_signature', sa.String(length=255), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=10), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('raw_payload', sa.JSON(), nullable=True),
            sa.Column('idempotency_key', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
        op.create_index(op.f('ix_payments_gateway_order_id'), 'payments', ['gateway_order_id'], unique=True)
        op.create_index(op.f('ix_payments_gateway_payment_id'), 'payments', ['gateway_payment_id'], unique=True)
        op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=True)

    if 'refunds' not in tables:
        op.create_table(
            'refunds',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('payment_id', sa.Integer(), nullable=False),
            sa.Column('booking_id', sa.Integer(), nullable=False),
            sa.Column('gateway_refund_id', sa.String(length=100), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('reason', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_refunds_id'), 'refunds', ['id'], unique=False)
        op.create_index(op.f('ix_refunds_gateway_refund_id'), 'refunds', ['gateway_refund_id'], unique=True)

    if 'reviews' not in tables:
        op.create_table(
            'reviews',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('target_type', sa.String(length=50), nullable=False),
            sa.Column('target_id', sa.Integer(), nullable=False),
            sa.Column('rating', sa.Float(), nullable=False),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_reviews_id'), 'reviews', ['id'], unique=False)

    if 'notifications' not in tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('data', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)

    if 'audit_logs' not in tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('resource_type', sa.String(length=50), nullable=False),
            sa.Column('resource_id', sa.String(length=100), nullable=True),
            sa.Column('ip_address', sa.String(length=50), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name in [
        'audit_logs',
        'notifications',
        'reviews',
        'refunds',
        'payments',
        'activity_slots',
        'activities',
        'sports_venues',
        'event_ticket_types',
        'events',
        'seat_locks',
        'booking_items',
        'dining_reservations',
        'bookings',
        'coupons',
        'dining_tables',
        'restaurant_menus',
        'restaurants',
        'movie_shows',
        'seats',
        'screens',
        'cinemas',
        'movies',
        'partner_documents',
        'partners',
        'user_profiles',
        'locations',
        'role_permissions',
        'user_roles',
        'permissions',
        'roles',
        'users',
    ]:
        if table_name in tables:
            op.drop_table(table_name)
