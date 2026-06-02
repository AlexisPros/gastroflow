from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.floor_plan_decoration import FloorPlanDecoration
from app.schemas.floor_plan_decoration import (
    FloorPlanDecorationCreate,
    FloorPlanDecorationUpdate,
)


class CRUDFloorPlanDecoration(
    CRUDBase[
        FloorPlanDecoration,
        FloorPlanDecorationCreate,
        FloorPlanDecorationUpdate,
    ],
):
    async def get_by_plan(
        self,
        db: AsyncSession,
        *,
        floor_plan_id: int,
    ) -> list[FloorPlanDecoration]:
        result = await db.execute(
            select(FloorPlanDecoration)
            .where(FloorPlanDecoration.floor_plan_id == floor_plan_id)
            .order_by(FloorPlanDecoration.id.asc()),
        )
        return list(result.scalars().all())


floor_plan_decoration = CRUDFloorPlanDecoration(FloorPlanDecoration)
