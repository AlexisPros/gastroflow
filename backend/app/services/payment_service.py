from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.crud import order as crud_order
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.payment import Payment


class PaymentService:
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
    ) -> Payment:
        result = await db.execute(select(Order).where(Order.id == payment.order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found.")
        if order.waiter_id != user_id:
            raise ValueError("Only the owner of the order can change its payment method.")
        if order.status != "CLOSED":
            raise ValueError("Payment method can only be changed for a closed order.")
        if payment.status != "COMPLETED":
            raise ValueError("Only a completed payment can be changed.")

        current_method = payment.method.upper()
        if current_method not in {"CARD", "CASH"}:
            raise ValueError("Only CARD and CASH payment methods can be changed.")

        next_method = "CASH" if current_method == "CARD" else "CARD"
        payment.method = next_method
        db.add(payment)
        db.add(
            OrderActionLog(
                order_id=order.id,
                user_id=user_id,
                action_type="PAYMENT_METHOD_CHANGED",
                description=f"Payment method changed from {current_method} to {next_method}.",
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
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero.")

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
