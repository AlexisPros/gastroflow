"""add floor plan decorations

Revision ID: c9d8e7f6a105
Revises: b8d4e2f6a901
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9d8e7f6a105"
down_revision: Union[str, Sequence[str], None] = "b8d4e2f6a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "floor_plan_decorations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("floor_plan_id", sa.Integer(), nullable=False),
        sa.Column("x", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("y", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("width", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("height", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("rotation", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("shape", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=True),
        sa.ForeignKeyConstraint(["floor_plan_id"], ["floor_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_floor_plan_decorations_id"),
        "floor_plan_decorations",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_decorations_floor_plan_id"),
        "floor_plan_decorations",
        ["floor_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_floor_plan_decorations_floor_plan_id"),
        table_name="floor_plan_decorations",
    )
    op.drop_index(
        op.f("ix_floor_plan_decorations_id"),
        table_name="floor_plan_decorations",
    )
    op.drop_table("floor_plan_decorations")
