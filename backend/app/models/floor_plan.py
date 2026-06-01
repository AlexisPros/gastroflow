from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.floor_plan_decoration import FloorPlanDecoration
    from app.models.floor_plan_table import FloorPlanTable


class FloorPlan(Base):
    __tablename__ = "floor_plans"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1200,
    )

    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=800,
    )

    background_image_url: Mapped[str | None] = mapped_column(
        String(500),
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

    tables: Mapped[list[FloorPlanTable]] = relationship(
        "FloorPlanTable",
        back_populates="floor_plan",
        cascade="all, delete-orphan",
    )

    decorations: Mapped[list[FloorPlanDecoration]] = relationship(
        "FloorPlanDecoration",
        back_populates="floor_plan",
        cascade="all, delete-orphan",
    )
