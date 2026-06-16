from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.order import Order
from app.models.order_transfer_log import OrderTransferLog
from app.schemas.order_transfer_log import OrderTransferLogCreate, OrderTransferLogUpdate


class CRUDOrderTransferLog(
    CRUDBase[OrderTransferLog, OrderTransferLogCreate, OrderTransferLogUpdate],
):
    async def transfer(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        from_waiter_id: int,
        to_waiter_id: int,
    ) -> OrderTransferLog:
        db_obj = OrderTransferLog(
            order_id=order_id,
            from_waiter_id=from_waiter_id,
            to_waiter_id=to_waiter_id,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def transfer_order(
        self,
        db: AsyncSession,
        *,
        order: Order,
        to_waiter_id: int,
        shift_id: int,
    ) -> OrderTransferLog:
        if order.waiter_id is None:
            raise ValueError("Order must have a waiter before it can be transferred.")

        db_obj = OrderTransferLog(
            order_id=order.id,
            from_waiter_id=order.waiter_id,
            to_waiter_id=to_waiter_id,
        )
        order.waiter_id = to_waiter_id
        order.shift_id = shift_id

        db.add(order)
        db.add(db_obj)
        await db.commit()
        await db.refresh(order)
        await db.refresh(db_obj)
        return db_obj


order_transfer_log = CRUDOrderTransferLog(OrderTransferLog)
