"""add floor plan tables

Revision ID: a3f4c2d8e901
Revises: 851ced557524
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3f4c2d8e901"
down_revision: Union[str, Sequence[str], None] = "851ced557524"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "floor_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_floor_plans_id"), "floor_plans", ["id"], unique=False)

    op.create_table(
        "floor_plan_tables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("floor_plan_id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("x", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("y", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("width", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("height", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("rotation", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("shape", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["floor_plan_id"], ["floor_plans.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["restaurant_tables.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("floor_plan_id", "table_id"),
    )
    op.create_index(
        op.f("ix_floor_plan_tables_id"),
        "floor_plan_tables",
        ["id"],
        unique=False,
    )

    op.create_table(
        "reservation_tables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["restaurant_tables.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_id", "table_id"),
    )
    op.create_index(
        op.f("ix_reservation_tables_id"),
        "reservation_tables",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_reservation_tables_id"), table_name="reservation_tables")
    op.drop_table("reservation_tables")
    op.drop_index(op.f("ix_floor_plan_tables_id"), table_name="floor_plan_tables")
    op.drop_table("floor_plan_tables")
    op.drop_index(op.f("ix_floor_plans_id"), table_name="floor_plans")
    op.drop_table("floor_plans")
