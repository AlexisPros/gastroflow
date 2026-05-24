from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
    from app.models.product_modifier import ProductModifier


class OrderItemModifier(Base):
    __tablename__ = "order_item_modifiers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id"),
        nullable=False,
    )

    product_modifier_id: Mapped[int] = mapped_column(
        ForeignKey("product_modifiers.id"),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )

    order_item: Mapped[OrderItem] = relationship(
        "OrderItem",
        back_populates="modifiers",
    )

    product_modifier: Mapped[ProductModifier] = relationship(
        "ProductModifier",
        back_populates="order_item_modifiers",
    )
