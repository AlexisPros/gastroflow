from datetime import datetime
from decimal import Decimal

from app.schemas.base import OrmBaseModel


class StockMovementBase(OrmBaseModel):
    stock_item_id: int
    type: str
    quantity: Decimal
    description: str | None = None


class StockMovementCreate(StockMovementBase):
    pass


class StockMovementUpdate(OrmBaseModel):
    stock_item_id: int | None = None
    type: str | None = None
    quantity: Decimal | None = None
    description: str | None = None


class StockMovementRead(StockMovementBase):
    id: int
    created_at: datetime
