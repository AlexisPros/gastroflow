from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.reservation import Reservation
    from app.models.restaurant_table import RestaurantTable


class ReservationTable(Base):
    __tablename__ = "reservation_tables"
    __table_args__ = (
        UniqueConstraint("reservation_id", "table_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"),
        nullable=False,
    )

    table_id: Mapped[int] = mapped_column(
        ForeignKey("restaurant_tables.id"),
        nullable=False,
    )

    reservation: Mapped[Reservation] = relationship(
        "Reservation",
        back_populates="reservation_tables",
    )

    table: Mapped[RestaurantTable] = relationship(
        "RestaurantTable",
        back_populates="reservation_links",
    )
