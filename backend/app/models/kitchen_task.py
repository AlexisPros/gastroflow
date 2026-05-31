from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.kitchen_section import KitchenSection
    from app.models.order_item import OrderItem
    from app.models.product_kitchen_step import ProductKitchenStep
    from app.models.user import User


class KitchenTask(Base):
    __tablename__ = "kitchen_tasks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id"),
        nullable=False,
    )

    kitchen_section_id: Mapped[int] = mapped_column(
        ForeignKey("kitchen_sections.id"),
        nullable=False,
    )

    product_kitchen_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_kitchen_steps.id"),
        nullable=True,
    )

    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NEW",
    )

    estimated_time: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    order_item: Mapped[OrderItem] = relationship(
        "OrderItem",
        back_populates="kitchen_tasks",
    )

    kitchen_section: Mapped[KitchenSection] = relationship(
        "KitchenSection",
        back_populates="kitchen_tasks",
    )

    product_kitchen_step: Mapped[ProductKitchenStep | None] = relationship(
        "ProductKitchenStep",
        back_populates="kitchen_tasks",
    )

    assigned_user: Mapped[User | None] = relationship(
        "User",
        back_populates="assigned_kitchen_tasks",
    )
