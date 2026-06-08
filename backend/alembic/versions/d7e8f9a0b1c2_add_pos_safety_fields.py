"""add POS safety fields

Revision ID: d7e8f9a0b1c2
Revises: c2d3e4f5a6b7
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "orders",
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_orders_idempotency_key",
        "orders",
        ["idempotency_key"],
    )
    op.add_column(
        "payments",
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("cash_received", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("change_given", sa.Numeric(10, 2), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payments_idempotency_key",
        "payments",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_idempotency_key", "payments", type_="unique")
    op.drop_column("payments", "change_given")
    op.drop_column("payments", "cash_received")
    op.drop_column("payments", "idempotency_key")
    op.drop_constraint("uq_orders_idempotency_key", "orders", type_="unique")
    op.drop_column("orders", "idempotency_key")
    op.drop_column("orders", "version")
