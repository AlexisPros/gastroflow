from datetime import datetime, timezone
from decimal import Decimal
from typing import NotRequired, TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.crud import order as crud_order
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.payment import Payment


class PaymentInput(TypedDict):
    method: str
    amount: Decimal
    cash_received: NotRequired[Decimal | None]
    idempotency_key: NotRequired[str | None]


class PaymentService:
    async def close_order_with_payments(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        user_id: int,
        can_manage_all: bool = False,
        payments: list[PaymentInput],
    ) -> tuple[Order, list[Payment], Decimal]:
        result = await db.execute(
            select(Order).where(Order.id == order_id).with_for_update(),
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found.")
        if not can_manage_all and order.waiter_id != user_id:
            raise ValueError("Only the owner of the order can close it.")

        idempotency_keys = [
            str(item["idempotency_key"])
            for item in payments
            if item.get("idempotency_key")
        ]
        if idempotency_keys:
            existing_by_key_result = await db.execute(
                select(Payment).where(Payment.idempotency_key.in_(idempotency_keys)),
            )
            existing_by_key: dict[str, Payment] = {
                payment.idempotency_key: payment
                for payment in existing_by_key_result.scalars().all()
                if payment.idempotency_key is not None
            }
            if existing_by_key:
                if (
                    len(idempotency_keys) != len(payments)
                    or len(existing_by_key) != len(payments)
                ):
                    raise ValueError("Payment request was only partially processed.")

                existing_payments: list[Payment] = []
                for item in payments:
                    key = str(item["idempotency_key"])
                    existing_payment = existing_by_key.get(key)
                    if existing_payment is None:
                        raise ValueError("Payment request was only partially processed.")
                    requested_cash_received = item.get("cash_received")
                    if (
                        existing_payment.order_id != order.id
                        or existing_payment.status != "COMPLETED"
                        or existing_payment.method.upper() != str(item["method"]).upper()
                        or existing_payment.amount != Decimal(item["amount"])
                        or (
                            requested_cash_received is not None
                            and existing_payment.cash_received
                            != Decimal(requested_cash_received)
                        )
                    ):
                        raise ValueError("Idempotency key was reused with different payment data.")
                    existing_payments.append(existing_payment)

                if order.status != "CLOSED":
                    raise ValueError("Processed payments belong to an order that is not closed.")
                change_due = Decimal("0.00")
                for payment in existing_payments:
                    change_due += payment.change_given or Decimal("0.00")
                return (
                    order,
                    existing_payments,
                    change_due,
                )

        if order.status not in {"OPEN", "IN_PROGRESS"}:
            raise ValueError("Only an active order can be paid.")
        if not payments:
            raise ValueError("At least one payment is required.")

        existing_result = await db.execute(
            select(Payment).where(
                Payment.order_id == order.id,
                Payment.status == "COMPLETED",
            ),
        )
        if existing_result.scalars().first() is not None:
            raise ValueError("Order already has a completed payment.")

        created: list[Payment] = []
        payment_methods: set[str] = set()
        payment_total = Decimal("0.00")
        cash_received_total = Decimal("0.00")
        cash_due_total = Decimal("0.00")
        for item in payments:
            method = str(item["method"]).upper()
            amount = Decimal(item["amount"])
            idempotency_key = item.get("idempotency_key")
            cash_received = item.get("cash_received")
            if method not in {"CARD", "CASH"}:
                raise ValueError("Payment method must be CARD or CASH.")
            if method in payment_methods:
                raise ValueError("Each payment method can only appear once.")
            payment_methods.add(method)
            if amount <= 0:
                raise ValueError("Payment amount must be greater than zero.")
            if idempotency_key:
                duplicate_result = await db.execute(
                    select(Payment).where(Payment.idempotency_key == idempotency_key),
                )
                duplicate = duplicate_result.scalar_one_or_none()
                if duplicate is not None:
                    raise ValueError("This payment request was already processed.")

            if method == "CASH":
                received = amount if cash_received is None else Decimal(cash_received)
                if received < amount:
                    raise ValueError("Cash received cannot be lower than the cash payment.")
                cash_received_total += received
                cash_due_total += amount
                change_given = received - amount
            else:
                received = None
                change_given = None

            payment = Payment(
                order_id=order.id,
                method=method,
                amount=amount,
                cash_received=received,
                change_given=change_given,
                idempotency_key=idempotency_key,
            )
            db.add(payment)
            created.append(payment)
            payment_total += amount

        if payment_total != order.total_amount:
            raise ValueError("Payment total must exactly match the order total.")

        order.status = "CLOSED"
        order.closed_at = datetime.now(timezone.utc)
        await crud_order._release_table_if_no_active_orders(db, order=order)
        db.add(order)
        await db.commit()
        await db.refresh(order)
        for payment in created:
            await db.refresh(payment)

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
        return order, created, cash_received_total - cash_due_total

    async def list_closed_payments_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> list[tuple[Payment, Order]]:
        result = await db.execute(
            select(Payment, Order)
            .join(Order, Order.id == Payment.order_id)
            .where(
                Order.waiter_id == user_id,
                Order.status == "CLOSED",
                Payment.status == "COMPLETED",
                Payment.method.in_(["CARD", "CASH"]),
            )
            .order_by(Order.closed_at.desc(), Payment.created_at.desc()),
        )
        return list(result.all())

    async def toggle_payment_method(
        self,
        db: AsyncSession,
        *,
        payment: Payment,
        user_id: int,
        authorized_user_id: int,
        can_manage_all: bool,
        reason: str,
    ) -> Payment:
        result = await db.execute(select(Order).where(Order.id == payment.order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found.")
        if not can_manage_all and order.waiter_id != user_id:
            raise ValueError("Only the owner of the order can change its payment method.")
        if order.status != "CLOSED":
            raise ValueError("Payment method can only be changed for a closed order.")
        if payment.status != "COMPLETED":
            raise ValueError("Only a completed payment can be changed.")

        other_payments_result = await db.execute(
            select(Payment).where(
                Payment.order_id == order.id,
                Payment.id != payment.id,
                Payment.status == "COMPLETED",
            ),
        )
        if other_payments_result.scalars().first() is not None:
            raise ValueError("Mixed payment methods cannot be toggled.")

        current_method = payment.method.upper()
        if current_method not in {"CARD", "CASH"}:
            raise ValueError("Only CARD and CASH payment methods can be changed.")

        next_method = "CASH" if current_method == "CARD" else "CARD"
        payment.method = next_method
        if next_method == "CASH":
            payment.cash_received = payment.amount
            payment.change_given = Decimal("0.00")
        else:
            payment.cash_received = None
            payment.change_given = None
        db.add(payment)
        db.add(
            OrderActionLog(
                order_id=order.id,
                user_id=authorized_user_id,
                action_type="PAYMENT_METHOD_CHANGED",
                description=(
                    f"Payment method changed from {current_method} to {next_method}. "
                    f"Reason: {reason}"
                ),
            ),
        )
        await db.commit()
        await db.refresh(payment)
        await websocket_manager.broadcast_many(
            channels=["waiters", "managers"],
            event="payment_method_changed",
            data={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "method": payment.method,
            },
        )
        return payment

    async def register_payment(
        self,
        db: AsyncSession,
        *,
        order: Order,
        method: str,
        amount: Decimal,
        close_order: bool = False,
    ) -> Payment:
        method = method.upper()
        if method not in {"CARD", "CASH"}:
            raise ValueError("Payment method must be CARD or CASH.")
        if order.status not in {"OPEN", "IN_PROGRESS"}:
            raise ValueError("Only an active order can receive payments.")
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        total_result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00"))).where(
                Payment.order_id == order.id,
                Payment.status == "COMPLETED",
            ),
        )
        paid_total = Decimal(total_result.scalar_one())
        if paid_total + amount > order.total_amount:
            raise ValueError("Payment would exceed the order total.")
        if close_order and paid_total + amount != order.total_amount:
            raise ValueError("Order can only close when fully paid.")

        payment = Payment(
            order_id=order.id,
            method=method,
            amount=amount,
        )
        db.add(payment)

        if close_order:
            await crud_order.close(db, db_obj=order)
        else:
            await db.commit()

        await db.refresh(payment)
        await websocket_manager.broadcast_many(
            channels=["waiters", "managers"],
            event="payment_registered",
            data={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "method": payment.method,
                "amount": str(payment.amount),
                "close_order": close_order,
            },
        )
        if close_order:
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

        return payment

    async def cancel_payment(
        self,
        db: AsyncSession,
        *,
        payment: Payment,
    ) -> Payment:
        if payment.status == "REFUNDED":
            raise ValueError("Refunded payment cannot be cancelled.")

        payment.status = "CANCELLED"

        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        await websocket_manager.broadcast_many(
            channels=["waiters", "managers"],
            event="payment_cancelled",
            data={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "status": payment.status,
            },
        )
        return payment

    async def refund_payment(
        self,
        db: AsyncSession,
        *,
        payment: Payment,
    ) -> Payment:
        if payment.status == "CANCELLED":
            raise ValueError("Cancelled payment cannot be refunded.")

        payment.status = "REFUNDED"

        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        await websocket_manager.broadcast_many(
            channels=["waiters", "managers"],
            event="payment_refunded",
            data={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "status": payment.status,
            },
        )
        return payment


payment_service = PaymentService()
