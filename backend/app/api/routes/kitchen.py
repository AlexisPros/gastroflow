from fastapi import APIRouter

from app.api.deps import DbSession, get_or_404, raise_bad_request
from app.crud import kitchen_task as crud_kitchen_task
from app.schemas import KitchenTaskRead
from app.services import kitchen_service

router = APIRouter(tags=["Kitchen"])


@router.post("/kitchen-tasks/{task_id}/start", response_model=KitchenTaskRead)
async def start_kitchen_task(task_id: int, db: DbSession):
    task = await get_or_404(
        crud_obj=crud_kitchen_task,
        db=db,
        id=task_id,
        entity_name="kitchen task",
    )
    try:
        return await kitchen_service.start_task(db, task=task)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/kitchen-tasks/{task_id}/complete", response_model=KitchenTaskRead)
async def complete_kitchen_task(task_id: int, db: DbSession):
    task = await get_or_404(
        crud_obj=crud_kitchen_task,
        db=db,
        id=task_id,
        entity_name="kitchen task",
    )
    try:
        return await kitchen_service.complete_task(db, task=task)
    except ValueError as exc:
        raise_bad_request(exc)
