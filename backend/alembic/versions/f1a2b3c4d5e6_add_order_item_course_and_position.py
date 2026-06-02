"""add order item course and position

Revision ID: f1a2b3c4d5e6
Revises: c9d8e7f6a105
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c9d8e7f6a105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "order_items",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "order_items",
        sa.Column("course_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("order_items", "position", server_default=None)
    op.alter_column("order_items", "course_number", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("order_items", "course_number")
    op.drop_column("order_items", "position")
