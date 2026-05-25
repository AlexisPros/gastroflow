from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

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
            order.status = "CLOSED"
            order.closed_at = datetime.now(timezone.utc)
            db.add(order)

        await db.commit()
        await db.refresh(payment)
        if close_order:
            await db.refresh(order)

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
        return payment


payment_service = PaymentService()
