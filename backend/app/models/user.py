from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee_shift import EmployeeShift
    from app.models.employee_shift_report import EmployeeShiftReport
    from app.models.kitchen_section import KitchenSection
    from app.models.kitchen_task import KitchenTask
    from app.models.order import Order
    from app.models.order_action_log import OrderActionLog
    from app.models.order_transfer_log import OrderTransferLog


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)

    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    pin_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    pin_lookup: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    kitchen_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("kitchen_sections.id"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="waiter",
        foreign_keys="Order.waiter_id",
    )

    assigned_kitchen_tasks: Mapped[list[KitchenTask]] = relationship(
        "KitchenTask",
        back_populates="assigned_user",
    )

    kitchen_section: Mapped[KitchenSection | None] = relationship(
        "KitchenSection",
        back_populates="users",
    )

    outgoing_transfer_logs: Mapped[list[OrderTransferLog]] = relationship(
        "OrderTransferLog",
        back_populates="from_waiter",
        foreign_keys="OrderTransferLog.from_waiter_id",
    )

    incoming_transfer_logs: Mapped[list[OrderTransferLog]] = relationship(
        "OrderTransferLog",
        back_populates="to_waiter",
        foreign_keys="OrderTransferLog.to_waiter_id",
    )

    action_logs: Mapped[list[OrderActionLog]] = relationship(
        "OrderActionLog",
        back_populates="user",
    )

    employee_shifts: Mapped[list[EmployeeShift]] = relationship(
        "EmployeeShift",
        back_populates="user",
    )

    employee_shift_reports: Mapped[list[EmployeeShiftReport]] = relationship(
        "EmployeeShiftReport",
        back_populates="user",
    )
