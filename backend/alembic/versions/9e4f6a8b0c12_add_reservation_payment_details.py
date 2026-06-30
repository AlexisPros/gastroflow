"""add reservation payment details

Revision ID: 9e4f6a8b0c12
Revises: 8c3e5f7a9b11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "9e4f6a8b0c12"
down_revision: str | Sequence[str] | None = "8c3e5f7a9b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reservations", sa.Column("invoice_nip", sa.String(20), nullable=True))
    op.add_column(
        "reservation_payments",
        sa.Column("cash_received", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "reservation_payments",
        sa.Column("change_given", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reservation_payments", "change_given")
    op.drop_column("reservation_payments", "cash_received")
    op.drop_column("reservations", "invoice_nip")
