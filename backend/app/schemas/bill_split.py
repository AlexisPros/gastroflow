from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import OrmBaseModel


class BillSplitOriginalItemRead(OrmBaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: Decimal
    assigned_quantity: Decimal
    remaining_quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    notes: str | None = None


class BillSegmentItemRead(OrmBaseModel):
    id: int
    bill_segment_id: int
    original_order_item_id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    notes: str | None = None
    modifier_snapshot: str | None = None


class BillSegmentRead(OrmBaseModel):
    id: int
    order_id: int
    name: str
    position: int
    status: str
    total_amount: Decimal
    created_at: datetime
    items: list[BillSegmentItemRead] = Field(default_factory=list)


class BillSplitViewRead(OrmBaseModel):
    order_id: int
    original_items: list[BillSplitOriginalItemRead]
    segments: list[BillSegmentRead]
    unassigned_total: Decimal


class BillSplitMoveItemInput(OrmBaseModel):
    order_item_id: int
    quantity: Decimal | None = None


class BillSplitMoveItemsRequest(OrmBaseModel):
    target_segment_id: int
    items: list[BillSplitMoveItemInput]


class BillSplitSplitItemRequest(OrmBaseModel):
    order_item_id: int
    target_segment_ids: list[int]


class BillSplitSegmentGuestCountInput(OrmBaseModel):
    segment_id: int
    guest_count: int


class BillSplitFinalizeRequest(OrmBaseModel):
    segment_guest_counts: list[BillSplitSegmentGuestCountInput]
