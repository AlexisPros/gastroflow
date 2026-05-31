"""add qr flow fields

Revision ID: a7c3d9e2f105
Revises: f6b2c8d4e901
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c3d9e2f105"
down_revision: Union[str, Sequence[str], None] = "f6b2c8d4e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "restaurant_tables",
        sa.Column("qr_token", sa.String(length=100), nullable=True),
    )
    op.create_index(
        op.f("ix_restaurant_tables_qr_token"),
        "restaurant_tables",
        ["qr_token"],
        unique=True,
    )
    op.add_column(
        "orders",
        sa.Column("guest_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("orders", "guest_count")
    op.drop_index(
        op.f("ix_restaurant_tables_qr_token"),
        table_name="restaurant_tables",
    )
    op.drop_column("restaurant_tables", "qr_token")
