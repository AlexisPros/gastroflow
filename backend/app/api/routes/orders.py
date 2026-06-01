from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DbSession, RequireOrderRole, get_or_404, raise_bad_request
from app.core.websocket_manager import websocket_manager
from app.crud import order as crud_order
from app.crud import order_item as crud_order_item
from app.services import (
    billing_service,
    discount_service,
    order_service,
)
from app.services.order_service import OrderItemRequest
from app.schemas import (
    OrderActionLogRead,
    OrderItemRead,
    OrderRead,
    OrderTransferLogRead,
)

router = APIRouter(
    tags=["Orders"],
    dependencies=[RequireOrderRole],
)


class OrderItemInput(BaseModel):
    product_id: int
    quantity: int = 1
    notes: str | None = None
    product_modifier_ids: list[int] = Field(default_factory=list)


class CreateOrderWithItemsRequest(BaseModel):
    table_id: int | None = None
    waiter_id: int | None = None
    source: str = "WAITER"
    items: list[OrderItemInput]


class ChangeOrderTableRequest(BaseModel):
    table_id: int | None = None


class AddTipRequest(BaseModel):
    tip_amount: Decimal


class TransferOrderRequest(BaseModel):
    to_waiter_id: int


class RecordOrderActionRequest(BaseModel):
    user_id: int
    action_type: str
    description: str | None = None


class ApplyDiscountRequest(BaseModel):
    discount_id: int


class SplitOrderRequest(BaseModel):
    order_item_ids: list[int]


class MoveItemsRequest(BaseModel):
    target_order_id: int
    order_item_ids: list[int]


class SplitItemRequest(BaseModel):
    target_order_id: int
    quantity: int


@router.post("/orders/with-items", response_model=OrderRead)
async def create_order_with_items(
    body: CreateOrderWithItemsRequest,
    db: DbSession,
):
    try:
        return await order_service.create_order_with_items(
            db,
            table_id=body.table_id,
            waiter_id=body.waiter_id,
            source=body.source,
            items=[
                OrderItemRequest(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    notes=item.notes,
                    product_modifier_ids=item.product_modifier_ids,
                )
                for item in body.items
            ],
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/orders/{order_id}/recalculate", response_model=OrderRead)
async def recalculate_order_total(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await order_service.recalculate_total(db, order=order)


@router.patch("/orders/{order_id}/table", response_model=OrderRead)
async def change_order_table(
    order_id: int,
    body: ChangeOrderTableRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await crud_order.change_table(db, db_obj=order, table_id=body.table_id)


@router.patch("/orders/{order_id}/tip", response_model=OrderRead)
async def add_order_tip(order_id: int, body: AddTipRequest, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await crud_order.add_tip(db, db_obj=order, tip_amount=body.tip_amount)


@router.post("/orders/{order_id}/close", response_model=OrderRead)
async def close_order(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    order = await crud_order.close(db, db_obj=order)
    await websocket_manager.broadcast_many(
        channels=["waiters", "floor", "managers"],
        event="order_closed",
        data={
            "order_id": order.id,
            "table_id": order.table_id,
            "status": order.status,
            "table_status": "FREE",
        },
    )
    return order


@router.post("/orders/{order_id}/transfer", response_model=OrderTransferLogRead)
async def transfer_order(
    order_id: int,
    body: TransferOrderRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await order_service.transfer_order(
            db,
            order=order,
            to_waiter_id=body.to_waiter_id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/orders/{order_id}/actions", response_model=OrderActionLogRead)
async def record_order_action(
    order_id: int,
    body: RecordOrderActionRequest,
    db: DbSession,
):
    return await order_service.record_action(
        db,
        order_id=order_id,
        user_id=body.user_id,
        action_type=body.action_type,
        description=body.description,
    )


@router.post("/orders/{order_id}/discount", response_model=OrderRead)
async def apply_order_discount(
    order_id: int,
    body: ApplyDiscountRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await discount_service.apply_discount(
            db,
            order=order,
            discount_id=body.discount_id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.delete("/orders/{order_id}/discount", response_model=OrderRead)
async def remove_order_discount(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    return await discount_service.remove_discount(db, order=order)


@router.post("/orders/{source_order_id}/split", response_model=OrderRead)
async def split_order(
    source_order_id: int,
    body: SplitOrderRequest,
    db: DbSession,
):
    source_order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=source_order_id,
        entity_name="source order",
    )
    try:
        return await billing_service.split_order(
            db,
            source_order=source_order,
            order_item_ids=body.order_item_ids,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/orders/{source_order_id}/move-items", response_model=list[OrderRead])
async def move_items_between_orders(
    source_order_id: int,
    body: MoveItemsRequest,
    db: DbSession,
):
    if source_order_id == body.target_order_id:
        raise_bad_request(ValueError("Source and target order must be different."))

    source_order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=source_order_id,
        entity_name="source order",
    )
    target_order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=body.target_order_id,
        entity_name="target order",
    )
    try:
        source_order, target_order = await billing_service.move_items_to_order(
            db,
            source_order=source_order,
            target_order=target_order,
            order_item_ids=body.order_item_ids,
        )
        return [source_order, target_order]
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/order-items/{order_item_id}/split", response_model=OrderItemRead)
async def split_order_item_quantity(
    order_item_id: int,
    body: SplitItemRequest,
    db: DbSession,
):
    source_item = await get_or_404(
        crud_obj=crud_order_item,
        db=db,
        id=order_item_id,
        entity_name="order item",
    )
    target_order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=body.target_order_id,
        entity_name="target order",
    )
    try:
        return await billing_service.split_item_quantity(
            db,
            source_item=source_item,
            target_order=target_order,
            quantity=body.quantity,
        )
    except ValueError as exc:
        raise_bad_request(exc)
