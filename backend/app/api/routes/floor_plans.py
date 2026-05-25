from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DbSession, RequireFloorPlanRole, get_or_404, raise_bad_request
from app.crud import floor_plan as crud_floor_plan
from app.crud import floor_plan_table as crud_floor_plan_table
from app.crud import restaurant_table as crud_restaurant_table
from app.schemas import (
    FloorPlanRead,
    FloorPlanTablePositionUpdate,
    FloorPlanTableRead,
)
from app.services import floor_plan_service

router = APIRouter(
    tags=["Floor plans"],
    dependencies=[RequireFloorPlanRole],
)


class AddTableToFloorPlanRequest(BaseModel):
    table_id: int
    position: FloorPlanTablePositionUpdate


@router.get("/floor-plans/active", response_model=FloorPlanRead)
async def get_active_floor_plan(db: DbSession):
    floor_plan = await crud_floor_plan.get_active(db)
    if floor_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="active floor plan not found.",
        )

    return floor_plan


@router.post("/floor-plans/{floor_plan_id}/activate", response_model=FloorPlanRead)
async def activate_floor_plan(floor_plan_id: int, db: DbSession):
    floor_plan = await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    return await floor_plan_service.activate(db, floor_plan=floor_plan)


@router.post("/floor-plans/{floor_plan_id}/deactivate", response_model=FloorPlanRead)
async def deactivate_floor_plan(floor_plan_id: int, db: DbSession):
    floor_plan = await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    return await floor_plan_service.deactivate(db, floor_plan=floor_plan)


@router.get(
    "/floor-plans/{floor_plan_id}/tables",
    response_model=list[FloorPlanTableRead],
)
async def list_floor_plan_tables(floor_plan_id: int, db: DbSession):
    await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    return await crud_floor_plan_table.get_by_plan(
        db,
        floor_plan_id=floor_plan_id,
    )


@router.get(
    "/floor-plans/{floor_plan_id}/tables/by-restaurant-table/{table_id}",
    response_model=FloorPlanTableRead,
)
async def get_floor_plan_table_position(
    floor_plan_id: int,
    table_id: int,
    db: DbSession,
):
    await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    floor_plan_table = await crud_floor_plan_table.get_by_plan_and_table(
        db,
        floor_plan_id=floor_plan_id,
        table_id=table_id,
    )
    if floor_plan_table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="floor plan table not found.",
        )

    return floor_plan_table


@router.post(
    "/floor-plans/{floor_plan_id}/tables",
    response_model=FloorPlanTableRead,
)
async def add_table_to_floor_plan(
    floor_plan_id: int,
    body: AddTableToFloorPlanRequest,
    db: DbSession,
):
    floor_plan = await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    await get_or_404(
        crud_obj=crud_restaurant_table,
        db=db,
        id=body.table_id,
        entity_name="restaurant table",
    )
    try:
        return await floor_plan_service.add_table(
            db,
            floor_plan=floor_plan,
            table_id=body.table_id,
            position=body.position,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.patch(
    "/floor-plans/{floor_plan_id}/tables/{floor_plan_table_id}/position",
    response_model=FloorPlanTableRead,
)
async def update_floor_plan_table_position(
    floor_plan_id: int,
    floor_plan_table_id: int,
    body: FloorPlanTablePositionUpdate,
    db: DbSession,
):
    floor_plan = await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    floor_plan_table = await get_or_404(
        crud_obj=crud_floor_plan_table,
        db=db,
        id=floor_plan_table_id,
        entity_name="floor plan table",
    )
    try:
        return await floor_plan_service.update_table_position(
            db,
            floor_plan=floor_plan,
            floor_plan_table=floor_plan_table,
            position=body,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.delete(
    "/floor-plans/{floor_plan_id}/tables/{floor_plan_table_id}",
    response_model=FloorPlanTableRead,
)
async def remove_table_from_floor_plan(
    floor_plan_id: int,
    floor_plan_table_id: int,
    db: DbSession,
):
    await get_or_404(
        crud_obj=crud_floor_plan,
        db=db,
        id=floor_plan_id,
        entity_name="floor plan",
    )
    floor_plan_table = await get_or_404(
        crud_obj=crud_floor_plan_table,
        db=db,
        id=floor_plan_table_id,
        entity_name="floor plan table",
    )
    if floor_plan_table.floor_plan_id != floor_plan_id:
        raise_bad_request(
            ValueError("Table position does not belong to this floor plan."),
        )

    return await floor_plan_service.remove_table(
        db,
        floor_plan_table=floor_plan_table,
    )
