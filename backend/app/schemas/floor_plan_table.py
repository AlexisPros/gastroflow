from decimal import Decimal

from app.schemas.base import OrmBaseModel


class FloorPlanTableBase(OrmBaseModel):
    floor_plan_id: int
    table_id: int
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    rotation: Decimal = Decimal("0.00")
    shape: str = "RECTANGLE"


class FloorPlanTableCreate(FloorPlanTableBase):
    pass


class FloorPlanTableUpdate(OrmBaseModel):
    floor_plan_id: int | None = None
    table_id: int | None = None
    x: Decimal | None = None
    y: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    rotation: Decimal | None = None
    shape: str | None = None


class FloorPlanTablePositionUpdate(OrmBaseModel):
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    rotation: Decimal = Decimal("0.00")
    shape: str = "RECTANGLE"


class FloorPlanTableRead(FloorPlanTableBase):
    id: int
