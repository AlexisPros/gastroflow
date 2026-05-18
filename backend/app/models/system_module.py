from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.restaurant_config import RestaurantConfig


class SystemModule(Base):
    __tablename__ = "system_modules"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    restaurant_config_id: Mapped[int] = mapped_column(
        ForeignKey("restaurant_config.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    restaurant_config: Mapped[RestaurantConfig] = relationship(
        "RestaurantConfig",
        back_populates="system_modules",
    )
