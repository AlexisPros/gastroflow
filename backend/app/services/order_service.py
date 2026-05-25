from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import order_action_log, order_transfer_log
from app.models.kitchen_task import KitchenTask
from app.models.modifier import Modifier
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.product import Product
from app.models.product_modifier import ProductModifier


@dataclass(slots=True)
class OrderItemRequest:
    product_id: int
    quantity: int = 1
    notes: str | None = None
    product_modifier_ids: list[int] = field(default_factory=list)


class OrderService:
    async def create_order_with_items(
        self,
        db: AsyncSession,
        *,
        table_id: int | None = None,
        waiter_id: int | None = None,
        source: str = "WAITER",
        items: list[OrderItemRequest],
    ) -> Order:
        if not items:
            raise ValueError("Order must contain at least one item.")

        order = Order(
            table_id=table_id,
            waiter_id=waiter_id,
            source=source,
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        await db.flush()

        total_amount = Decimal("0.00")

        for item_request in items:
            order_item, item_total = await self._create_order_item(
                db,
                order_id=order.id,
                item_request=item_request,
            )
            total_amount += item_total
            await self._create_kitchen_task_for_item(db, order_item=order_item)

        order.total_amount = total_amount

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def recalculate_total(self, db: AsyncSession, *, order: Order) -> Order:
        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id),
        )
        order_items = result.scalars().all()

        order.total_amount = sum(
            (item.total_price for item in order_items),
            Decimal("0.00"),
        )

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def transfer_order(
        self,
        db: AsyncSession,
        *,
        order: Order,
        to_waiter_id: int,
    ):
        return await order_transfer_log.transfer_order(
            db,
            order=order,
            to_waiter_id=to_waiter_id,
        )

    async def record_action(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        user_id: int,
        action_type: str,
        description: str | None = None,
    ):
        return await order_action_log.record(
            db,
            order_id=order_id,
            user_id=user_id,
            action_type=action_type,
            description=description,
        )

    async def _create_order_item(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        item_request: OrderItemRequest,
    ) -> tuple[OrderItem, Decimal]:
        if item_request.quantity <= 0:
            raise ValueError("Order item quantity must be greater than zero.")

        product = await self._get_active_product(db, product_id=item_request.product_id)
        modifier_total = Decimal("0.00")

        order_item = OrderItem(
            order_id=order_id,
            product_id=product.id,
            quantity=item_request.quantity,
            unit_price=product.price,
            total_price=Decimal("0.00"),
            notes=item_request.notes,
        )
        db.add(order_item)
        await db.flush()

        for product_modifier_id in item_request.product_modifier_ids:
            modifier_price = await self._get_product_modifier_price(
                db,
                product_id=product.id,
                product_modifier_id=product_modifier_id,
            )
            modifier_total += modifier_price

            db.add(
                OrderItemModifier(
                    order_item_id=order_item.id,
                    product_modifier_id=product_modifier_id,
                    price=modifier_price,
                ),
            )

        item_total = (product.price + modifier_total) * item_request.quantity
        order_item.total_price = item_total

        db.add(order_item)
        await db.flush()
        return order_item, item_total

    async def _create_kitchen_task_for_item(
        self,
        db: AsyncSession,
        *,
        order_item: OrderItem,
    ) -> None:
        product = await self._get_active_product(db, product_id=order_item.product_id)
        if product.kitchen_section_id is None:
            return

        db.add(
            KitchenTask(
                order_item_id=order_item.id,
                kitchen_section_id=product.kitchen_section_id,
                estimated_time=product.preparation_time,
            ),
        )
        await db.flush()

    async def _get_active_product(self, db: AsyncSession, *, product_id: int) -> Product:
        result = await db.execute(
            select(Product).where(Product.id == product_id),
        )
        product = result.scalar_one_or_none()

        if product is None:
            raise ValueError("Product does not exist.")

        if not product.is_active:
            raise ValueError("Product is not active.")

        return product

    async def _get_product_modifier_price(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        product_modifier_id: int,
    ) -> Decimal:
        result = await db.execute(
            select(ProductModifier, Modifier)
            .join(Modifier, ProductModifier.modifier_id == Modifier.id)
            .where(
                ProductModifier.id == product_modifier_id,
                ProductModifier.product_id == product_id,
                ProductModifier.is_active.is_(True),
                Modifier.is_active.is_(True),
            ),
        )
        row = result.one_or_none()

        if row is None:
            raise ValueError("Product modifier is not available for this product.")

        product_modifier, modifier = row
        return product_modifier.price_override or modifier.price


order_service = OrderService()
