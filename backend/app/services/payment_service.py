from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.crud import order as crud_order
from app.models.order import Order
from app.models.payment import Payment


class PaymentService:
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
