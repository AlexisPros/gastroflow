from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.stock_item import StockItem
    from app.models.warehouse_document import WarehouseDocument
    from app.models.warehouse_user_access import WarehouseUserAccess


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="GENERAL",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    stock_items: Mapped[list[StockItem]] = relationship(
        "StockItem",
        back_populates="warehouse",
    )

    user_accesses: Mapped[list[WarehouseUserAccess]] = relationship(
        "WarehouseUserAccess",
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )

    outgoing_documents: Mapped[list[WarehouseDocument]] = relationship(
        "WarehouseDocument",
        back_populates="source_warehouse",
        foreign_keys="WarehouseDocument.source_warehouse_id",
    )

    incoming_documents: Mapped[list[WarehouseDocument]] = relationship(
        "WarehouseDocument",
        back_populates="destination_warehouse",
        foreign_keys="WarehouseDocument.destination_warehouse_id",
    )
