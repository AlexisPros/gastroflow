from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.order_action_log import OrderActionLog
from app.schemas.order_action_log import OrderActionLogCreate, OrderActionLogUpdate


class CRUDOrderActionLog(
    CRUDBase[OrderActionLog, OrderActionLogCreate, OrderActionLogUpdate],
):
    async def record(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        user_id: int,
        action_type: str,
        description: str | None = None,
    ) -> OrderActionLog:
        db_obj = OrderActionLog(
            order_id=order_id,
            user_id=user_id,
            action_type=action_type,
            description=description,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


order_action_log = CRUDOrderActionLog(OrderActionLog)
