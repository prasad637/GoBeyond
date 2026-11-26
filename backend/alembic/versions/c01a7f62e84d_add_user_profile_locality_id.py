"""add_user_profile_locality_id

Revision ID: c01a7f62e84d
Revises: abd72e902347
Create Date: 2026-11-05 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c01a7f62e84d'
down_revision: Union[str, None] = 'abd72e902347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('user_profiles')]

    if 'locality_id' not in cols:
        if is_postgres:
            op.add_column('user_profiles', sa.Column('locality_id', sa.Integer(), nullable=True))
            op.create_foreign_key(
                'user_profiles_locality_id_fkey',
                'user_profiles',
                'locations',
                ['locality_id'],
                ['id']
            )
            op.create_index(
                op.f('ix_user_profiles_locality_id'),
                'user_profiles',
                ['locality_id'],
                unique=False
            )
        else:
            with op.batch_alter_table('user_profiles') as batch_op:
                batch_op.add_column(sa.Column('locality_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'user_profiles_locality_id_fkey',
                    'locations',
                    ['locality_id'],
                    ['id']
                )
                batch_op.create_index(
                    op.f('ix_user_profiles_locality_id'),
                    ['locality_id'],
                    unique=False
                )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index(op.f('ix_user_profiles_locality_id'), table_name='user_profiles')
    if is_postgres:
        op.drop_constraint('user_profiles_locality_id_fkey', 'user_profiles', type_='foreignkey')
        op.drop_column('user_profiles', 'locality_id')
    else:
        with op.batch_alter_table('user_profiles') as batch_op:
            batch_op.drop_column('locality_id')

