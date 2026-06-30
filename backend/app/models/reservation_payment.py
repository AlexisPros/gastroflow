from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee_shift import EmployeeShift
    from app.models.reservation import Reservation
    from app.models.user import User


class ReservationPayment(Base):
    __tablename__ = "reservation_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    shift_id: Mapped[int] = mapped_column(ForeignKey("employee_shifts.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cash_received: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    change_given: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    reservation: Mapped[Reservation] = relationship("Reservation", back_populates="payments")
    user: Mapped[User] = relationship("User")
    shift: Mapped[EmployeeShift] = relationship("EmployeeShift")
