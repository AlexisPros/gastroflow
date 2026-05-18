from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.restaurant_table import RestaurantTable


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    table_id: Mapped[int] = mapped_column(
        ForeignKey("restaurant_tables.id"),
        nullable=False,
    )

    customer_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    customer_phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    guest_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reservation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    table: Mapped[RestaurantTable] = relationship(
        "RestaurantTable",
        back_populates="reservations",
    )
