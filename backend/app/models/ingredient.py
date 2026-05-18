from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product_ingredient import ProductIngredient
    from app.models.stock_item import StockItem


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    product_ingredients: Mapped[list[ProductIngredient]] = relationship(
        "ProductIngredient",
        back_populates="ingredient",
    )

    stock_items: Mapped[list[StockItem]] = relationship(
        "StockItem",
        back_populates="ingredient",
    )
