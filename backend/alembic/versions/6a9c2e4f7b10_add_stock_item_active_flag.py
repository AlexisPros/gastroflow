"""add stock item active flag

Revision ID: 6a9c2e4f7b10
Revises: 4f8a1c2d3e90
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "6a9c2e4f7b10"
down_revision: str | Sequence[str] | None = "4f8a1c2d3e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_items",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("stock_items", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("stock_items", "is_active")
