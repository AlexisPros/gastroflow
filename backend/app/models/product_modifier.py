from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
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

    order_item_modifiers: Mapped[list[OrderItemModifier]] = relationship(
        "OrderItemModifier",
        back_populates="product_modifier",
    )
