from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.warehouse import Warehouse


class WarehouseUserAccess(Base):
    __tablename__ = "warehouse_user_accesses"
    __table_args__ = (
        UniqueConstraint(
            "warehouse_id",
            "user_id",
            name="uq_warehouse_user_access",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    warehouse: Mapped[Warehouse] = relationship(
        "Warehouse",
        back_populates="user_accesses",
    )
    user: Mapped[User] = relationship(
        "User",
        back_populates="warehouse_accesses",
    )
