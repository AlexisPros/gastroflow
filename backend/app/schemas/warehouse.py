from app.schemas.base import OrmBaseModel


class WarehouseBase(OrmBaseModel):
    name: str
    type: str


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(OrmBaseModel):
    name: str | None = None
    type: str | None = None


class WarehouseRead(WarehouseBase):
    id: int
