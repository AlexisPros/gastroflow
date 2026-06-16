from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    parent_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_categories.id"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    department: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="KITCHEN",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    parent: Mapped["ProductCategory | None"] = relationship(
        remote_side=[id],
        back_populates="children",
    )

    children: Mapped[list["ProductCategory"]] = relationship(
        back_populates="parent",
    )

    products: Mapped[list[Product]] = relationship(
        "Product",
        back_populates="category",
    )
