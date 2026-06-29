from app.schemas.base import OrmBaseModel


class WarehouseBase(OrmBaseModel):
    name: str
    type: str = "GENERAL"
    is_active: bool = True
    is_default: bool = False


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(OrmBaseModel):
    name: str | None = None
    type: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class WarehouseRead(WarehouseBase):
    id: int
