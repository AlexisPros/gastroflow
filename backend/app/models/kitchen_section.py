from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.kitchen_task import KitchenTask
    from app.models.product import Product
    from app.models.product_kitchen_step import ProductKitchenStep
    from app.models.user import User


class KitchenSection(Base):
    __tablename__ = "kitchen_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    products: Mapped[list[Product]] = relationship(
        "Product",
        back_populates="kitchen_section",
    )

    kitchen_tasks: Mapped[list[KitchenTask]] = relationship(
        "KitchenTask",
        back_populates="kitchen_section",
    )

    product_steps: Mapped[list[ProductKitchenStep]] = relationship(
        "ProductKitchenStep",
        back_populates="kitchen_section",
    )

    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="kitchen_section",
    )
