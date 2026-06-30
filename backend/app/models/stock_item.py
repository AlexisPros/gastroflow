from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.stock_movement import StockMovement
    from app.models.warehouse import Warehouse


class StockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = (
        UniqueConstraint(
            "warehouse_id",
            "ingredient_id",
            name="uq_stock_items_warehouse_ingredient",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id"),
        nullable=False,
    )

    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    minimum_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    warehouse: Mapped[Warehouse] = relationship(
        "Warehouse",
        back_populates="stock_items",
    )

    ingredient: Mapped[Ingredient] = relationship(
        "Ingredient",
        back_populates="stock_items",
    )

    stock_movements: Mapped[list[StockMovement]] = relationship(
        "StockMovement",
        back_populates="stock_item",
        cascade="all, delete-orphan",
    )
