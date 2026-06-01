from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.discount import Discount
    from app.models.invoice import Invoice
    from app.models.order_action_log import OrderActionLog
    from app.models.order_item import OrderItem
    from app.models.order_transfer_log import OrderTransferLog
    from app.models.payment import Payment
    from app.models.restaurant_table import RestaurantTable
    from app.models.user import User


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    table_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurant_tables.id"),
        nullable=True,
    )

    waiter_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    discount_id: Mapped[int | None] = mapped_column(
        ForeignKey("discounts.id"),
        nullable=True,
    )

    guest_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="WAITER",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="OPEN",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    tip_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    estimated_time: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    table: Mapped[RestaurantTable | None] = relationship(
        "RestaurantTable",
        back_populates="orders",
    )

    waiter: Mapped[User | None] = relationship(
        "User",
        back_populates="orders",
        foreign_keys=[waiter_id],
    )

    discount: Mapped[Discount | None] = relationship(
        "Discount",
        back_populates="orders",
    )

    items: Mapped[list[OrderItem]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    payments: Mapped[list[Payment]] = relationship(
        "Payment",
        back_populates="order",
    )

    invoice: Mapped[Invoice | None] = relationship(
        "Invoice",
        back_populates="order",
        uselist=False,
    )

    transfer_logs: Mapped[list[OrderTransferLog]] = relationship(
        "OrderTransferLog",
        back_populates="order",
    )

    action_logs: Mapped[list[OrderActionLog]] = relationship(
        "OrderActionLog",
        back_populates="order",
    )
