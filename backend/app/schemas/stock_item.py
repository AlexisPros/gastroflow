from app.schemas.base import OrmBaseModel


class StockItemBase(OrmBaseModel):
    warehouse_id: int
    ingredient_id: int
    quantity: float
    minimum_quantity: float | None = None


class StockItemCreate(StockItemBase):
    pass


class StockItemUpdate(OrmBaseModel):
    warehouse_id: int | None = None
    ingredient_id: int | None = None
    quantity: float | None = None
    minimum_quantity: float | None = None


class StockItemRead(StockItemBase):
    id: int
