from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import order_action_log, order_transfer_log, product_kitchen_step
from app.models.kitchen_task import KitchenTask
from app.models.modifier import Modifier
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.product import Product
from app.models.product_modifier import ProductModifier
from app.models.restaurant_table import RestaurantTable


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
        item_estimates: list[int] = []

        for item_request in items:
            order_item, item_total = await self._create_order_item(
                db,
                order_id=order.id,
                item_request=item_request,
            )
            total_amount += item_total
            item_estimated_time = await self._create_kitchen_task_for_item(
                db,
                order_item=order_item,
            )
            if item_estimated_time is not None:
                item_estimates.append(item_estimated_time)

        order.total_amount = total_amount
        order.estimated_time = max(item_estimates) if item_estimates else None

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def create_pending_qr_order(
        self,
        db: AsyncSession,
        *,
        table_id: int,
        guest_count: int,
        items: list[OrderItemRequest],
    ) -> Order:
        if guest_count <= 0:
            raise ValueError("Guest count must be greater than zero.")

        if not items:
            raise ValueError("Order must contain at least one item.")

        await self._ensure_table_accepts_qr_order(db, table_id=table_id)

        order = Order(
            table_id=table_id,
            waiter_id=None,
            guest_count=guest_count,
            source="QR",
            status="PENDING_CONFIRMATION",
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        await db.flush()

        total_amount = Decimal("0.00")

        for item_request in items:
            _, item_total = await self._create_order_item(
                db,
                order_id=order.id,
                item_request=item_request,
            )
            total_amount += item_total

        order.total_amount = total_amount

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def reject_pending_qr_order(
        self,
        db: AsyncSession,
        *,
        order: Order,
        waiter_id: int,
        reason: str | None = None,
    ) -> Order:
        if order.source != "QR":
            raise ValueError("Only QR orders can be rejected with this operation.")

        if order.status != "PENDING_CONFIRMATION":
            raise ValueError("QR order is not pending confirmation.")

        order.waiter_id = waiter_id
        order.status = "REJECTED"

        db.add(
            OrderActionLog(
                order_id=order.id,
                user_id=waiter_id,
                action_type="QR_ORDER_REJECTED",
                description=reason or "QR order rejected by waiter PIN.",
            ),
        )
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
        order.estimated_time = await self._calculate_order_estimated_time(
            db,
            order_items=list(order_items),
        )

        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    async def _ensure_table_accepts_qr_order(
        self,
        db: AsyncSession,
        *,
        table_id: int,
    ) -> None:
        result = await db.execute(
            select(RestaurantTable).where(RestaurantTable.id == table_id),
        )
        table = result.scalar_one_or_none()

        if table is None:
            raise ValueError("Restaurant table does not exist.")

        if not table.is_active:
            raise ValueError("Restaurant table is not active.")

        if table.status != "FREE":
            raise ValueError("Restaurant table is not free.")

        active_order_result = await db.execute(
            select(Order)
            .where(
                Order.table_id == table_id,
                Order.status.in_(["PENDING_CONFIRMATION", "OPEN"]),
            )
            .limit(1),
        )
        if active_order_result.scalar_one_or_none() is not None:
            raise ValueError("Restaurant table already has an active order.")

    async def confirm_pending_qr_order(
        self,
        db: AsyncSession,
        *,
        order: Order,
        waiter_id: int,
    ) -> Order:
        if order.source != "QR":
            raise ValueError("Only QR orders can be confirmed with this operation.")

        if order.status != "PENDING_CONFIRMATION":
            raise ValueError("QR order is not pending confirmation.")

        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id),
        )
        order_items = list(result.scalars().all())

        if not order_items:
            raise ValueError("QR order must contain at least one item.")

        item_estimates: list[int] = []
        for order_item in order_items:
            item_estimated_time = await self._create_kitchen_task_for_item(
                db,
                order_item=order_item,
            )
            if item_estimated_time is not None:
                item_estimates.append(item_estimated_time)

        order.waiter_id = waiter_id
        order.status = "OPEN"
        order.estimated_time = max(item_estimates) if item_estimates else None

        db.add(
            OrderActionLog(
                order_id=order.id,
                user_id=waiter_id,
                action_type="QR_ORDER_CONFIRMED",
                description="QR order confirmed by waiter PIN.",
            ),
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
    ) -> int | None:
        (
            has_existing_tasks,
            existing_estimated_time,
        ) = await self._get_existing_kitchen_task_estimated_time(
            db,
            order_item_id=order_item.id,
        )
        if has_existing_tasks:
            return existing_estimated_time

        product = await self._get_active_product(db, product_id=order_item.product_id)
        kitchen_steps = await product_kitchen_step.get_active_by_product(
            db,
            product_id=product.id,
        )
        if kitchen_steps:
            for step in kitchen_steps:
                db.add(
                    KitchenTask(
                        order_item_id=order_item.id,
                        kitchen_section_id=step.kitchen_section_id,
                        product_kitchen_step_id=step.id,
                        estimated_time=step.estimated_time,
                    ),
                )
            await db.flush()
            return self._calculate_product_estimated_time(
                [step.estimated_time for step in kitchen_steps],
            )

        if product.kitchen_section_id is None:
            return None

        db.add(
            KitchenTask(
                order_item_id=order_item.id,
                kitchen_section_id=product.kitchen_section_id,
                estimated_time=product.preparation_time,
            ),
        )
        await db.flush()
        return product.preparation_time

    async def _get_existing_kitchen_task_estimated_time(
        self,
        db: AsyncSession,
        *,
        order_item_id: int,
    ) -> tuple[bool, int | None]:
        result = await db.execute(
            select(KitchenTask.estimated_time).where(
                KitchenTask.order_item_id == order_item_id,
            ),
        )
        estimates = list(result.scalars().all())
        known_estimates = [
            estimate
            for estimate in estimates
            if estimate is not None
        ]
        return bool(estimates), max(known_estimates) if known_estimates else None

    def _calculate_product_estimated_time(
        self,
        step_estimates: list[int | None],
    ) -> int | None:
        known_estimates = [
            estimate
            for estimate in step_estimates
            if estimate is not None
        ]
        return max(known_estimates) if known_estimates else None

    async def _calculate_order_estimated_time(
        self,
        db: AsyncSession,
        *,
        order_items: list[OrderItem],
    ) -> int | None:
        order_item_ids = [item.id for item in order_items]
        if not order_item_ids:
            return None

        result = await db.execute(
            select(KitchenTask.estimated_time).where(
                KitchenTask.order_item_id.in_(order_item_ids),
                KitchenTask.estimated_time.is_not(None),
            ),
        )
        estimates = [
            estimate
            for estimate in result.scalars().all()
            if estimate is not None
        ]
        return max(estimates) if estimates else None

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
