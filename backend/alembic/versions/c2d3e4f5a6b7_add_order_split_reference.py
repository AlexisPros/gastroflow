"""add order split reference

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("split_parent_order_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("split_sequence", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_orders_split_parent_order_id"),
        "orders",
        ["split_parent_order_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_orders_split_parent_order_id_orders",
        "orders",
        "orders",
        ["split_parent_order_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_orders_split_parent_order_id_orders",
        "orders",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_orders_split_parent_order_id"), table_name="orders")
    op.drop_column("orders", "split_sequence")
    op.drop_column("orders", "split_parent_order_id")
