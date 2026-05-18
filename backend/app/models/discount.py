from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order


class Discount(Base):
    __tablename__ = "discounts"

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

    value: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="discount",
    )
