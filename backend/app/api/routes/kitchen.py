from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, RequireKitchenRole, get_or_404, raise_bad_request, CurrentUser
from app.core.websocket_manager import websocket_manager
from app.crud import kitchen_task as crud_kitchen_task
from app.models.kitchen_section import KitchenSection
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.kitchen_task import KitchenTask
from app.schemas import (
    KitchenTaskRead,
    KitchenOrderRead,
    KitchenOrderItemRead,
    KitchenSectionTaskRead,
)
from app.services import kitchen_service, stock_service

router = APIRouter(
    tags=["Kitchen"],
    dependencies=[RequireKitchenRole],
)

ORDER_QUEUE_ROLES = {"ADMIN", "MANAGER", "CHEF", "WYDAWKA"}
ALL_SECTION_TASK_ROLES = {"ADMIN", "MANAGER", "CHEF"}


async def _get_bar_section_id(db: DbSession) -> int | None:
    result = await db.execute(
        select(KitchenSection.id).where(KitchenSection.name.ilike("bar")),
    )
    return result.scalar_one_or_none()


async def _get_wydawka_section_id(db: DbSession) -> int | None:
    result = await db.execute(
        select(KitchenSection.id).where(KitchenSection.name.ilike("wydawka")),
    )
    return result.scalar_one_or_none()


def _require_order_queue_access(current_user: CurrentUser) -> None:
    if current_user.role not in ORDER_QUEUE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only kitchen pass roles can manage kitchen order queue.",
        )


def _require_section_access(
    *,
    current_user: CurrentUser,
    target_section_id: int | None,
    bar_section_id: int | None,
    wydawka_section_id: int | None = None,
) -> None:
    if current_user.role in ALL_SECTION_TASK_ROLES:
        return

    if current_user.role == "BARTENDER":
        if bar_section_id is not None and target_section_id == bar_section_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bartender can only access bar tasks.",
        )

    if current_user.role == "KITCHEN":
        if current_user.kitchen_section_id is not None and target_section_id == current_user.kitchen_section_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kitchen user can only access assigned kitchen section tasks.",
        )

    if current_user.role == "WYDAWKA":
        if current_user.kitchen_section_id is not None and target_section_id == current_user.kitchen_section_id:
            return
        if wydawka_section_id is not None and target_section_id == wydawka_section_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kitchen pass user can only complete kitchen pass tasks.",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="User does not have permission for section tasks.",
    )


def _require_task_access(
    *,
    current_user: CurrentUser,
    task: KitchenTask,
    bar_section_id: int | None,
    wydawka_section_id: int | None = None,
) -> None:
    _require_section_access(
        current_user=current_user,
        target_section_id=task.kitchen_section_id,
        bar_section_id=bar_section_id,
        wydawka_section_id=wydawka_section_id,
    )


@router.get("/kitchen/orders/active", response_model=list[KitchenOrderRead])
async def list_active_kitchen_orders(db: DbSession, current_user: CurrentUser):
    _require_order_queue_access(current_user)
    bar_section_id = await _get_bar_section_id(db)

    query = (
        select(Order)
        .where(Order.status == "OPEN")
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .outerjoin(KitchenTask, KitchenTask.order_item_id == OrderItem.id)
    )
    if bar_section_id is not None:
        query = query.where(KitchenTask.kitchen_section_id != bar_section_id)

    result = await db.execute(
        query
        .options(
            selectinload(Order.table),
            selectinload(Order.waiter),
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.kitchen_tasks).selectinload(KitchenTask.product_kitchen_step),
        )
        .distinct()
        .order_by(Order.created_at.asc())
    )
    orders = result.scalars().all()

    response = []
    for order in orders:
        items_read = []
        for item in order.items:
            visible_tasks = item.kitchen_tasks
            if bar_section_id is not None:
                visible_tasks = [
                    task
                    for task in item.kitchen_tasks
                    if task.kitchen_section_id != bar_section_id
                ]

            if not visible_tasks:
                continue

            if item.status in {"KITCHEN_READY", "READY", "COMPLETED"} and all(
                task.status == "COMPLETED" for task in visible_tasks
            ):
                continue

            items_read.append(
                KitchenOrderItemRead(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=item.product.name,
                    quantity=item.quantity,
                    notes=item.notes,
                    course_number=item.course_number,
                    status=item.status,
                    created_at=item.created_at,
                    kitchen_tasks=[
                        KitchenTaskRead(
                            id=task.id,
                            order_item_id=task.order_item_id,
                            kitchen_section_id=task.kitchen_section_id,
                            product_kitchen_step_id=task.product_kitchen_step_id,
                            assigned_user_id=task.assigned_user_id,
                            estimated_time=task.estimated_time,
                            status=task.status,
                            started_at=task.started_at,
                            completed_at=task.completed_at,
                            step_name=task.product_kitchen_step.name if task.product_kitchen_step else None,
                            step_description=task.product_kitchen_step.description if task.product_kitchen_step else None,
                        )
                        for task in visible_tasks
                    ]
                )
            )
        if len(order.items) > 0 and not items_read:
            continue

        waiter_name = f"{order.waiter.first_name} {order.waiter.last_name}" if order.waiter else None
        response.append(
            KitchenOrderRead(
                id=order.id,
                table_id=order.table_id,
                table_number=order.table.table_number if order.table else None,
                waiter_name=waiter_name,
                created_at=order.created_at,
                status=order.status,
                estimated_time=order.estimated_time,
                items=items_read
            )
        )
    return response


@router.post("/kitchen/orders/{order_id}/accept")
async def accept_kitchen_order(order_id: int, db: DbSession, current_user: CurrentUser):
    _require_order_queue_access(current_user)
    bar_section_id = await _get_bar_section_id(db)
    order_result = await db.execute(
        select(Order).where(Order.id == order_id),
    )
    order = order_result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "OPEN":
        raise_bad_request(ValueError("Only open orders can be accepted by kitchen pass."))

    tasks_query = (
        select(KitchenTask)
        .join(OrderItem, OrderItem.id == KitchenTask.order_item_id)
        .where(OrderItem.order_id == order_id)
        .where(KitchenTask.status == "NEW")
    )
    if bar_section_id is not None:
        tasks_query = tasks_query.where(KitchenTask.kitchen_section_id != bar_section_id)

    result = await db.execute(tasks_query)
    tasks = result.scalars().all()
    for task in tasks:
        task.status = "PENDING"
        db.add(task)

    result_items = await db.execute(
        select(OrderItem)
        .where(OrderItem.order_id == order_id)
        .where(OrderItem.status == "NEW")
    )
    items = result_items.scalars().all()
    for item in items:
        tasks_for_item_query = (
            select(KitchenTask)
            .where(KitchenTask.order_item_id == item.id)
        )
        if bar_section_id is not None:
            tasks_for_item_query = tasks_for_item_query.where(
                KitchenTask.kitchen_section_id != bar_section_id
            )

        result_tasks_for_item = await db.execute(tasks_for_item_query)
        if result_tasks_for_item.scalars().first():
            item.status = "PENDING"
            db.add(item)

    await stock_service.consume_order_stock(db, order_id=order_id)

    await db.commit()

    await websocket_manager.broadcast_many(
        channels=["kitchen", "bar", "waiters"],
        event="kitchen_order_accepted",
        data={"order_id": order_id},
    )
    return {"success": True}


@router.post("/kitchen/orders/{order_id}/complete")
async def complete_kitchen_order(order_id: int, db: DbSession, current_user: CurrentUser):
    _require_order_queue_access(current_user)
    bar_section_id = await _get_bar_section_id(db)

    # Preload items to avoid lazy-loading MissingGreenlet errors
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.kitchen_tasks))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tasks_res = await db.execute(
        select(KitchenTask)
        .join(OrderItem, OrderItem.id == KitchenTask.order_item_id)
        .where(OrderItem.order_id == order_id)
    )
    all_tasks = list(tasks_res.scalars().all())
    kitchen_tasks = [
        task
        for task in all_tasks
        if bar_section_id is None or task.kitchen_section_id != bar_section_id
    ]
    if not kitchen_tasks:
        raise_bad_request(ValueError("Order has no kitchen tasks to issue."))

    unfinished_tasks = [task for task in kitchen_tasks if task.status != "COMPLETED"]
    if unfinished_tasks:
        raise_bad_request(ValueError("All kitchen tasks must be completed before issuing the order."))

    newly_ready_items = False
    for item in order.items:
        item_kitchen_tasks = [
            task
            for task in item.kitchen_tasks
            if bar_section_id is None or task.kitchen_section_id != bar_section_id
        ]
        if (
            item_kitchen_tasks
            and all(task.status == "COMPLETED" for task in item_kitchen_tasks)
            and item.status not in {"KITCHEN_READY", "READY", "COMPLETED"}
        ):
            item.status = (
                "READY"
                if all(task.status == "COMPLETED" for task in item.kitchen_tasks)
                else "KITCHEN_READY"
            )
            db.add(item)
            newly_ready_items = True

    await db.commit()

    if not newly_ready_items:
        return {"success": True}

    table_number = None
    if order.table_id:
        from app.crud import restaurant_table as crud_table
        table = await crud_table.get(db, order.table_id)
        if table:
            table_number = table.table_number

    await websocket_manager.broadcast_many(
        channels=["waiters", "kitchen", "bar", "floor", "public_qr"],
        event="kitchen_order_ready",
        data={
            "order_id": order.id,
            "table_id": order.table_id,
            "table_number": table_number,
            "waiter_id": order.waiter_id,
            "department": "KITCHEN",
            "public_status": "READY",
        },
    )
    return {"success": True}


@router.post("/kitchen/orders/{order_id}/courses/{course_number}/complete")
async def complete_kitchen_course(
    order_id: int,
    course_number: int,
    db: DbSession,
    current_user: CurrentUser,
):
    _require_order_queue_access(current_user)
    if course_number <= 0:
        raise_bad_request(ValueError("Course number must be greater than zero."))

    bar_section_id = await _get_bar_section_id(db)
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.kitchen_tasks))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "OPEN":
        raise_bad_request(ValueError("Only an open order can have a course issued."))

    kitchen_items: list[tuple[OrderItem, list[KitchenTask]]] = []
    for item in order.items:
        item_kitchen_tasks = [
            task
            for task in item.kitchen_tasks
            if bar_section_id is None or task.kitchen_section_id != bar_section_id
        ]
        if item_kitchen_tasks:
            kitchen_items.append((item, item_kitchen_tasks))

    ready_statuses = {"KITCHEN_READY", "READY", "COMPLETED"}
    pending_courses = sorted(
        {
            item.course_number
            for item, _tasks in kitchen_items
            if item.status not in ready_statuses
        }
    )
    if not pending_courses:
        return {"success": True, "course_number": course_number}
    if course_number != pending_courses[0]:
        raise_bad_request(
            ValueError(f"Course {pending_courses[0]} must be issued first."),
        )

    course_items = [
        (item, tasks)
        for item, tasks in kitchen_items
        if item.course_number == course_number
    ]
    if not course_items:
        raise_bad_request(ValueError("Order has no kitchen items in this course."))
    if any(
        task.status != "COMPLETED"
        for _item, tasks in course_items
        for task in tasks
    ):
        raise_bad_request(
            ValueError("All kitchen tasks in this course must be completed before issuing it."),
        )

    for item, _tasks in course_items:
        item.status = (
            "READY"
            if all(task.status == "COMPLETED" for task in item.kitchen_tasks)
            else "KITCHEN_READY"
        )
        db.add(item)

    await db.commit()

    table_number = None
    if order.table_id:
        from app.crud import restaurant_table as crud_table

        table = await crud_table.get(db, order.table_id)
        if table:
            table_number = table.table_number

    event_data = {
        "order_id": order.id,
        "table_id": order.table_id,
        "table_number": table_number,
        "waiter_id": order.waiter_id,
        "department": "KITCHEN",
        "course_number": course_number,
    }
    await websocket_manager.broadcast_many(
        channels=["waiters", "kitchen"],
        event="kitchen_course_ready",
        data=event_data,
    )

    all_kitchen_courses_issued = all(
        item.status in ready_statuses
        for item, _tasks in kitchen_items
    )
    if all_kitchen_courses_issued:
        await websocket_manager.broadcast_many(
            channels=["public_qr"],
            event="kitchen_order_ready",
            data={**event_data, "public_status": "READY"},
        )

    return {"success": True, "course_number": course_number}


@router.get("/kitchen/tasks/active", response_model=list[KitchenSectionTaskRead])
async def list_active_section_tasks(
    db: DbSession,
    current_user: CurrentUser,
    section_id: int | None = None,
):
    target_section_id = section_id
    if target_section_id is None:
        target_section_id = current_user.kitchen_section_id

    active_statuses = ["PENDING", "IN_PROGRESS"]
    bar_section_id = await _get_bar_section_id(db)
    if bar_section_id is not None and target_section_id == bar_section_id:
        active_statuses.append("NEW")

    query = (
        select(KitchenTask)
        .join(OrderItem, OrderItem.id == KitchenTask.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == "OPEN")
        .where(KitchenTask.status.in_(active_statuses))
    )

    wydawka_section_id = await _get_wydawka_section_id(db) if current_user.role == "WYDAWKA" else None
    _require_section_access(
        current_user=current_user,
        target_section_id=target_section_id,
        bar_section_id=bar_section_id,
        wydawka_section_id=wydawka_section_id,
    )

    if target_section_id is not None:
        query = query.where(KitchenTask.kitchen_section_id == target_section_id)
    elif bar_section_id is not None:
        query = query.where(KitchenTask.kitchen_section_id != bar_section_id)

    query = query.options(
        selectinload(KitchenTask.order_item).selectinload(OrderItem.product),
        selectinload(KitchenTask.order_item).selectinload(OrderItem.order).selectinload(Order.table),
        selectinload(KitchenTask.product_kitchen_step),
    ).order_by(Order.created_at.asc(), OrderItem.position.asc())

    result = await db.execute(query)
    tasks = list(result.scalars().all())

    all_tasks_by_item_id: dict[int, list[KitchenTask]] = {}
    order_item_ids = {task.order_item_id for task in tasks}
    if order_item_ids:
        all_tasks_result = await db.execute(
            select(KitchenTask)
            .where(KitchenTask.order_item_id.in_(order_item_ids))
            .options(selectinload(KitchenTask.product_kitchen_step))
        )
        for item_task in all_tasks_result.scalars().all():
            all_tasks_by_item_id.setdefault(item_task.order_item_id, []).append(item_task)

    response = []
    allow_new = bar_section_id is not None and target_section_id == bar_section_id
    for task in tasks:
        item = task.order_item
        order = item.order
        step_name = task.product_kitchen_step.name if task.product_kitchen_step else None
        step_description = task.product_kitchen_step.description if task.product_kitchen_step else None
        step_sequence = task.product_kitchen_step.sequence if task.product_kitchen_step else None
        depends_on_sequence = (
            task.product_kitchen_step.depends_on_sequence
            if task.product_kitchen_step
            else None
        )
        can_start, blocked_by_step_name = kitchen_service.get_task_start_state(
            task=task,
            tasks=all_tasks_by_item_id.get(task.order_item_id, [task]),
            allow_new=allow_new,
        )

        response.append(
            KitchenSectionTaskRead(
                id=task.id,
                order_id=order.id,
                order_item_id=item.id,
                kitchen_section_id=task.kitchen_section_id,
                order_created_at=order.created_at,
                item_created_at=item.created_at,
                order_estimated_time=order.estimated_time,
                table_number=order.table.table_number if order.table else None,
                product_name=item.product.name,
                quantity=item.quantity,
                notes=item.notes,
                course_number=item.course_number,
                status=task.status,
                estimated_time=task.estimated_time,
                step_name=step_name,
                step_description=step_description,
                step_sequence=step_sequence,
                depends_on_sequence=depends_on_sequence,
                can_start=can_start,
                blocked_by_step_name=blocked_by_step_name,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )
        )
    return response


@router.post("/kitchen-tasks/{task_id}/start", response_model=KitchenTaskRead)
async def start_kitchen_task(task_id: int, db: DbSession, current_user: CurrentUser):
    if current_user.role == "WYDAWKA":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kitchen pass can only complete its own issuing steps.",
        )
    task = await get_or_404(
        crud_obj=crud_kitchen_task,
        db=db,
        id=task_id,
        entity_name="kitchen task",
    )
    _require_task_access(
        current_user=current_user,
        task=task,
        bar_section_id=await _get_bar_section_id(db) if current_user.role == "BARTENDER" else None,
        wydawka_section_id=await _get_wydawka_section_id(db) if current_user.role == "WYDAWKA" else None,
    )
    try:
        if current_user.role == "BARTENDER":
            bar_section_id = await _get_bar_section_id(db)
            started_task = await kitchen_service.start_task(
                db,
                task=task,
                allow_new=True,
                start_section_id=bar_section_id,
            )
            await stock_service.consume_order_item_stock(
                db,
                order_item_id=task.order_item_id,
            )
            await db.commit()
            return started_task
        return await kitchen_service.start_task(db, task=task)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/kitchen-tasks/{task_id}/complete", response_model=KitchenTaskRead)
async def complete_kitchen_task(task_id: int, db: DbSession, current_user: CurrentUser):
    task = await get_or_404(
        crud_obj=crud_kitchen_task,
        db=db,
        id=task_id,
        entity_name="kitchen task",
    )
    bar_section_id = (
        await _get_bar_section_id(db)
        if current_user.role == "BARTENDER"
        else None
    )
    _require_task_access(
        current_user=current_user,
        task=task,
        bar_section_id=bar_section_id,
        wydawka_section_id=await _get_wydawka_section_id(db) if current_user.role == "WYDAWKA" else None,
    )
    try:
        was_completed = task.status == "COMPLETED"
        completed_task = await kitchen_service.complete_task(
            db,
            task=task,
            allow_new_following=current_user.role == "BARTENDER",
            start_section_id=bar_section_id,
        )

        if not was_completed and current_user.role in ALL_SECTION_TASK_ROLES | {"BARTENDER"}:
            if bar_section_id is None:
                bar_section_id = await _get_bar_section_id(db)
            if (
                bar_section_id is not None
                and completed_task.kitchen_section_id == bar_section_id
            ):
                await kitchen_service.broadcast_section_ready_if_complete(
                    db,
                    task=completed_task,
                    section_id=bar_section_id,
                    event="bar_order_ready",
                    department="BAR",
                    channels=["waiters", "bar"],
                )

        return completed_task
    except ValueError as exc:
        raise_bad_request(exc)
