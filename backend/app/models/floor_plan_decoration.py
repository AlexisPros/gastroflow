from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan


class FloorPlanDecoration(Base):
    __tablename__ = "floor_plan_decorations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    floor_plan_id: Mapped[int] = mapped_column(
        ForeignKey("floor_plans.id"),
        nullable=False,
        index=True,
    )

    x: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    y: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    width: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    height: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    rotation: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    shape: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="RECTANGLE",
    )

    color: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="#252b2d",
    )

    label: Mapped[str | None] = mapped_column(String(150), nullable=True)

    floor_plan: Mapped[FloorPlan] = relationship(
        "FloorPlan",
        back_populates="decorations",
    )
