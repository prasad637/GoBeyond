"""add_user_account_status

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-06 04:00:00.000000

Phase 1 Module 2 migration: Adds account_status column to users table
to support explicit lifecycle states (ACTIVE, DEACTIVATED, SUSPENDED)
and the account deletion/deactivation workflow.
Fully reversible.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [c['name'] for c in insp.get_columns('users')]
    
    if 'account_status' not in columns:
        op.add_column(
            'users',
            sa.Column(
                'account_status',
                sa.String(50),
                nullable=False,
                server_default='ACTIVE'
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [c['name'] for c in insp.get_columns('users')]
    
    if 'account_status' in columns:
        op.drop_column('users', 'account_status')

