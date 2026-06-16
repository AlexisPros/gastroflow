"""add kitchen step dependencies

Revision ID: 0f3a9c7d2b11
Revises: f2b3c4d5e6a7
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0f3a9c7d2b11"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_kitchen_steps",
        sa.Column("depends_on_sequence", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_kitchen_steps", "depends_on_sequence")
