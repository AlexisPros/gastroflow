from datetime import datetime
from decimal import Decimal

from app.schemas.base import OrmBaseModel


class OrderBase(OrmBaseModel):
    table_id: int | None = None
    waiter_id: int | None = None
    discount_id: int | None = None
    source: str = "WAITER"
    total_amount: Decimal = Decimal("0.00")
    tip_amount: Decimal = Decimal("0.00")


class OrderCreate(OrderBase):
    pass


class OrderUpdate(OrmBaseModel):
    table_id: int | None = None
    waiter_id: int | None = None
    discount_id: int | None = None
    source: str | None = None
    status: str | None = None
    total_amount: Decimal | None = None
    tip_amount: Decimal | None = None


class OrderRead(OrderBase):
    id: int
    status: str
    closed_at: datetime | None = None
    created_at: datetime
