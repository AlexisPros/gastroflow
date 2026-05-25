from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import kitchen_task
from app.models.kitchen_task import KitchenTask


class KitchenService:
    async def start_task(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
    ) -> KitchenTask:
        if task.status == "COMPLETED":
            raise ValueError("Completed kitchen task cannot be started again.")

        return await kitchen_task.start(db, db_obj=task)

    async def complete_task(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
    ) -> KitchenTask:
        if task.status == "COMPLETED":
            return task

        if task.started_at is None:
            task = await kitchen_task.start(db, db_obj=task)

        return await kitchen_task.complete(db, db_obj=task)


kitchen_service = KitchenService()
