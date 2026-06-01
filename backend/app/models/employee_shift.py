from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee_shift_report import EmployeeShiftReport
    from app.models.order import Order
    from app.models.user import User


class EmployeeShift(Base):
    __tablename__ = "employee_shifts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="OPEN",
    )

    opening_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    closing_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="employee_shifts",
    )

    orders: Mapped[list[Order]] = relationship(
        "Order",
        back_populates="shift",
    )

    report: Mapped[EmployeeShiftReport | None] = relationship(
        "EmployeeShiftReport",
        back_populates="shift",
        uselist=False,
        cascade="all, delete-orphan",
    )
