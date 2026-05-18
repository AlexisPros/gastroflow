from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class OrderTransferLog(Base):
    __tablename__ = "order_transfer_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        nullable=False,
    )

    from_waiter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    to_waiter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order: Mapped[Order] = relationship(
        "Order",
        back_populates="transfer_logs",
    )

    from_waiter: Mapped[User] = relationship(
        "User",
        back_populates="outgoing_transfer_logs",
        foreign_keys=[from_waiter_id],
    )

    to_waiter: Mapped[User] = relationship(
        "User",
        back_populates="incoming_transfer_logs",
        foreign_keys=[to_waiter_id],
    )
