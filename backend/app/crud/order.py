from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate


class CRUDOrder(CRUDBase[Order, OrderCreate, OrderUpdate]):
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
        tip_amount: float,
    ) -> Order:
        db_obj.tip_amount = tip_amount

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def close(self, db: AsyncSession, *, db_obj: Order) -> Order:
        db_obj.status = "CLOSED"
        db_obj.closed_at = datetime.now(timezone.utc)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


order = CRUDOrder(Order)
