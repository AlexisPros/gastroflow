from datetime import datetime
from decimal import Decimal

from app.schemas.base import OrmBaseModel


class OrderBase(OrmBaseModel):
    idempotency_key: str | None = None
    table_id: int | None = None
    waiter_id: int | None = None
    discount_id: int | None = None
    shift_id: int | None = None
    split_parent_order_id: int | None = None
    qr_parent_order_id: int | None = None
    reservation_id: int | None = None
    reservation_prepaid_amount: Decimal | None = Decimal("0.00")
    split_sequence: int | None = None
    guest_count: int | None = None
    source: str = "WAITER"
    total_amount: Decimal = Decimal("0.00")
    subtotal_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    tip_amount: Decimal = Decimal("0.00")
    estimated_time: int | None = None


class OrderCreate(OrderBase):
    pass


class OrderUpdate(OrmBaseModel):
    table_id: int | None = None
    waiter_id: int | None = None
    discount_id: int | None = None
    shift_id: int | None = None
    split_parent_order_id: int | None = None
    qr_parent_order_id: int | None = None
    reservation_id: int | None = None
    reservation_prepaid_amount: Decimal | None = None
    split_sequence: int | None = None
    guest_count: int | None = None
    source: str | None = None
    status: str | None = None
    total_amount: Decimal | None = None
    subtotal_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    tip_amount: Decimal | None = None
    estimated_time: int | None = None


class OrderRead(OrderBase):
    id: int
    version: int
    status: str
    closed_at: datetime | None = None
    created_at: datetime


class OrderMergeCandidateRead(OrmBaseModel):
    id: int
    table_id: int | None = None
    status: str
    total_amount: Decimal
    created_at: datetime
    item_count: int


class OrderMergeRequest(OrmBaseModel):
    source_order_id: int
