"""add category department

Revision ID: 5c8e4a1d9b22
Revises: 0f3a9c7d2b11
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "5c8e4a1d9b22"
down_revision: str | Sequence[str] | None = "0f3a9c7d2b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_categories",
        sa.Column(
            "department",
            sa.String(length=50),
            nullable=False,
            server_default="KITCHEN",
        ),
    )
    op.alter_column("product_categories", "department", server_default=None)


def downgrade() -> None:
    op.drop_column("product_categories", "department")
