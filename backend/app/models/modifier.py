from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product_modifier import ProductModifier


class Modifier(Base):
    __tablename__ = "modifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    price: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    product_modifiers: Mapped[list[ProductModifier]] = relationship(
        "ProductModifier",
        back_populates="modifier",
    )
