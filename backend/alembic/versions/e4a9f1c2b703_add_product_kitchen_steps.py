"""add product kitchen steps

Revision ID: e4a9f1c2b703
Revises: d2f7b8c9a104
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a9f1c2b703"
down_revision: Union[str, Sequence[str], None] = "d2f7b8c9a104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "product_kitchen_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("kitchen_section_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("estimated_time", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["kitchen_section_id"], ["kitchen_sections.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "sequence"),
    )
    op.create_index(
        op.f("ix_product_kitchen_steps_id"),
        "product_kitchen_steps",
        ["id"],
        unique=False,
    )
    op.add_column(
        "kitchen_tasks",
        sa.Column("product_kitchen_step_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_kitchen_tasks_product_kitchen_step_id",
        "kitchen_tasks",
        "product_kitchen_steps",
        ["product_kitchen_step_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_kitchen_tasks_product_kitchen_step_id",
        "kitchen_tasks",
        type_="foreignkey",
    )
    op.drop_column("kitchen_tasks", "product_kitchen_step_id")
    op.drop_index(
        op.f("ix_product_kitchen_steps_id"),
        table_name="product_kitchen_steps",
    )
    op.drop_table("product_kitchen_steps")
