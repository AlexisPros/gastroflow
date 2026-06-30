"""add reservation workflow

Revision ID: 8c3e5f7a9b11
Revises: 7b2d4f6a8c10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "8c3e5f7a9b11"
down_revision: str | Sequence[str] | None = "7b2d4f6a8c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reservations", sa.Column("customer_email", sa.String(255), nullable=True))
    op.add_column(
        "reservations",
        sa.Column("duration_minutes", sa.Integer(), server_default="120", nullable=False),
    )
    op.add_column(
        "reservations",
        sa.Column("total_amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
    )
    op.add_column(
        "reservations",
        sa.Column("prepaid_amount", sa.Numeric(10, 2), server_default="0.00", nullable=False),
    )
    op.add_column(
        "reservations",
        sa.Column("payment_status", sa.String(50), server_default="UNPAID", nullable=False),
    )
    op.add_column("reservations", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column("reservations", sa.Column("started_order_id", sa.Integer(), nullable=True))
    op.add_column("reservations", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_reservations_created_by_user_id_users",
        "reservations", "users", ["created_by_user_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_reservations_started_order_id_orders",
        "reservations", "orders", ["started_order_id"], ["id"],
    )
    op.create_unique_constraint(
        "uq_reservations_started_order_id", "reservations", ["started_order_id"]
    )

    op.add_column("orders", sa.Column("reservation_id", sa.Integer(), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "reservation_prepaid_amount",
            sa.Numeric(10, 2),
            server_default="0.00",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_orders_reservation_id_reservations",
        "orders", "reservations", ["reservation_id"], ["id"],
    )
    op.create_unique_constraint("uq_orders_reservation_id", "orders", ["reservation_id"])

    op.create_table(
        "reservation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Integer(),
            sa.ForeignKey("reservations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
    )
    op.create_index("ix_reservation_items_reservation_id", "reservation_items", ["reservation_id"])

    op.create_table(
        "reservation_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reservation_id",
            sa.Integer(),
            sa.ForeignKey("reservations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("employee_shifts.id"), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(50), server_default="COMPLETED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_reservation_payments_reservation_id", "reservation_payments", ["reservation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_reservation_payments_reservation_id", table_name="reservation_payments")
    op.drop_table("reservation_payments")
    op.drop_index("ix_reservation_items_reservation_id", table_name="reservation_items")
    op.drop_table("reservation_items")
    op.drop_constraint("uq_orders_reservation_id", "orders", type_="unique")
    op.drop_constraint("fk_orders_reservation_id_reservations", "orders", type_="foreignkey")
    op.drop_column("orders", "reservation_prepaid_amount")
    op.drop_column("orders", "reservation_id")
    op.drop_constraint("uq_reservations_started_order_id", "reservations", type_="unique")
    op.drop_constraint("fk_reservations_started_order_id_orders", "reservations", type_="foreignkey")
    op.drop_constraint("fk_reservations_created_by_user_id_users", "reservations", type_="foreignkey")
    op.drop_column("reservations", "started_at")
    op.drop_column("reservations", "started_order_id")
    op.drop_column("reservations", "created_by_user_id")
    op.drop_column("reservations", "payment_status")
    op.drop_column("reservations", "prepaid_amount")
    op.drop_column("reservations", "total_amount")
    op.drop_column("reservations", "duration_minutes")
    op.drop_column("reservations", "customer_email")
