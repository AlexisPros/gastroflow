from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession, RequirePaymentRole, get_or_404, raise_bad_request
from app.crud import order as crud_order
from app.crud import payment as crud_payment
from app.schemas import PaymentRead
from app.services import payment_service

router = APIRouter(
    tags=["Payments"],
    dependencies=[RequirePaymentRole],
)


class RegisterPaymentRequest(BaseModel):
    method: str
    amount: Decimal
    close_order: bool = False


class ClosedPaymentRead(BaseModel):
    payment_id: int
    order_id: int
    table_id: int | None
    method: str
    amount: Decimal
    closed_at: str | None


@router.get("/payments/current-user/closed", response_model=list[ClosedPaymentRead])
async def list_current_user_closed_payments(
    db: DbSession,
    current_user: CurrentUser,
):
    rows = await payment_service.list_closed_payments_for_user(db, user_id=current_user.id)
    return [
        ClosedPaymentRead(
            payment_id=payment.id,
            order_id=order.id,
            table_id=order.table_id,
            method=payment.method,
            amount=payment.amount,
            closed_at=order.closed_at.isoformat() if order.closed_at else None,
        )
        for payment, order in rows
    ]


@router.post("/payments/{payment_id}/toggle-method", response_model=PaymentRead)
async def toggle_payment_method(
    payment_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    payment = await get_or_404(
        crud_obj=crud_payment,
        db=db,
        id=payment_id,
        entity_name="payment",
    )
    try:
        return await payment_service.toggle_payment_method(
            db,
            payment=payment,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/orders/{order_id}/payments", response_model=PaymentRead)
async def register_payment(
    order_id: int,
    body: RegisterPaymentRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await payment_service.register_payment(
            db,
            order=order,
            method=body.method,
            amount=body.amount,
            close_order=body.close_order,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/payments/{payment_id}/cancel", response_model=PaymentRead)
async def cancel_payment(payment_id: int, db: DbSession):
    payment = await get_or_404(
        crud_obj=crud_payment,
        db=db,
        id=payment_id,
        entity_name="payment",
    )
    try:
        return await payment_service.cancel_payment(db, payment=payment)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/payments/{payment_id}/refund", response_model=PaymentRead)
async def refund_payment(payment_id: int, db: DbSession):
    payment = await get_or_404(
        crud_obj=crud_payment,
        db=db,
        id=payment_id,
        entity_name="payment",
    )
    try:
        return await payment_service.refund_payment(db, payment=payment)
    except ValueError as exc:
        raise_bad_request(exc)
