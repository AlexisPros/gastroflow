from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate


class CRUDOrder(CRUDBase[Order, OrderCreate, OrderUpdate]):
    async def close(self, db: AsyncSession, *, db_obj: Order) -> Order:
        db_obj.status = "CLOSED"
        db_obj.closed_at = datetime.now(timezone.utc)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


order = CRUDOrder(Order)
