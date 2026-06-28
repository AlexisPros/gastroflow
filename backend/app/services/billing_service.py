from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.models.bill_segment import BillSegment
from app.models.invoice import Invoice
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.payment import Payment


class BillingService:
    async def move_items_to_order(
        self,
        db: AsyncSession,
        *,
        source_order: Order,
        target_order: Order,
        order_item_ids: list[int],
    ) -> tuple[Order, Order]:
        if not order_item_ids:
            raise ValueError("At least one order item is required.")

        items = await self._get_order_items(
            db,
            order_id=source_order.id,
            order_item_ids=order_item_ids,
        )

        for item in items:
            item.order_id = target_order.id
            db.add(item)

        await db.flush()
        await self._recalculate_orders(db, source_order, target_order)
        return source_order, target_order

    async def split_order(
        self,
        db: AsyncSession,
        *,
        source_order: Order,
        order_item_ids: list[int],
    ) -> Order:
        target_order = Order(
            table_id=source_order.table_id,
            waiter_id=source_order.waiter_id,
            source=source_order.source,
            total_amount=Decimal("0.00"),
        )
        db.add(target_order)
        await db.flush()

        await self.move_items_to_order(
            db,
            source_order=source_order,
            target_order=target_order,
            order_item_ids=order_item_ids,
        )
        await db.refresh(target_order)
        return target_order

    async def merge_orders(
        self,
        db: AsyncSession,
        *,
        target_order: Order,
        source_order: Order,
        user_id: int,
    ) -> Order:
        from app.services.order_service import OrderService

        if target_order.id == source_order.id:
            raise ValueError("Target and source orders must be different.")

        invalid_statuses = {"PAID", "CLOSED", "CANCELLED", "REJECTED", "MERGED"}
        if target_order.status in invalid_statuses:
            raise ValueError("Target order cannot be merged into in its current status.")

        if source_order.status in invalid_statuses:
            raise ValueError("Source order cannot be merged in its current status.")

        payments_result = await db.execute(
            select(Payment).where(Payment.order_id == source_order.id).limit(1)
        )
        if payments_result.scalar_one_or_none() is not None:
            raise ValueError("Cannot merge order that already has payments.")

        invoice_result = await db.execute(
            select(Invoice).where(Invoice.order_id == source_order.id).limit(1)
        )
        if invoice_result.scalar_one_or_none() is not None:
            raise ValueError("Cannot merge order that already has an invoice.")

        segments_result = await db.execute(
            select(BillSegment).where(BillSegment.order_id == source_order.id).limit(1)
        )
        if segments_result.scalar_one_or_none() is not None:
            raise ValueError("Cannot merge order that has bill split segments.")

        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == source_order.id)
        )
        items = list(items_result.scalars().all())

        for item in items:
            item.order_id = target_order.id
            db.add(item)

        source_table_id = source_order.table_id
        source_order.status = "MERGED"
        if source_order.source == "QR":
            source_order.qr_parent_order_id = target_order.id
        source_order.total_amount = Decimal("0.00")
        source_order.subtotal_amount = Decimal("0.00")
        source_order.discount_amount = Decimal("0.00")
        source_order.tip_amount = Decimal("0.00")

        db.add(source_order)
        await db.flush()

        db.add(
            OrderActionLog(
                order_id=source_order.id,
                user_id=user_id,
                action_type="ORDER_MERGED_OUT",
                description=f"Merged into order #{target_order.id}.",
            )
        )

        db.add(
            OrderActionLog(
                order_id=target_order.id,
                user_id=user_id,
                action_type="ORDER_MERGED_IN",
                description=f"Merged items from order #{source_order.id}.",
            )
        )

        await db.flush()

        order_service = OrderService()
        await order_service._release_table_if_no_active_orders(
            db,
            order=source_order,
            table_id=source_table_id,
        )
        merged_order = await order_service.recalculate_total(db, order=target_order)

        await websocket_manager.broadcast_many(
            channels=["waiters", "floor"],
            event="orders_merged",
            data={
                "target_order_id": target_order.id,
                "source_order_id": source_order.id,
                "target_table_id": target_order.table_id,
                "source_table_id": source_table_id,
            },
        )
        return merged_order

    async def split_item_quantity(
        self,
        db: AsyncSession,
        *,
        source_item: OrderItem,
        target_order: Order,
        quantity: int,
    ) -> OrderItem:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if quantity >= source_item.quantity:
            raise ValueError("Quantity must be smaller than source item quantity.")

        unit_total = source_item.total_price / source_item.quantity
        source_order = await self._get_order(db, order_id=source_item.order_id)

        source_item.quantity -= quantity
        source_item.total_price = unit_total * source_item.quantity

        target_item = OrderItem(
            order_id=target_order.id,
            product_id=source_item.product_id,
            quantity=quantity,
            unit_price=source_item.unit_price,
            total_price=unit_total * quantity,
            status=source_item.status,
            notes=source_item.notes,
        )

        db.add(source_item)
        db.add(target_item)
        await db.flush()

        await self._copy_modifiers(
            db,
            source_order_item_id=source_item.id,
            target_order_item_id=target_item.id,
        )
        await db.flush()
        await self._recalculate_orders(db, source_order, target_order)
        return target_item

    async def _recalculate_orders(
        self,
        db: AsyncSession,
        *orders: Order,
    ) -> None:
        for order in orders:
            result = await db.execute(
                select(OrderItem).where(OrderItem.order_id == order.id),
            )
            items = result.scalars().all()
            order.total_amount = sum(
                (item.total_price for item in items),
                Decimal("0.00"),
            )
            order.estimated_time = await self._calculate_estimated_time(
                db,
                order_items=list(items),
            )
            db.add(order)

        await db.commit()
        for order in orders:
            await db.refresh(order)

    async def _get_order_items(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        order_item_ids: list[int],
    ) -> list[OrderItem]:
        result = await db.execute(
            select(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.id.in_(order_item_ids),
            ),
        )
        items = list(result.scalars().all())

        if len(items) != len(set(order_item_ids)):
            raise ValueError("Some order items do not belong to source order.")

        return items

    async def _calculate_estimated_time(
        self,
        db: AsyncSession,
        *,
        order_items,
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
        estimates = list(result.scalars().all())
        return max(estimates) if estimates else None

    async def _copy_modifiers(
        self,
        db: AsyncSession,
        *,
        source_order_item_id: int,
        target_order_item_id: int,
    ) -> None:
        result = await db.execute(
            select(OrderItemModifier).where(
                OrderItemModifier.order_item_id == source_order_item_id,
            ),
        )
        modifiers = result.scalars().all()

        for modifier in modifiers:
            db.add(
                OrderItemModifier(
                    order_item_id=target_order_item_id,
                    product_modifier_id=modifier.product_modifier_id,
                    price=modifier.price,
                ),
            )

    async def _get_order(self, db: AsyncSession, *, order_id: int) -> Order:
        result = await db.execute(
            select(Order).where(Order.id == order_id),
        )
        order = result.scalar_one_or_none()

        if order is None:
            raise ValueError("Order does not exist.")

        return order


billing_service = BillingService()
