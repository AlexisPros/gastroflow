from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_plan import FloorPlan
from app.models.floor_plan_table import FloorPlanTable
from app.schemas.floor_plan_table import FloorPlanTablePositionUpdate


class FloorPlanService:
    async def activate(
        self,
        db: AsyncSession,
        *,
        floor_plan: FloorPlan,
    ) -> FloorPlan:
        await db.execute(
            update(FloorPlan)
            .where(FloorPlan.id != floor_plan.id)
            .values(is_active=False),
        )
        floor_plan.is_active = True

        db.add(floor_plan)
        await db.commit()
        await db.refresh(floor_plan)
        return floor_plan

    async def deactivate(
        self,
        db: AsyncSession,
        *,
        floor_plan: FloorPlan,
    ) -> FloorPlan:
        floor_plan.is_active = False

        db.add(floor_plan)
        await db.commit()
        await db.refresh(floor_plan)
        return floor_plan

    async def add_table(
        self,
        db: AsyncSession,
        *,
        floor_plan: FloorPlan,
        table_id: int,
        position: FloorPlanTablePositionUpdate,
    ) -> FloorPlanTable:
        self._validate_position(floor_plan, position)

        floor_plan_table = FloorPlanTable(
            floor_plan_id=floor_plan.id,
            table_id=table_id,
            x=position.x,
            y=position.y,
            width=position.width,
            height=position.height,
            rotation=position.rotation,
            shape=position.shape,
        )

        db.add(floor_plan_table)
        await db.commit()
        await db.refresh(floor_plan_table)
        return floor_plan_table

    async def update_table_position(
        self,
        db: AsyncSession,
        *,
        floor_plan: FloorPlan,
        floor_plan_table: FloorPlanTable,
        position: FloorPlanTablePositionUpdate,
    ) -> FloorPlanTable:
        if floor_plan_table.floor_plan_id != floor_plan.id:
            raise ValueError("Table position does not belong to this floor plan.")

        self._validate_position(floor_plan, position)

        floor_plan_table.x = position.x
        floor_plan_table.y = position.y
        floor_plan_table.width = position.width
        floor_plan_table.height = position.height
        floor_plan_table.rotation = position.rotation
        floor_plan_table.shape = position.shape

        db.add(floor_plan_table)
        await db.commit()
        await db.refresh(floor_plan_table)
        return floor_plan_table

    async def remove_table(
        self,
        db: AsyncSession,
        *,
        floor_plan_table: FloorPlanTable,
    ) -> FloorPlanTable:
        await db.delete(floor_plan_table)
        await db.commit()
        return floor_plan_table

    def _validate_position(
        self,
        floor_plan: FloorPlan,
        position: FloorPlanTablePositionUpdate,
    ) -> None:
        if position.width <= Decimal("0") or position.height <= Decimal("0"):
            raise ValueError("Table size must be greater than zero.")

        if position.x < Decimal("0") or position.y < Decimal("0"):
            raise ValueError("Table position cannot be negative.")

        if position.x + position.width > Decimal(floor_plan.width):
            raise ValueError("Table is outside the floor plan width.")

        if position.y + position.height > Decimal(floor_plan.height):
            raise ValueError("Table is outside the floor plan height.")


floor_plan_service = FloorPlanService()
