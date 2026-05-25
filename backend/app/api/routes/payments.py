from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DbSession, RequirePaymentRole, get_or_404, raise_bad_request
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
