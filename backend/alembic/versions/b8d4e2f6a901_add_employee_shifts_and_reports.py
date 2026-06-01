"""add employee shifts and reports

Revision ID: b8d4e2f6a901
Revises: a7c3d9e2f105
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8d4e2f6a901"
down_revision: Union[str, Sequence[str], None] = "a7c3d9e2f105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_shifts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("opening_note", sa.Text(), nullable=True),
        sa.Column("closing_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_shifts_id"),
        "employee_shifts",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_shifts_user_id"),
        "employee_shifts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "employee_shift_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("orders_count", sa.Integer(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("total_sales", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_tips", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_discounts", sa.Numeric(10, 2), nullable=False),
        sa.Column("cash_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("card_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("other_payment_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["employee_shifts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shift_id"),
    )
    op.create_index(
        op.f("ix_employee_shift_reports_id"),
        "employee_shift_reports",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_shift_reports_shift_id"),
        "employee_shift_reports",
        ["shift_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_shift_reports_user_id"),
        "employee_shift_reports",
        ["user_id"],
        unique=False,
    )

    op.add_column(
        "orders",
        sa.Column("shift_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "subtotal_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0.00",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "discount_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0.00",
        ),
    )
    op.create_index(
        op.f("ix_orders_shift_id"),
        "orders",
        ["shift_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_orders_shift_id_employee_shifts"),
        "orders",
        "employee_shifts",
        ["shift_id"],
        ["id"],
    )

    op.alter_column("orders", "subtotal_amount", server_default=None)
    op.alter_column("orders", "discount_amount", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_orders_shift_id_employee_shifts"),
        "orders",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_orders_shift_id"), table_name="orders")
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "subtotal_amount")
    op.drop_column("orders", "shift_id")

    op.drop_index(
        op.f("ix_employee_shift_reports_user_id"),
        table_name="employee_shift_reports",
    )
    op.drop_index(
        op.f("ix_employee_shift_reports_shift_id"),
        table_name="employee_shift_reports",
    )
    op.drop_index(
        op.f("ix_employee_shift_reports_id"),
        table_name="employee_shift_reports",
    )
    op.drop_table("employee_shift_reports")

    op.drop_index(
        op.f("ix_employee_shifts_user_id"),
        table_name="employee_shifts",
    )
    op.drop_index(op.f("ix_employee_shifts_id"), table_name="employee_shifts")
    op.drop_table("employee_shifts")
