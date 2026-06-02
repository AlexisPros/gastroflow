from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.order import Order
from app.models.restaurant_table import RestaurantTable
from app.schemas.order import OrderCreate, OrderUpdate


class CRUDOrder(CRUDBase[Order, OrderCreate, OrderUpdate]):
    async def get_pending_qr_orders(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Order]:
        result = await db.execute(
            select(Order)
            .where(
                Order.source == "QR",
                Order.status == "PENDING_CONFIRMATION",
            )
            .order_by(Order.created_at.asc())
            .offset(skip)
            .limit(limit),
        )
        return list(result.scalars().all())

    async def change_table(
        self,
        db: AsyncSession,
        *,
        db_obj: Order,
        table_id: int | None,
    ) -> Order:
        db_obj.table_id = table_id

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def assign_discount(
        self,
        db: AsyncSession,
        *,
        db_obj: Order,
        discount_id: int | None,
    ) -> Order:
        db_obj.discount_id = discount_id

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def add_tip(
        self,
        db: AsyncSession,
        *,
        db_obj: Order,
        tip_amount: Decimal,
    ) -> Order:
        if tip_amount < Decimal("0.00"):
            raise ValueError("Tip amount must be zero or greater.")

        db_obj.tip_amount = tip_amount
        db_obj.total_amount = (
            max(
                db_obj.subtotal_amount - db_obj.discount_amount,
                Decimal("0.00"),
            )
            + tip_amount
        )

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def close(self, db: AsyncSession, *, db_obj: Order) -> Order:
        db_obj.status = "CLOSED"
        db_obj.closed_at = datetime.now(timezone.utc)

        await self._release_table_if_no_active_orders(db, order=db_obj)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def _release_table_if_no_active_orders(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> None:
        if order.table_id is None:
            return

        active_order_result = await db.execute(
            select(Order)
            .where(
                Order.table_id == order.table_id,
                Order.id != order.id,
                Order.status.in_(["PENDING_CONFIRMATION", "OPEN"]),
            )
            .limit(1),
        )
        if active_order_result.scalar_one_or_none() is not None:
            return

        table_result = await db.execute(
            select(RestaurantTable).where(RestaurantTable.id == order.table_id),
        )
        table = table_result.scalar_one_or_none()
        if table is None:
            return

        table.status = "FREE"
        table.current_guests = None
        db.add(table)


order = CRUDOrder(Order)
