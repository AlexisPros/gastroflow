"""add user pin lookup

Revision ID: e8f1a2b3c4d5
Revises: d7e8f9a0b1c2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e8f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pin_lookup", sa.String(length=64), nullable=True))
    op.create_index("ix_users_pin_lookup", "users", ["pin_lookup"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_pin_lookup", table_name="users")
    op.drop_column("users", "pin_lookup")
