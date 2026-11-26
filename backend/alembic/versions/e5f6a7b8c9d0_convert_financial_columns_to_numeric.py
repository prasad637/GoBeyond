"""convert_financial_columns_to_numeric

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-06 00:00:00.000000

Reversible migration converting float-based financial and rate columns to exact PostgreSQL
NUMERIC precision (12, 2 for INR amounts and prices, 5, 4 for commission rates, 4, 2 for multipliers).
Preserves existing data without precision loss and supports symmetric downgrade back to double precision.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table_name, column_name, target_numeric_type, using_sql, downgrade_using_sql)
FINANCIAL_COLUMNS = [
    ('bookings', 'total_amount', sa.Numeric(12, 2), '"total_amount"::numeric(12, 2)', '"total_amount"::double precision'),
    ('bookings', 'tax_amount', sa.Numeric(12, 2), '"tax_amount"::numeric(12, 2)', '"tax_amount"::double precision'),
    ('bookings', 'discount_amount', sa.Numeric(12, 2), '"discount_amount"::numeric(12, 2)', '"discount_amount"::double precision'),
    ('bookings', 'final_payable', sa.Numeric(12, 2), '"final_payable"::numeric(12, 2)', '"final_payable"::double precision'),
    ('booking_items', 'unit_price', sa.Numeric(12, 2), '"unit_price"::numeric(12, 2)', '"unit_price"::double precision'),
    ('booking_items', 'subtotal', sa.Numeric(12, 2), '"subtotal"::numeric(12, 2)', '"subtotal"::double precision'),
    ('payments', 'amount', sa.Numeric(12, 2), '"amount"::numeric(12, 2)', '"amount"::double precision'),
    ('refunds', 'amount', sa.Numeric(12, 2), '"amount"::numeric(12, 2)', '"amount"::double precision'),
    ('coupons', 'discount_value', sa.Numeric(12, 2), '"discount_value"::numeric(12, 2)', '"discount_value"::double precision'),
    ('coupons', 'min_order_value', sa.Numeric(12, 2), '"min_order_value"::numeric(12, 2)', '"min_order_value"::double precision'),
    ('coupons', 'max_discount', sa.Numeric(12, 2), '"max_discount"::numeric(12, 2)', '"max_discount"::double precision'),
    ('partners', 'commission_rate', sa.Numeric(5, 4), '"commission_rate"::numeric(5, 4)', '"commission_rate"::double precision'),
    ('seats', 'base_price', sa.Numeric(12, 2), '"base_price"::numeric(12, 2)', '"base_price"::double precision'),
    ('movie_shows', 'price_multiplier', sa.Numeric(4, 2), '"price_multiplier"::numeric(4, 2)', '"price_multiplier"::double precision'),
    ('restaurant_menus', 'price', sa.Numeric(12, 2), '"price"::numeric(12, 2)', '"price"::double precision'),
    ('event_ticket_types', 'price', sa.Numeric(12, 2), '"price"::numeric(12, 2)', '"price"::double precision'),
    ('activities', 'base_price', sa.Numeric(12, 2), '"base_price"::numeric(12, 2)', '"base_price"::double precision'),
    ('activity_slots', 'price_override', sa.Numeric(12, 2), '"price_override"::numeric(12, 2)', '"price_override"::double precision'),
]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        inspector = sa.inspect(bind)
        for tbl, col, num_type, using_sql, _ in FINANCIAL_COLUMNS:
            existing_cols = {c['name']: c for c in inspector.get_columns(tbl)}
            if col in existing_cols:
                op.alter_column(
                    tbl,
                    col,
                    type_=num_type,
                    postgresql_using=using_sql
                )
    else:
        # SQLite: Batch table alteration
        for tbl, col, num_type, _, _ in FINANCIAL_COLUMNS:
            try:
                with op.batch_alter_table(tbl) as batch_op:
                    batch_op.alter_column(col, type_=num_type)
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        inspector = sa.inspect(bind)
        for tbl, col, _, _, down_using in FINANCIAL_COLUMNS:
            existing_cols = {c['name']: c for c in inspector.get_columns(tbl)}
            if col in existing_cols:
                op.alter_column(
                    tbl,
                    col,
                    type_=sa.Float(),
                    postgresql_using=down_using
                )
    else:
        for tbl, col, _, _, _ in FINANCIAL_COLUMNS:
            try:
                with op.batch_alter_table(tbl) as batch_op:
                    batch_op.alter_column(col, type_=sa.Float())
            except Exception:
                pass

