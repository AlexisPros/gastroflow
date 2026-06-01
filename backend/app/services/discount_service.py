from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import Discount
from app.models.order import Order
from app.models.order_item import OrderItem


class DiscountService:
    async def apply_discount(
        self,
        db: AsyncSession,
        *,
        order: Order,
        discount_id: int,
    ) -> Order:
        discount = await self._get_active_discount(db, discount_id=discount_id)
        base_total = await self._get_order_items_total(db, order_id=order.id)
        discount_amount = self.calculate_discount_amount(
            discount=discount,
            base_total=base_total,
        )

        order.discount_id = discount.id
        order.subtotal_amount = base_total
        order.discount_amount = discount_amount
        order.total_amount = max(base_total - discount_amount, Decimal("0.00"))

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def remove_discount(self, db: AsyncSession, *, order: Order) -> Order:
        base_total = await self._get_order_items_total(db, order_id=order.id)

        order.discount_id = None
        order.subtotal_amount = base_total
        order.discount_amount = Decimal("0.00")
        order.total_amount = base_total

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    def calculate_discount_amount(
        self,
        *,
        discount: Discount,
        base_total: Decimal,
    ) -> Decimal:
        discount_type = discount.type.upper()

        if discount_type in {"PERCENT", "PERCENTAGE"}:
            return base_total * discount.value / Decimal("100")

        if discount_type in {"AMOUNT", "FIXED"}:
            return min(discount.value, base_total)

        raise ValueError("Unsupported discount type.")

    async def _get_active_discount(
        self,
        db: AsyncSession,
        *,
        discount_id: int,
    ) -> Discount:
        result = await db.execute(
            select(Discount).where(Discount.id == discount_id),
        )
        discount = result.scalar_one_or_none()

        if discount is None:
            raise ValueError("Discount does not exist.")

        if not discount.is_active:
            raise ValueError("Discount is not active.")

        return discount

    async def _get_order_items_total(self, db: AsyncSession, *, order_id: int) -> Decimal:
        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order_id),
        )
        return sum(
            (item.total_price for item in result.scalars().all()),
            Decimal("0.00"),
        )


discount_service = DiscountService()
