from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.kitchen_section import KitchenSection
    from app.models.order_item import OrderItem
    from app.models.product_category import ProductCategory
    from app.models.product_ingredient import ProductIngredient
    from app.models.product_kitchen_step import ProductKitchenStep
    from app.models.product_modifier import ProductModifier
    from app.models.warehouse import Warehouse


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("product_categories.id"),
        nullable=False,
    )

    kitchen_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("kitchen_sections.id"),
        nullable=True,
    )

    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("8.00"),
    )

    preparation_time: Mapped[int | None] = mapped_column(
        Integer,
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

    category: Mapped[ProductCategory] = relationship(
        "ProductCategory",
        back_populates="products",
    )

    kitchen_section: Mapped[KitchenSection | None] = relationship(
        "KitchenSection",
        back_populates="products",
    )

    warehouse: Mapped[Warehouse | None] = relationship(
        "Warehouse",
    )

    product_modifiers: Mapped[list[ProductModifier]] = relationship(
        "ProductModifier",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    product_ingredients: Mapped[list[ProductIngredient]] = relationship(
        "ProductIngredient",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    kitchen_steps: Mapped[list[ProductKitchenStep]] = relationship(
        "ProductKitchenStep",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    order_items: Mapped[list[OrderItem]] = relationship(
        "OrderItem",
        back_populates="product",
    )
