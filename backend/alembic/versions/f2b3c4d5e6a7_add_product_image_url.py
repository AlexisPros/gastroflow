"""add product image url

Revision ID: f2b3c4d5e6a7
Revises: e8f1a2b3c4d5
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa


revision = "f2b3c4d5e6a7"
down_revision = "e8f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_url")
