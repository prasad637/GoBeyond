"""add_partner_commission_rate

Revision ID: d4e5f6a7b8c9
Revises: c01a7f62e84d
Create Date: 2026-11-05 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c01a7f62e84d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('partners')]

    if 'commission_rate' not in cols:
        op.add_column(
            'partners',
            sa.Column('commission_rate', sa.Float(), server_default='0.10', nullable=False)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('partners')]

    if 'commission_rate' in cols:
        op.drop_column('partners', 'commission_rate')

