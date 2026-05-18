from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.system_module import SystemModule


class RestaurantConfig(Base):
    __tablename__ = "restaurant_config"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    restaurant_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="PLN",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    system_modules: Mapped[list[SystemModule]] = relationship(
        "SystemModule",
        back_populates="restaurant_config",
        cascade="all, delete-orphan",
    )
