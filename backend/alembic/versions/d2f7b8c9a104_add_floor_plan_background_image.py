"""add floor plan background image

Revision ID: d2f7b8c9a104
Revises: a3f4c2d8e901
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2f7b8c9a104"
down_revision: Union[str, Sequence[str], None] = "a3f4c2d8e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "floor_plans",
        sa.Column("background_image_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("floor_plans", "background_image_url")
