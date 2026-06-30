from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import (
    CurrentUser,
    DbSession,
    RequirePaymentRole,
    get_or_404,
    raise_bad_request,
    raise_forbidden,
)
from app.crud import order as crud_order
from app.crud import payment as crud_payment
from app.schemas import OrderRead, PaymentRead
from app.services import authorization_service, order_service, payment_service
from app.services.payment_service import PaymentInput

router = APIRouter(
    tags=["Payments"],
    dependencies=[RequirePaymentRole],
)


class RegisterPaymentRequest(BaseModel):
    method: str
    amount: Decimal
    close_order: bool = False


class PaymentPartRequest(BaseModel):
    method: str
    amount: Decimal = Field(gt=0)
    cash_received: Decimal | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, max_length=100)


class CloseOrderWithPaymentsRequest(BaseModel):
    payments: list[PaymentPartRequest] = Field(default_factory=list, max_length=2)


class CloseOrderWithPaymentsResponse(BaseModel):
    order: OrderRead
    payments: list[PaymentRead]
    change_due: Decimal


class ChangePaymentMethodRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)
    manager_pin: str | None = Field(default=None, min_length=4, max_length=12)


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
    body: ChangePaymentMethodRequest,
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
        authorized_user_id = current_user.id
        if current_user.role not in {"ADMIN", "MANAGER"}:
            if not body.manager_pin:
                raise ValueError("Manager PIN is required.")
            manager = await order_service.verify_manager_pin(
                db,
                manager_pin=body.manager_pin,
            )
            authorized_user_id = manager.id
        return await payment_service.toggle_payment_method(
            db,
            payment=payment,
            user_id=current_user.id,
            authorized_user_id=authorized_user_id,
            can_manage_all=current_user.role in {"ADMIN", "MANAGER"},
            reason=body.reason,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/orders/{order_id}/payments", response_model=PaymentRead)
async def register_payment(
    order_id: int,
    body: RegisterPaymentRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        authorization_service.require_order_access(user=current_user, order=order)
    except PermissionError as exc:
        raise_forbidden(exc)
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


@router.post(
    "/orders/{order_id}/close-with-payments",
    response_model=CloseOrderWithPaymentsResponse,
)
async def close_order_with_payments(
    order_id: int,
    body: CloseOrderWithPaymentsRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    try:
        payment_inputs: list[PaymentInput] = [
            {
                "method": item.method,
                "amount": item.amount,
                "cash_received": item.cash_received,
                "idempotency_key": item.idempotency_key,
            }
            for item in body.payments
        ]
        order, payments, change_due = await payment_service.close_order_with_payments(
            db,
            order_id=order_id,
            user_id=current_user.id,
            can_manage_all=current_user.role in {"ADMIN", "MANAGER"},
            payments=payment_inputs,
        )
        return CloseOrderWithPaymentsResponse(
            order=order,
            payments=payments,
            change_due=change_due,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/payments/{payment_id}/cancel", response_model=PaymentRead)
async def cancel_payment(payment_id: int, db: DbSession, current_user: CurrentUser):
    if current_user.role not in {"ADMIN", "MANAGER"}:
        raise_forbidden(PermissionError("Only a manager can cancel a payment."))
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
async def refund_payment(payment_id: int, db: DbSession, current_user: CurrentUser):
    if current_user.role not in {"ADMIN", "MANAGER"}:
        raise_forbidden(PermissionError("Only a manager can refund a payment."))
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
