from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.reservation import Reservation


class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    table_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    current_guests: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="FREE",
    )

    qr_code_url: Mapped[str | None] = mapped_column(
        String(500),
        unique=True,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="table",
    )

    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation",
        back_populates="table",
    )
