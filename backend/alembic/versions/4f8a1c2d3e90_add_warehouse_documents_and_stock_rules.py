"""add warehouse documents and stock rules

Revision ID: 4f8a1c2d3e90
Revises: 9d1f4b6a8c20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "4f8a1c2d3e90"
down_revision: str | Sequence[str] | None = "9d1f4b6a8c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "warehouses",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "warehouses",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column(
        "warehouses",
        "type",
        existing_type=sa.String(length=50),
        server_default="GENERAL",
        existing_nullable=False,
    )

    # Preserve movements and quantities before enforcing one row per ingredient/warehouse.
    op.execute(
        """
        WITH grouped AS (
            SELECT warehouse_id, ingredient_id, MIN(id) AS keep_id, SUM(quantity) AS total_quantity
            FROM stock_items
            GROUP BY warehouse_id, ingredient_id
        )
        UPDATE stock_items AS target
        SET quantity = grouped.total_quantity
        FROM grouped
        WHERE target.id = grouped.keep_id
        """,
    )
    op.execute(
        """
        UPDATE stock_movements AS movement
        SET stock_item_id = keeper.keep_id
        FROM (
            SELECT duplicate.id AS duplicate_id, grouped.keep_id
            FROM stock_items AS duplicate
            JOIN (
                SELECT warehouse_id, ingredient_id, MIN(id) AS keep_id
                FROM stock_items
                GROUP BY warehouse_id, ingredient_id
            ) AS grouped
              ON grouped.warehouse_id = duplicate.warehouse_id
             AND grouped.ingredient_id = duplicate.ingredient_id
            WHERE duplicate.id <> grouped.keep_id
        ) AS keeper
        WHERE movement.stock_item_id = keeper.duplicate_id
        """,
    )
    op.execute(
        """
        DELETE FROM stock_items AS duplicate
        USING (
            SELECT warehouse_id, ingredient_id, MIN(id) AS keep_id
            FROM stock_items
            GROUP BY warehouse_id, ingredient_id
        ) AS grouped
        WHERE duplicate.warehouse_id = grouped.warehouse_id
          AND duplicate.ingredient_id = grouped.ingredient_id
          AND duplicate.id <> grouped.keep_id
        """,
    )
    op.alter_column(
        "stock_items",
        "quantity",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(14, 3),
        existing_nullable=False,
    )
    op.alter_column(
        "stock_items",
        "minimum_quantity",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(14, 3),
        existing_nullable=True,
    )
    op.create_unique_constraint(
        "uq_stock_items_warehouse_ingredient",
        "stock_items",
        ["warehouse_id", "ingredient_id"],
    )

    op.add_column(
        "order_items",
        sa.Column("stock_consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "product_modifiers",
        sa.Column("stock_ingredient_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_modifiers",
        sa.Column("replaces_ingredient_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_modifiers",
        sa.Column("stock_quantity", sa.Numeric(14, 3), nullable=True),
    )
    op.create_foreign_key(
        "fk_product_modifiers_stock_ingredient",
        "product_modifiers",
        "ingredients",
        ["stock_ingredient_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_product_modifiers_replaces_ingredient",
        "product_modifiers",
        "ingredients",
        ["replaces_ingredient_id"],
        ["id"],
    )

    op.create_table(
        "warehouse_user_accesses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warehouse_id", "user_id", name="uq_warehouse_user_access"),
    )
    op.create_index("ix_warehouse_user_accesses_id", "warehouse_user_accesses", ["id"])
    op.create_index("ix_warehouse_user_accesses_user_id", "warehouse_user_accesses", ["user_id"])
    op.create_index("ix_warehouse_user_accesses_warehouse_id", "warehouse_user_accesses", ["warehouse_id"])

    op.create_table(
        "warehouse_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_number", sa.String(length=80), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_warehouse_id", sa.Integer(), nullable=True),
        sa.Column("destination_warehouse_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["destination_warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["source_warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_number"),
    )
    op.create_index("ix_warehouse_documents_id", "warehouse_documents", ["id"])
    op.create_index("ix_warehouse_documents_document_number", "warehouse_documents", ["document_number"])
    op.create_index("ix_warehouse_documents_document_type", "warehouse_documents", ["document_type"])
    op.create_index("ix_warehouse_documents_source_warehouse_id", "warehouse_documents", ["source_warehouse_id"])
    op.create_index("ix_warehouse_documents_destination_warehouse_id", "warehouse_documents", ["destination_warehouse_id"])
    op.create_index("ix_warehouse_documents_order_id", "warehouse_documents", ["order_id"])

    op.create_table(
        "warehouse_document_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("warehouse_document_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_value", sa.Numeric(12, 2), nullable=True),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"]),
        sa.ForeignKeyConstraint(["warehouse_document_id"], ["warehouse_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_warehouse_document_items_id", "warehouse_document_items", ["id"])
    op.create_index("ix_warehouse_document_items_ingredient_id", "warehouse_document_items", ["ingredient_id"])
    op.create_index("ix_warehouse_document_items_warehouse_document_id", "warehouse_document_items", ["warehouse_document_id"])

    op.add_column(
        "stock_movements",
        sa.Column("warehouse_document_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "stock_movements",
        sa.Column("order_item_id", sa.Integer(), nullable=True),
    )
    op.alter_column(
        "stock_movements",
        "quantity",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(14, 3),
        existing_nullable=False,
    )
    op.create_foreign_key(
        "fk_stock_movements_warehouse_document",
        "stock_movements",
        "warehouse_documents",
        ["warehouse_document_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_stock_movements_order_item",
        "stock_movements",
        "order_items",
        ["order_item_id"],
        ["id"],
    )
    op.create_index("ix_stock_movements_warehouse_document_id", "stock_movements", ["warehouse_document_id"])
    op.create_index("ix_stock_movements_order_item_id", "stock_movements", ["order_item_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_movements_order_item_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_warehouse_document_id", table_name="stock_movements")
    op.drop_constraint("fk_stock_movements_order_item", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_warehouse_document", "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "order_item_id")
    op.drop_column("stock_movements", "warehouse_document_id")
    op.alter_column(
        "stock_movements",
        "quantity",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.drop_table("warehouse_document_items")
    op.drop_table("warehouse_documents")
    op.drop_table("warehouse_user_accesses")
    op.drop_constraint("fk_product_modifiers_replaces_ingredient", "product_modifiers", type_="foreignkey")
    op.drop_constraint("fk_product_modifiers_stock_ingredient", "product_modifiers", type_="foreignkey")
    op.drop_column("product_modifiers", "stock_quantity")
    op.drop_column("product_modifiers", "replaces_ingredient_id")
    op.drop_column("product_modifiers", "stock_ingredient_id")
    op.drop_column("order_items", "stock_consumed_at")
    op.drop_constraint("uq_stock_items_warehouse_ingredient", "stock_items", type_="unique")
    op.alter_column(
        "stock_items",
        "minimum_quantity",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "stock_items",
        "quantity",
        existing_type=sa.Numeric(14, 3),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.drop_column("warehouses", "is_default")
    op.drop_column("warehouses", "is_active")
    op.alter_column(
        "warehouses",
        "type",
        existing_type=sa.String(length=50),
        server_default=None,
        existing_nullable=False,
    )
