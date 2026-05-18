from app.schemas.base import OrmBaseModel


class OrderItemBase(OrmBaseModel):
    order_id: int
    product_id: int
    quantity: int = 1
    unit_price: float
    total_price: float
    status: str = "NEW"
    notes: str | None = None


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemUpdate(OrmBaseModel):
    order_id: int | None = None
    product_id: int | None = None
    quantity: int | None = None
    unit_price: float | None = None
    total_price: float | None = None
    status: str | None = None
    notes: str | None = None


class OrderItemRead(OrderItemBase):
    id: int
