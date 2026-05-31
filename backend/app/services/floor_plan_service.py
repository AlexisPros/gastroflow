from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_plan import FloorPlan
from app.models.floor_plan_table import FloorPlanTable
from app.models.restaurant_table import RestaurantTable
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

    async def create_restaurant_table_on_plan(
        self,
        db: AsyncSession,
        *,
        floor_plan: FloorPlan,
        table_number: str,
        position: FloorPlanTablePositionUpdate,
        current_guests: int | None = None,
        qr_code_url: str | None = None,
        is_active: bool = True,
    ) -> FloorPlanTable:
        self._validate_position(floor_plan, position)
        await self._validate_new_restaurant_table(
            db,
            table_number=table_number,
            qr_code_url=qr_code_url,
            current_guests=current_guests,
        )

        table = RestaurantTable(
            table_number=table_number,
            current_guests=current_guests,
            status="FREE",
            qr_code_url=qr_code_url,
            is_active=is_active,
        )
        db.add(table)
        await db.flush()

        floor_plan_table = FloorPlanTable(
            floor_plan_id=floor_plan.id,
            table_id=table.id,
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

    async def _validate_new_restaurant_table(
        self,
        db: AsyncSession,
        *,
        table_number: str,
        qr_code_url: str | None,
        current_guests: int | None,
    ) -> None:
        if current_guests is not None and current_guests < 0:
            raise ValueError("Current guests cannot be negative.")

        result = await db.execute(
            select(RestaurantTable).where(
                RestaurantTable.table_number == table_number,
            ),
        )
        if result.scalar_one_or_none() is not None:
            raise ValueError("Restaurant table number already exists.")

        if qr_code_url is None:
            return

        result = await db.execute(
            select(RestaurantTable).where(
                RestaurantTable.qr_code_url == qr_code_url,
            ),
        )
        if result.scalar_one_or_none() is not None:
            raise ValueError("Restaurant table QR code URL already exists.")


floor_plan_service = FloorPlanService()
