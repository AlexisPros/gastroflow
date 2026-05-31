from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.kitchen_section import KitchenSection
    from app.models.kitchen_task import KitchenTask
    from app.models.product import Product


class ProductKitchenStep(Base):
    __tablename__ = "product_kitchen_steps"
    __table_args__ = (
        UniqueConstraint("product_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )

    kitchen_section_id: Mapped[int] = mapped_column(
        ForeignKey("kitchen_sections.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    estimated_time: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    product: Mapped[Product] = relationship(
        "Product",
        back_populates="kitchen_steps",
    )

    kitchen_section: Mapped[KitchenSection] = relationship(
        "KitchenSection",
        back_populates="product_steps",
    )

    kitchen_tasks: Mapped[list[KitchenTask]] = relationship(
        "KitchenTask",
        back_populates="product_kitchen_step",
    )
