"""add qr parent order reference

Revision ID: 9d1f4b6a8c20
Revises: 35e5b3a75d66
Create Date: 2026-06-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d1f4b6a8c20"
down_revision: Union[str, Sequence[str], None] = "35e5b3a75d66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("qr_parent_order_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_orders_qr_parent_order_id",
        "orders",
        ["qr_parent_order_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_orders_qr_parent_order_id_orders",
        "orders",
        "orders",
        ["qr_parent_order_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_orders_qr_parent_order_id_orders",
        "orders",
        type_="foreignkey",
    )
    op.drop_index("ix_orders_qr_parent_order_id", table_name="orders")
    op.drop_column("orders", "qr_parent_order_id")
