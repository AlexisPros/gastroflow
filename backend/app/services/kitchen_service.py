from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import websocket_manager
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.order_item import OrderItem


class KitchenService:
    async def _load_order_for_task(
        self,
        db: AsyncSession,
        *,
        order_item_id: int,
    ) -> Order | None:
        result = await db.execute(
            select(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(OrderItem.id == order_item_id)
            .options(
                selectinload(Order.table),
                selectinload(Order.items).selectinload(OrderItem.kitchen_tasks),
            )
        )
        return result.scalar_one_or_none()

    async def _load_order_item_tasks(
        self,
        db: AsyncSession,
        *,
        order_item_id: int,
    ) -> list[KitchenTask]:
        result = await db.execute(
            select(KitchenTask)
            .where(KitchenTask.order_item_id == order_item_id)
            .options(selectinload(KitchenTask.product_kitchen_step))
        )
        return list(result.scalars().all())

    @staticmethod
    def _step_sequence(task: KitchenTask) -> int | None:
        if task.product_kitchen_step is None:
            return None
        return task.product_kitchen_step.sequence

    @staticmethod
    def _depends_on_sequence(task: KitchenTask) -> int | None:
        if task.product_kitchen_step is None:
            return None
        return task.product_kitchen_step.depends_on_sequence

    def _dependency_completed(
        self,
        tasks: list[KitchenTask],
        *,
        depends_on_sequence: int | None,
    ) -> bool:
        if depends_on_sequence is None:
            return True

        dependency_tasks = [
            task
            for task in tasks
            if self._step_sequence(task) == depends_on_sequence
        ]
        return bool(dependency_tasks) and all(
            task.status == "COMPLETED" for task in dependency_tasks
        )

    def _ready_to_start_tasks(
        self,
        tasks: list[KitchenTask],
    ) -> list[KitchenTask]:
        return [
            task
            for task in tasks
            if task.status == "PENDING"
            and self._dependency_completed(
                tasks,
                depends_on_sequence=self._depends_on_sequence(task),
            )
        ]

    async def _broadcast_task_event(
        self,
        *,
        event: str,
        task: KitchenTask,
    ) -> None:
        await websocket_manager.broadcast_many(
            channels=["kitchen", "bar", "waiters"],
            event=event,
            data={
                "task_id": task.id,
                "order_item_id": task.order_item_id,
                "kitchen_section_id": task.kitchen_section_id,
                "status": task.status,
            },
        )

    async def broadcast_section_ready_if_complete(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
        section_id: int,
        event: str,
        department: str,
        channels: list[str],
    ) -> bool:
        order = await self._load_order_for_task(
            db,
            order_item_id=task.order_item_id,
        )
        if order is None or order.status != "OPEN":
            return False

        section_tasks = [
            section_task
            for item in order.items
            for section_task in item.kitchen_tasks
            if section_task.kitchen_section_id == section_id
        ]
        if not section_tasks or any(
            section_task.status != "COMPLETED"
            for section_task in section_tasks
        ):
            return False

        updated_items = False
        for item in order.items:
            item_section_tasks = [
                item_task
                for item_task in item.kitchen_tasks
                if item_task.kitchen_section_id == section_id
            ]
            if (
                item_section_tasks
                and all(item_task.status == "COMPLETED" for item_task in item.kitchen_tasks)
                and item.status not in {"READY", "COMPLETED"}
            ):
                item.status = "READY"
                db.add(item)
                updated_items = True

        if updated_items:
            await db.commit()

        await websocket_manager.broadcast_many(
            channels=channels,
            event=event,
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "table_number": order.table.table_number if order.table else None,
                "waiter_id": order.waiter_id,
                "department": department,
            },
        )
        return True

    async def start_task(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
        allow_new: bool = False,
        start_section_id: int | None = None,
    ) -> KitchenTask:
        if task.status == "COMPLETED":
            raise ValueError("Completed kitchen task cannot be started again.")
        if task.status == "NEW" and not allow_new:
            raise ValueError("Kitchen order must be accepted before the task can be started.")
        if task.status not in {"NEW", "PENDING", "IN_PROGRESS"}:
            raise ValueError("Kitchen task cannot be started from its current status.")

        tasks = await self._load_order_item_tasks(db, order_item_id=task.order_item_id)
        current_task = next((item for item in tasks if item.id == task.id), task)
        depends_on_sequence = self._depends_on_sequence(current_task)

        if not self._dependency_completed(tasks, depends_on_sequence=depends_on_sequence):
            raise ValueError("Previous kitchen step must be completed before this task can be started.")

        startable_statuses = {"PENDING"}
        if allow_new:
            startable_statuses.add("NEW")

        tasks_to_start = [
            item
            for item in tasks
            if item.status in startable_statuses
            and self._depends_on_sequence(item) == depends_on_sequence
            and (start_section_id is None or item.kitchen_section_id == start_section_id)
            and self._dependency_completed(
                tasks,
                depends_on_sequence=self._depends_on_sequence(item),
            )
        ]
        if current_task.status == "IN_PROGRESS":
            tasks_to_start = [
                item
                for item in tasks_to_start
                if item.id != current_task.id
            ]

        started_at = datetime.now(timezone.utc)
        for item in tasks_to_start:
            item.status = "IN_PROGRESS"
            if item.started_at is None:
                item.started_at = started_at
            db.add(item)

        if tasks_to_start:
            await db.commit()
            for item in tasks_to_start:
                await db.refresh(item)
                await self._broadcast_task_event(event="kitchen_task_started", task=item)
        elif current_task.status == "IN_PROGRESS":
            await db.refresh(current_task)

        return current_task

    async def _start_ready_following_tasks(
        self,
        db: AsyncSession,
        *,
        tasks: list[KitchenTask],
    ) -> list[KitchenTask]:
        ready_tasks = self._ready_to_start_tasks(tasks)
        started_at = datetime.now(timezone.utc)

        for item in ready_tasks:
            item.status = "IN_PROGRESS"
            if item.started_at is None:
                item.started_at = started_at
            db.add(item)

        return ready_tasks

    def _ensure_task_can_be_completed(
        self,
        *,
        task: KitchenTask,
        tasks: list[KitchenTask],
    ) -> None:
        if task.status == "COMPLETED":
            return

        if task.status == "NEW":
            raise ValueError("Kitchen order must be accepted before the task can be completed.")
        if task.status not in {"PENDING", "IN_PROGRESS"}:
            raise ValueError("Kitchen task cannot be completed from its current status.")

        depends_on_sequence = self._depends_on_sequence(task)
        if not self._dependency_completed(tasks, depends_on_sequence=depends_on_sequence):
            raise ValueError("Previous kitchen step must be completed before this task can be completed.")

    async def _finish_task_and_start_following(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
    ) -> tuple[KitchenTask, list[KitchenTask]]:
        tasks = await self._load_order_item_tasks(db, order_item_id=task.order_item_id)
        current_task = next((item for item in tasks if item.id == task.id), task)

        self._ensure_task_can_be_completed(task=current_task, tasks=tasks)
        if current_task.status == "COMPLETED":
            return current_task, []

        completed_at = datetime.now(timezone.utc)
        if current_task.started_at is None:
            current_task.started_at = completed_at
        current_task.status = "COMPLETED"
        current_task.completed_at = completed_at
        db.add(current_task)

        following_tasks = await self._start_ready_following_tasks(
            db,
            tasks=tasks,
        )

        await db.commit()
        await db.refresh(current_task)
        for item in following_tasks:
            await db.refresh(item)

        return current_task, following_tasks

    async def complete_task(
        self,
        db: AsyncSession,
        *,
        task: KitchenTask,
    ) -> KitchenTask:
        if task.status == "COMPLETED":
            return task

        completed_task, started_tasks = await self._finish_task_and_start_following(db, task=task)
        await self._broadcast_task_event(event="kitchen_task_completed", task=completed_task)
        for started_task in started_tasks:
            await self._broadcast_task_event(event="kitchen_task_started", task=started_task)

        return completed_task


kitchen_service = KitchenService()
