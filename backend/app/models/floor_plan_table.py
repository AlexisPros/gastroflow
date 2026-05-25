from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.floor_plan import FloorPlan
    from app.models.restaurant_table import RestaurantTable


class FloorPlanTable(Base):
    __tablename__ = "floor_plan_tables"
    __table_args__ = (
        UniqueConstraint("floor_plan_id", "table_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    floor_plan_id: Mapped[int] = mapped_column(
        ForeignKey("floor_plans.id"),
        nullable=False,
    )

    table_id: Mapped[int] = mapped_column(
        ForeignKey("restaurant_tables.id"),
        nullable=False,
    )

    x: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    y: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    width: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    height: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

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

    floor_plan: Mapped[FloorPlan] = relationship(
        "FloorPlan",
        back_populates="tables",
    )

    table: Mapped[RestaurantTable] = relationship(
        "RestaurantTable",
        back_populates="floor_plan_positions",
    )
