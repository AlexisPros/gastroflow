from datetime import datetime

from app.schemas.base import OrmBaseModel


class OrderActionLogBase(OrmBaseModel):
    order_id: int
    user_id: int
    action_type: str
    description: str | None = None


class OrderActionLogCreate(OrderActionLogBase):
    pass


class OrderActionLogUpdate(OrmBaseModel):
    order_id: int | None = None
    user_id: int | None = None
    action_type: str | None = None
    description: str | None = None
    created_at: datetime | None = None


class OrderActionLogRead(OrderActionLogBase):
    id: int
    created_at: datetime
