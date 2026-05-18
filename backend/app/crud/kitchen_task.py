from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.kitchen_task import KitchenTask
from app.schemas.kitchen_task import KitchenTaskCreate, KitchenTaskUpdate


class CRUDKitchenTask(CRUDBase[KitchenTask, KitchenTaskCreate, KitchenTaskUpdate]):
    async def start(self, db: AsyncSession, *, db_obj: KitchenTask) -> KitchenTask:
        db_obj.status = "IN_PROGRESS"
        db_obj.started_at = datetime.now(timezone.utc)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def complete(self, db: AsyncSession, *, db_obj: KitchenTask) -> KitchenTask:
        db_obj.status = "COMPLETED"
        db_obj.completed_at = datetime.now(timezone.utc)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


kitchen_task = CRUDKitchenTask(KitchenTask)
