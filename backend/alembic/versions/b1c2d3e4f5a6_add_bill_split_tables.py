"""add bill split tables

Revision ID: b1c2d3e4f5a6
Revises: a9e8d7c6b5f4
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "a9e8d7c6b5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bill_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bill_segments_id"), "bill_segments", ["id"], unique=False)
    op.create_index(
        op.f("ix_bill_segments_order_id"),
        "bill_segments",
        ["order_id"],
        unique=False,
    )

    op.create_table(
        "bill_segment_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bill_segment_id", sa.Integer(), nullable=False),
        sa.Column("original_order_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("modifier_snapshot", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["bill_segment_id"], ["bill_segments.id"]),
        sa.ForeignKeyConstraint(["original_order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_bill_segment_items_bill_segment_id"),
        "bill_segment_items",
        ["bill_segment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bill_segment_items_id"),
        "bill_segment_items",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bill_segment_items_original_order_item_id"),
        "bill_segment_items",
        ["original_order_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_bill_segment_items_original_order_item_id"),
        table_name="bill_segment_items",
    )
    op.drop_index(op.f("ix_bill_segment_items_id"), table_name="bill_segment_items")
    op.drop_index(
        op.f("ix_bill_segment_items_bill_segment_id"),
        table_name="bill_segment_items",
    )
    op.drop_table("bill_segment_items")
    op.drop_index(op.f("ix_bill_segments_order_id"), table_name="bill_segments")
    op.drop_index(op.f("ix_bill_segments_id"), table_name="bill_segments")
    op.drop_table("bill_segments")
