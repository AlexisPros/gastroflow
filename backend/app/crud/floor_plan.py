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


floor_plan = CRUDFloorPlan(FloorPlan)
