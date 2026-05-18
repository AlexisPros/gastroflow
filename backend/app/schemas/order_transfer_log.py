from datetime import datetime

from app.schemas.base import OrmBaseModel


class OrderTransferLogBase(OrmBaseModel):
    order_id: int
    from_waiter_id: int
    to_waiter_id: int


class OrderTransferLogCreate(OrderTransferLogBase):
    pass


class OrderTransferLogUpdate(OrmBaseModel):
    order_id: int | None = None
    from_waiter_id: int | None = None
    to_waiter_id: int | None = None


class OrderTransferLogRead(OrderTransferLogBase):
    id: int
    transferred_at: datetime
