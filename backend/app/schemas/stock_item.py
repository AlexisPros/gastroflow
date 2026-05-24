from app.schemas.base import OrmBaseModel
from decimal import Decimal

class StockItemBase(OrmBaseModel):
    warehouse_id: int
    ingredient_id: int
    quantity: Decimal
    minimum_quantity: Decimal | None = None


class StockItemCreate(StockItemBase):
    pass


class StockItemUpdate(OrmBaseModel):
    warehouse_id: int | None = None
    ingredient_id: int | None = None
    quantity: Decimal | None = None
    minimum_quantity: Decimal | None = None


class StockItemRead(StockItemBase):
    id: int
