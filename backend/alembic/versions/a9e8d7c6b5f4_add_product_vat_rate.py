"""add product vat rate

Revision ID: a9e8d7c6b5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-06-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a9e8d7c6b5f4"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "vat_rate",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="8.00",
        ),
    )
    op.alter_column("products", "vat_rate", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "vat_rate")
