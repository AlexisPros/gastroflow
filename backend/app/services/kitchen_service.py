from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
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
        if task.status == "NEW":
            raise ValueError("Kitchen order must be accepted before the task can be started.")
        if task.status not in {"PENDING", "IN_PROGRESS"}:
            raise ValueError("Kitchen task cannot be started from its current status.")

        task = await kitchen_task.start(db, db_obj=task)
        await websocket_manager.broadcast_many(
            channels=["kitchen", "bar", "waiters"],
            event="kitchen_task_started",
            data={
                "task_id": task.id,
                "order_item_id": task.order_item_id,
                "kitchen_section_id": task.kitchen_section_id,
                "status": task.status,
            },
        )
        return task

    async def complete_task(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
    ) -> KitchenTask:
        if task.status == "COMPLETED":
            return task

        if task.status == "NEW":
            raise ValueError("Kitchen order must be accepted before the task can be completed.")
        if task.status not in {"PENDING", "IN_PROGRESS"}:
            raise ValueError("Kitchen task cannot be completed from its current status.")

        if task.started_at is None:
            task = await kitchen_task.start(db, db_obj=task)

        task = await kitchen_task.complete(db, db_obj=task)
        await websocket_manager.broadcast_many(
            channels=["kitchen", "bar", "waiters"],
            event="kitchen_task_completed",
            data={
                "task_id": task.id,
                "order_item_id": task.order_item_id,
                "kitchen_section_id": task.kitchen_section_id,
                "status": task.status,
            },
        )
        return task


kitchen_service = KitchenService()
