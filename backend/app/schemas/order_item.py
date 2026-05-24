from app.schemas.base import OrmBaseModel
from decimal import Decimal

class OrderItemBase(OrmBaseModel):
    order_id: int
    product_id: int
    quantity: int = 1
    unit_price: Decimal
    total_price: Decimal
    notes: str | None = None


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemUpdate(OrmBaseModel):
    order_id: int | None = None
    product_id: int | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    status: str | None = None
    notes: str | None = None


class OrderItemRead(OrderItemBase):
    id: int
    status: str
