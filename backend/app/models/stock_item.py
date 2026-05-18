from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.stock_movement import StockMovement
    from app.models.warehouse import Warehouse


class StockItem(Base):
    __tablename__ = "stock_items"

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

    quantity: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    minimum_quantity: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
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
