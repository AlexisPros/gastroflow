from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bill_segment import BillSegment
    from app.models.order_item import OrderItem
    from app.models.product import Product


class BillSegmentItem(Base):
    __tablename__ = "bill_segment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    bill_segment_id: Mapped[int] = mapped_column(
        ForeignKey("bill_segments.id"),
        nullable=False,
        index=True,
    )

    original_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    modifier_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    segment: Mapped[BillSegment] = relationship(
        "BillSegment",
        back_populates="items",
    )

    original_order_item: Mapped[OrderItem] = relationship(
        "OrderItem",
        back_populates="bill_segment_items",
    )

    product: Mapped[Product] = relationship("Product")
