from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bill_segment_item import BillSegmentItem
    from app.models.kitchen_task import KitchenTask
    from app.models.order import Order
    from app.models.order_item_modifier import OrderItemModifier
    from app.models.product import Product


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    course_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    total_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NEW",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    stock_consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    order: Mapped[Order] = relationship(
        "Order",
        back_populates="items",
    )

    product: Mapped[Product] = relationship(
        "Product",
        back_populates="order_items",
    )

    modifiers: Mapped[list[OrderItemModifier]] = relationship(
        "OrderItemModifier",
        back_populates="order_item",
        cascade="all, delete-orphan",
    )

    kitchen_tasks: Mapped[list[KitchenTask]] = relationship(
        "KitchenTask",
        back_populates="order_item",
        cascade="all, delete-orphan",
    )

    bill_segment_items: Mapped[list[BillSegmentItem]] = relationship(
        "BillSegmentItem",
        back_populates="original_order_item",
    )
