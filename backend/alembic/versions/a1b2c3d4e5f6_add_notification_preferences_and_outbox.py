"""add_notification_preferences_and_outbox

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-11-08 19:50:00.000000

Phase 1 Module 9 migration: Adds notification_preferences and notification_outbox
tables for durable outbox pattern and user notification preferences.
Fully reversible.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Create notification_preferences table
    if 'notification_preferences' not in tables:
        op.create_table(
            'notification_preferences',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True),
            sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('push_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('in_app_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('booking_alerts', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('payment_alerts', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('marketing_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )

    # 2. Create notification_outbox table
    if 'notification_outbox' not in tables:
        op.create_table(
            'notification_outbox',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('event_type', sa.String(100), nullable=False, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
            sa.Column('channel', sa.String(50), nullable=False, index=True),
            sa.Column('recipient', sa.String(255), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('status', sa.String(50), nullable=False, server_default='PENDING', index=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
            sa.Column('next_retry_at', sa.DateTime(), nullable=True, index=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('provider_name', sa.String(100), nullable=False, server_default='MOCK_PROVIDER'),
            sa.Column('provider_metadata', sa.JSON(), nullable=True),
            sa.Column('idempotency_key', sa.String(255), unique=True, nullable=False, index=True),
            sa.Column('is_marketing', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index(
            'ix_notification_outbox_status_next_retry',
            'notification_outbox',
            ['status', 'next_retry_at']
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'notification_outbox' in tables:
        op.drop_table('notification_outbox')

    if 'notification_preferences' in tables:
        op.drop_table('notification_preferences')

