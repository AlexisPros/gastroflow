from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.warehouse_document import WarehouseDocument


class WarehouseDocumentItem(Base):
    __tablename__ = "warehouse_document_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    warehouse_document_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    document: Mapped[WarehouseDocument] = relationship(
        "WarehouseDocument",
        back_populates="items",
    )
    ingredient: Mapped[Ingredient] = relationship("Ingredient")
