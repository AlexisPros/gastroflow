from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.reservation_table import ReservationTable
    from app.models.reservation_item import ReservationItem
    from app.models.reservation_payment import ReservationPayment
    from app.models.restaurant_table import RestaurantTable
    from app.models.order import Order
    from app.models.user import User


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

    customer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    invoice_nip: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    guest_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reservation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=120,
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

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    prepaid_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    payment_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UNPAID",
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    started_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"),
        nullable=True,
        unique=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    reservation_tables: Mapped[list[ReservationTable]] = relationship(
        "ReservationTable",
        back_populates="reservation",
        cascade="all, delete-orphan",
    )

    items: Mapped[list[ReservationItem]] = relationship(
        "ReservationItem",
        back_populates="reservation",
        cascade="all, delete-orphan",
    )

    payments: Mapped[list[ReservationPayment]] = relationship(
        "ReservationPayment",
        back_populates="reservation",
        cascade="all, delete-orphan",
    )

    created_by: Mapped[User | None] = relationship("User")

    started_order: Mapped[Order | None] = relationship(
        "Order",
        foreign_keys=[started_order_id],
    )
