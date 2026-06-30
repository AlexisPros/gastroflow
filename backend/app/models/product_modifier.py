from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.modifier import Modifier
    from app.models.order_item_modifier import OrderItemModifier
    from app.models.product import Product


class ProductModifier(Base):
    __tablename__ = "product_modifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    modifier_id: Mapped[int] = mapped_column(
        ForeignKey("modifiers.id"),
        nullable=False,
    )

    stock_ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=True,
    )

    replaces_ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=True,
    )

    stock_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3),
        nullable=True,
    )

    price_override: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    product: Mapped[Product] = relationship(
        "Product",
        back_populates="product_modifiers",
    )

    modifier: Mapped[Modifier] = relationship(
        "Modifier",
        back_populates="product_modifiers",
    )

    stock_ingredient: Mapped[Ingredient | None] = relationship(
        "Ingredient",
        foreign_keys=[stock_ingredient_id],
    )

    replaces_ingredient: Mapped[Ingredient | None] = relationship(
        "Ingredient",
        foreign_keys=[replaces_ingredient_id],
    )

    order_item_modifiers: Mapped[list[OrderItemModifier]] = relationship(
        "OrderItemModifier",
        back_populates="product_modifier",
    )
