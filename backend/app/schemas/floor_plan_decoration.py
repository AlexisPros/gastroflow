from decimal import Decimal

from app.schemas.base import OrmBaseModel


class FloorPlanDecorationBase(OrmBaseModel):
    floor_plan_id: int
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    rotation: Decimal = Decimal("0.00")
    shape: str = "RECTANGLE"
    color: str = "#252b2d"
    label: str | None = None


class FloorPlanDecorationCreate(FloorPlanDecorationBase):
    pass


class FloorPlanDecorationUpdate(OrmBaseModel):
    floor_plan_id: int | None = None
    x: Decimal | None = None
    y: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    rotation: Decimal | None = None
    shape: str | None = None
    color: str | None = None
    label: str | None = None


class FloorPlanDecorationRead(FloorPlanDecorationBase):
    id: int
