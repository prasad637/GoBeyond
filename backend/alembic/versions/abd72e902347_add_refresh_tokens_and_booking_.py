"""add_refresh_tokens_and_booking_integrity_constraints

Revision ID: abd72e902347
Revises: 120cd1ac8c2f
Create Date: 2026-11-05 17:05:54.764612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abd72e902347'
down_revision: Union[str, None] = '120cd1ac8c2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Refresh Tokens Table
    if 'refresh_tokens' not in tables:
        op.create_table(
            'refresh_tokens',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('family_id', sa.String(length=36), nullable=False),
            sa.Column('is_revoked', sa.Boolean(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_refresh_tokens_family_id'), 'refresh_tokens', ['family_id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
        op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    # 2. Dining Reservations Time Range Columns
    dining_cols = [c['name'] for c in inspector.get_columns('dining_reservations')]
    if 'duration_minutes' not in dining_cols:
        op.add_column('dining_reservations', sa.Column('duration_minutes', sa.Integer(), server_default='90', nullable=False))
    if 'buffer_minutes' not in dining_cols:
        op.add_column('dining_reservations', sa.Column('buffer_minutes', sa.Integer(), server_default='15', nullable=False))
    if 'start_datetime' not in dining_cols:
        op.add_column('dining_reservations', sa.Column('start_datetime', sa.DateTime(), nullable=True))
    if 'end_datetime' not in dining_cols:
        op.add_column('dining_reservations', sa.Column('end_datetime', sa.DateTime(), nullable=True))

    # Populate start_datetime and end_datetime for any pre-existing rows
    if is_postgres:
        op.execute("""
            UPDATE dining_reservations
            SET start_datetime = (reservation_date + reservation_time),
                end_datetime = (reservation_date + reservation_time) + (COALESCE(duration_minutes, 90) + COALESCE(buffer_minutes, 15)) * INTERVAL '1 minute'
            WHERE start_datetime IS NULL AND reservation_date IS NOT NULL AND reservation_time IS NOT NULL;
        """)

    # 3. Dining Reservations Constraints: PostgreSQL GiST Exclusion vs SQLite Partial Index
    if is_postgres:
        # PostgreSQL-only: Enable btree_gist extension and add GiST Exclusion Constraint
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'exclude_overlapping_dining_reservations'
                ) THEN
                    ALTER TABLE dining_reservations
                    ADD CONSTRAINT exclude_overlapping_dining_reservations
                    EXCLUDE USING gist (
                        table_id WITH =,
                        tsrange(start_datetime, end_datetime) WITH &&
                    ) WHERE (status IN ('PENDING', 'CONFIRMED', 'SEATED') AND start_datetime IS NOT NULL AND end_datetime IS NOT NULL);
                END IF;
            END $$;
        """)
    else:
        # SQLite-compatible fallback: partial B-Tree unique index
        dining_indexes = [idx['name'] for idx in inspector.get_indexes('dining_reservations')]
        if 'uq_active_dining_reservation' not in dining_indexes:
            op.create_index(
                'uq_active_dining_reservation',
                'dining_reservations',
                ['restaurant_id', 'table_id', 'reservation_date', 'reservation_time'],
                unique=True,
                sqlite_where=sa.text("status IN ('PENDING', 'CONFIRMED', 'SEATED')")
            )

    # 4. Seat Locks Partial Unique Index (Fixed PostgreSQL boolean predicate: is_released = false)
    seat_indexes = [idx['name'] for idx in inspector.get_indexes('seat_locks')]
    if 'uq_active_resource_lock' not in seat_indexes:
        op.create_index(
            'uq_active_resource_lock',
            'seat_locks',
            ['resource_type', 'resource_id', 'identifier'],
            unique=True,
            postgresql_where=sa.text('is_released = false'),
            sqlite_where=sa.text('is_released = 0')
        )

    # 5. Inventory and Capacity Check Constraints (PostgreSQL)
    if is_postgres:
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_ticket_quantity_valid'
                ) THEN
                    ALTER TABLE event_ticket_types
                    ADD CONSTRAINT chk_ticket_quantity_valid
                    CHECK (available_quantity >= 0 AND available_quantity <= total_quantity);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_slot_capacity_valid'
                ) THEN
                    ALTER TABLE activity_slots
                    ADD CONSTRAINT chk_slot_capacity_valid
                    CHECK (booked_count <= capacity AND booked_count >= 0);
                END IF;
            END $$;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Drop seat lock partial index and constraints
    if is_postgres:
        op.drop_index('uq_active_resource_lock', table_name='seat_locks', postgresql_where=sa.text('is_released = false'))
        op.execute("ALTER TABLE dining_reservations DROP CONSTRAINT IF EXISTS exclude_overlapping_dining_reservations;")
        op.execute("ALTER TABLE event_ticket_types DROP CONSTRAINT IF EXISTS chk_ticket_quantity_valid;")
        op.execute("ALTER TABLE activity_slots DROP CONSTRAINT IF EXISTS chk_slot_capacity_valid;")
    else:
        op.drop_index('uq_active_resource_lock', table_name='seat_locks', sqlite_where=sa.text('is_released = 0'))
        op.drop_index('uq_active_dining_reservation', table_name='dining_reservations', sqlite_where=sa.text("status IN ('PENDING', 'CONFIRMED', 'SEATED')"))

    # Drop dining columns
    op.drop_column('dining_reservations', 'end_datetime')
    op.drop_column('dining_reservations', 'start_datetime')
    op.drop_column('dining_reservations', 'buffer_minutes')
    op.drop_column('dining_reservations', 'duration_minutes')

    # Drop refresh tokens table & indexes
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_family_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
