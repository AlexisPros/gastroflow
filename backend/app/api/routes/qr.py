from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import DbSession, ORDER_ROLES, raise_bad_request, require_roles
from app.crud import order as crud_order
from app.crud import restaurant_table as crud_restaurant_table
from app.schemas import OrderRead
from app.services import order_service, user_service
from app.services.order_service import OrderItemRequest

router = APIRouter(tags=["QR"])


class PublicQRTableRead(BaseModel):
    id: int
    table_number: str
    status: str
    qr_code_url: str | None = None
    is_active: bool


class QROrderItemInput(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)
    notes: str | None = None
    product_modifier_ids: list[int] = Field(default_factory=list)


class CreateQRPendingOrderRequest(BaseModel):
    guest_count: int = Field(gt=0)
    items: list[QROrderItemInput] = Field(min_length=1)


class ConfirmQRPendingOrderRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class RejectQRPendingOrderRequest(BaseModel):
    pin: str = Field(min_length=4, max_length=12)
    reason: str | None = Field(default=None, max_length=255)


async def get_table_by_qr_token(qr_token: str, db: DbSession):
    table = await crud_restaurant_table.get_by_qr_token(
        db,
        qr_token=qr_token,
    )
    if table is None or not table.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR table not found.",
        )

    return table


@router.get("/qr/{qr_token}/table", response_model=PublicQRTableRead)
async def get_qr_table(qr_token: str, db: DbSession):
    return await get_table_by_qr_token(qr_token, db)


@router.post("/qr/{qr_token}/orders", response_model=OrderRead)
async def create_qr_pending_order(
    qr_token: str,
    body: CreateQRPendingOrderRequest,
    db: DbSession,
):
    table = await get_table_by_qr_token(qr_token, db)

    try:
        return await order_service.create_pending_qr_order(
            db,
            table_id=table.id,
            guest_count=body.guest_count,
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


async def get_service_order_user_by_pin(pin: str, db: DbSession):
    try:
        waiter = await user_service.find_service_order_user_by_pin(
            db,
            pin=pin,
        )
    except ValueError as exc:
        raise_bad_request(exc)

    if waiter is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN.",
        )

    return waiter


@router.get(
    "/qr/orders/pending",
    response_model=list[OrderRead],
    dependencies=[Depends(require_roles(ORDER_ROLES))],
)
async def list_pending_qr_orders(
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
):
    return await crud_order.get_pending_qr_orders(
        db,
        skip=skip,
        limit=limit,
    )


@router.post("/qr/orders/{order_id}/confirm", response_model=OrderRead)
async def confirm_qr_pending_order(
    order_id: int,
    body: ConfirmQRPendingOrderRequest,
    db: DbSession,
):
    order = await crud_order.get(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    waiter = await get_service_order_user_by_pin(body.pin, db)

    try:
        return await order_service.confirm_pending_qr_order(
            db,
            order=order,
            waiter_id=waiter.id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/qr/orders/{order_id}/reject", response_model=OrderRead)
async def reject_qr_pending_order(
    order_id: int,
    body: RejectQRPendingOrderRequest,
    db: DbSession,
):
    order = await crud_order.get(db, order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR order not found.",
        )

    waiter = await get_service_order_user_by_pin(body.pin, db)

    try:
        return await order_service.reject_pending_qr_order(
            db,
            order=order,
            waiter_id=waiter.id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise_bad_request(exc)
