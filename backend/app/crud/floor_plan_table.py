from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.floor_plan_table import FloorPlanTable
from app.schemas.floor_plan_table import FloorPlanTableCreate, FloorPlanTableUpdate


class CRUDFloorPlanTable(
    CRUDBase[FloorPlanTable, FloorPlanTableCreate, FloorPlanTableUpdate],
):
    async def get_by_plan(
        self,
        db: AsyncSession,
        *,
        floor_plan_id: int,
    ) -> list[FloorPlanTable]:
        result = await db.execute(
            select(FloorPlanTable).where(
                FloorPlanTable.floor_plan_id == floor_plan_id,
            ),
        )
        return list(result.scalars().all())

    async def get_by_plan_and_table(
        self,
        db: AsyncSession,
        *,
        floor_plan_id: int,
        table_id: int,
    ) -> FloorPlanTable | None:
        result = await db.execute(
            select(FloorPlanTable).where(
                FloorPlanTable.floor_plan_id == floor_plan_id,
                FloorPlanTable.table_id == table_id,
            ),
        )
        return result.scalar_one_or_none()


floor_plan_table = CRUDFloorPlanTable(FloorPlanTable)
