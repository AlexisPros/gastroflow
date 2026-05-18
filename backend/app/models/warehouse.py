from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.stock_item import StockItem


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
    )

    stock_items: Mapped[list[StockItem]] = relationship(
        "StockItem",
        back_populates="warehouse",
    )
