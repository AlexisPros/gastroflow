from datetime import datetime
from decimal import Decimal

from app.schemas.base import OrmBaseModel


class PaymentBase(OrmBaseModel):
    order_id: int
    idempotency_key: str | None = None
    method: str
    amount: Decimal
    cash_received: Decimal | None = None
    change_given: Decimal | None = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(OrmBaseModel):
    order_id: int | None = None
    method: str | None = None
    amount: Decimal | None = None
    status: str | None = None


class PaymentRead(PaymentBase):
    id: int
    status: str
    created_at: datetime
