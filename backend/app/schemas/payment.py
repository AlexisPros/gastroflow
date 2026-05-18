from datetime import datetime

from app.schemas.base import OrmBaseModel


class PaymentBase(OrmBaseModel):
    order_id: int
    method: str
    amount: float


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(OrmBaseModel):
    order_id: int | None = None
    method: str | None = None
    amount: float | None = None
    status: str | None = None


class PaymentRead(PaymentBase):
    id: int
    status: str
    created_at: datetime
