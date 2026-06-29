from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
    from app.models.stock_item import StockItem
    from app.models.warehouse_document import WarehouseDocument


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    stock_item_id: Mapped[int] = mapped_column(
        ForeignKey("stock_items.id"),
        nullable=False,
    )

    warehouse_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse_documents.id"),
        nullable=True,
        index=True,
    )

    order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_items.id"),
        nullable=True,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    stock_item: Mapped[StockItem] = relationship(
        "StockItem",
        back_populates="stock_movements",
    )

    warehouse_document: Mapped[WarehouseDocument | None] = relationship(
        "WarehouseDocument",
        back_populates="stock_movements",
    )

    order_item: Mapped[OrderItem | None] = relationship("OrderItem")
