from datetime import datetime

from app.schemas.base import OrmBaseModel


class FloorPlanBase(OrmBaseModel):
    name: str
    width: int = 1200
    height: int = 800
    is_active: bool = True


class FloorPlanCreate(FloorPlanBase):
    pass


class FloorPlanUpdate(OrmBaseModel):
    name: str | None = None
    width: int | None = None
    height: int | None = None
    is_active: bool | None = None


class FloorPlanRead(FloorPlanBase):
    id: int
    created_at: datetime
