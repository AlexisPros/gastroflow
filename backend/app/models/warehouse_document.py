from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.stock_movement import StockMovement
    from app.models.user import User
    from app.models.warehouse import Warehouse
    from app.models.warehouse_document_item import WarehouseDocumentItem


class WarehouseDocument(Base):
    __tablename__ = "warehouse_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_number: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="COMPLETED",
    )
    source_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"),
        nullable=True,
        index=True,
    )
    destination_warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"),
        nullable=True,
        index=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"),
        nullable=True,
        index=True,
    )
    issued_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    operation_date: Mapped[date] = mapped_column(Date, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_warehouse: Mapped[Warehouse | None] = relationship(
        "Warehouse",
        back_populates="outgoing_documents",
        foreign_keys=[source_warehouse_id],
    )
    destination_warehouse: Mapped[Warehouse | None] = relationship(
        "Warehouse",
        back_populates="incoming_documents",
        foreign_keys=[destination_warehouse_id],
    )
    order: Mapped[Order | None] = relationship("Order")
    issued_by_user: Mapped[User | None] = relationship("User")
    items: Mapped[list[WarehouseDocumentItem]] = relationship(
        "WarehouseDocumentItem",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    stock_movements: Mapped[list[StockMovement]] = relationship(
        "StockMovement",
        back_populates="warehouse_document",
    )
