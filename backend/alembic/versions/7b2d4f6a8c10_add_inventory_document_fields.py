"""add inventory document fields

Revision ID: 7b2d4f6a8c10
Revises: 6a9c2e4f7b10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "7b2d4f6a8c10"
down_revision: str | Sequence[str] | None = "6a9c2e4f7b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "warehouse_document_items",
        sa.Column("book_quantity", sa.Numeric(14, 3), nullable=True),
    )
    op.add_column(
        "warehouse_document_items",
        sa.Column("actual_quantity", sa.Numeric(14, 3), nullable=True),
    )
    op.add_column(
        "warehouse_document_items",
        sa.Column("difference_quantity", sa.Numeric(14, 3), nullable=True),
    )
    op.add_column(
        "warehouse_document_items",
        sa.Column("difference_value", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("warehouse_document_items", "difference_value")
    op.drop_column("warehouse_document_items", "difference_quantity")
    op.drop_column("warehouse_document_items", "actual_quantity")
    op.drop_column("warehouse_document_items", "book_quantity")
