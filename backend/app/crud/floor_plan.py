from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.floor_plan import FloorPlan
from app.schemas.floor_plan import FloorPlanCreate, FloorPlanUpdate


class CRUDFloorPlan(CRUDBase[FloorPlan, FloorPlanCreate, FloorPlanUpdate]):
    async def get_active(self, db: AsyncSession) -> FloorPlan | None:
        result = await db.execute(
            select(FloorPlan).where(FloorPlan.is_active.is_(True)).limit(1),
        )
        return result.scalar_one_or_none()

    async def delete(self, db: AsyncSession, *, id: int) -> FloorPlan | None:
        from app.models.floor_plan_decoration import FloorPlanDecoration
        from app.models.floor_plan_table import FloorPlanTable
        from sqlalchemy import delete

        await db.execute(delete(FloorPlanDecoration).where(FloorPlanDecoration.floor_plan_id == id))
        await db.execute(delete(FloorPlanTable).where(FloorPlanTable.floor_plan_id == id))

        return await super().delete(db, id=id)


floor_plan = CRUDFloorPlan(FloorPlan)
