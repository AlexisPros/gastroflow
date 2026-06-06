from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.crud import order_action_log, order_transfer_log, product_kitchen_step
from app.crud import employee_shift as crud_employee_shift
from app.models.kitchen_task import KitchenTask
from app.models.employee_shift import EmployeeShift
from app.models.modifier import Modifier
from app.models.order import Order
from app.models.order_action_log import OrderActionLog
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.order_transfer_log import OrderTransferLog
from app.models.product import Product
from app.models.product_modifier import ProductModifier
from app.models.restaurant_table import RestaurantTable
from app.models.user import User
from app.core.security import verify_pin
from app.services.discount_service import discount_service


@dataclass(slots=True)
class OrderItemRequest:
    product_id: int
    quantity: int = 1
    position: int = 0
    course_number: int = 1
    notes: str | None = None
    product_modifier_ids: list[int] = field(default_factory=list)


class OrderService:
    async def create_order_with_items(
        self,
        db: AsyncSession,
        *,
        table_id: int | None = None,
        waiter_id: int | None = None,
        guest_count: int | None = None,
        source: str = "WAITER",
        items: list[OrderItemRequest],
    ) -> Order:
        if not items:
            raise ValueError("Order must contain at least one item.")

        if guest_count is not None and guest_count <= 0:
            raise ValueError("Guest count must be greater than zero.")

        shift_id: int | None = None
        if waiter_id is not None:
            shift = await crud_employee_shift.get_open_by_user(
                db,
                user_id=waiter_id,
            )
            if shift is None:
                raise ValueError("Start shift first.")
            shift_id = shift.id

        order = Order(
            table_id=table_id,
            waiter_id=waiter_id,
            guest_count=guest_count,
            shift_id=shift_id,
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
        order.subtotal_amount = total_amount
        order.discount_amount = Decimal("0.00")
        order.estimated_time = max(item_estimates) if item_estimates else None

        await self._set_order_table_status(
            db,
            order=order,
            status="OCCUPIED",
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["waiters", "floor"],
            event="order_created",
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "waiter_id": order.waiter_id,
                "source": order.source,
                "status": order.status,
                "table_status": "OCCUPIED",
            },
        )
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

        table = await self._ensure_table_accepts_qr_order(db, table_id=table_id)

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
        order.subtotal_amount = total_amount
        order.discount_amount = Decimal("0.00")
        table.status = "PENDING_ORDER"

        db.add(table)
        db.add(order)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["waiters", "floor"],
            event="qr_order_created",
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "guest_count": order.guest_count,
                "status": order.status,
                "table_status": table.status,
            },
        )
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

        await self._set_order_table_status(
            db,
            order=order,
            status="FREE",
        )
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
        await websocket_manager.broadcast_many(
            channels=["waiters", "floor"],
            event="qr_order_rejected",
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "waiter_id": order.waiter_id,
                "status": order.status,
                "table_status": "FREE",
            },
        )
        return order

    async def recalculate_total(self, db: AsyncSession, *, order: Order) -> Order:
        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id),
        )
        order_items = result.scalars().all()

        subtotal_amount = sum(
            (item.total_price for item in order_items),
            Decimal("0.00"),
        )
        order.subtotal_amount = subtotal_amount
        order.total_amount = (
            max(
                subtotal_amount - order.discount_amount,
                Decimal("0.00"),
            )
            + order.tip_amount
        )
        order.estimated_time = await self._calculate_order_estimated_time(
            db,
            order_items=list(order_items),
        )

        db.add(order)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["waiters", "kitchen", "bar", "floor"],
            event="qr_order_confirmed",
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "waiter_id": order.waiter_id,
                "shift_id": order.shift_id,
                "status": order.status,
                "estimated_time": order.estimated_time,
                "table_status": "OCCUPIED",
            },
        )
        return order

    async def add_items_to_order(
        self,
        db: AsyncSession,
        *,
        order: Order,
        items: list[OrderItemRequest],
    ) -> Order:
        if order.status != "OPEN":
            raise ValueError("Only open orders can receive new items.")

        if not items:
            raise ValueError("Order must contain at least one item.")

        existing_items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id),
        )
        existing_items = list(existing_items_result.scalars().all())
        next_position = (
            max((item.position for item in existing_items), default=-1) + 1
        )

        item_estimates: list[int] = []
        for index, item_request in enumerate(items):
            item_request.position = next_position + index
            order_item, item_total = await self._create_order_item(
                db,
                order_id=order.id,
                item_request=item_request,
            )
            order.subtotal_amount += item_total
            order.total_amount += item_total
            item_estimated_time = await self._create_kitchen_task_for_item(
                db,
                order_item=order_item,
            )
            if item_estimated_time is not None:
                item_estimates.append(item_estimated_time)

        if item_estimates:
            order.estimated_time = max(
                [order.estimated_time or 0, *item_estimates],
            )

        db.add(order)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["waiters", "kitchen", "bar"],
            event="order_items_added",
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "status": order.status,
            },
        )
        return order

    async def cancel_order_with_manager_pin(
        self,
        db: AsyncSession,
        *,
        order: Order,
        manager_pin: str,
    ) -> Order:
        await self._authorize_manager_pin(db, manager_pin=manager_pin)

        if order.status not in {"OPEN", "PENDING_CONFIRMATION"}:
            raise ValueError("Only active orders can be cancelled.")

        order.status = "CANCELLED"
        await self._release_table_if_no_active_orders(db, order=order)
        db.add(order)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["waiters", "floor", "managers"],
            event="order_cancelled",
            data={
                "order_id": order.id,
                "table_id": order.table_id,
                "status": order.status,
                "table_status": "FREE",
            },
        )
        return order

    async def verify_manager_pin(
        self,
        db: AsyncSession,
        *,
        manager_pin: str,
    ) -> User:
        return await self._authorize_manager_pin(db, manager_pin=manager_pin)

    async def void_order_item(
        self,
        db: AsyncSession,
        *,
        order: Order,
        order_item_id: int,
        current_user: User,
        manager_pin: str | None = None,
    ) -> Order:
        if order.status != "OPEN":
            raise ValueError("Only open orders can be changed.")

        authorized_user = current_user
        if current_user.role not in {"ADMIN", "MANAGER"}:
            if not manager_pin:
                raise ValueError("Manager PIN is required.")
            authorized_user = await self._authorize_manager_pin(
                db,
                manager_pin=manager_pin,
            )

        result = await db.execute(
            select(OrderItem).where(
                OrderItem.id == order_item_id,
                OrderItem.order_id == order.id,
            ),
        )
        order_item = result.scalar_one_or_none()
        if order_item is None:
            raise ValueError("Order item does not exist in this order.")

        remaining_result = await db.execute(
            select(OrderItem).where(
                OrderItem.order_id == order.id,
                OrderItem.id != order_item.id,
            ),
        )
        base_total = sum(
            (item.total_price for item in remaining_result.scalars().all()),
            Decimal("0.00"),
        )
        discount_amount = Decimal("0.00")
        if order.discount_id is not None:
            discount = await discount_service._get_active_discount(
                db,
                discount_id=order.discount_id,
            )
            discount_amount = discount_service.calculate_discount_amount(
                discount=discount,
                base_total=base_total,
            )

        order.subtotal_amount = base_total
        order.discount_amount = discount_amount
        order.total_amount = (
            max(base_total - discount_amount, Decimal("0.00"))
            + order.tip_amount
        )

        db.add(
            OrderActionLog(
                order_id=order.id,
                user_id=authorized_user.id,
                action_type="ORDER_ITEM_VOIDED",
                description=f"Voided order item #{order_item.id}.",
            ),
        )
        await db.delete(order_item)
        db.add(order)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["waiters", "kitchen", "bar", "managers"],
            event="order_item_voided",
            data={
                "order_id": order.id,
                "order_item_id": order_item_id,
                "status": order.status,
                "total_amount": str(order.total_amount),
            },
        )
        return order

    async def _authorize_manager_pin(
        self,
        db: AsyncSession,
        *,
        manager_pin: str,
    ) -> User:
        result = await db.execute(
            select(User).where(
                User.role.in_(["ADMIN", "MANAGER"]),
                User.is_active.is_(True),
            ),
        )
        for user in result.scalars().all():
            if user.pin_hash and verify_pin(manager_pin, user.pin_hash):
                return user

        raise ValueError("Manager PIN is invalid.")

    async def _release_table_if_no_active_orders(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> None:
        if order.table_id is None:
            return

        active_order_result = await db.execute(
            select(Order)
            .where(
                Order.table_id == order.table_id,
                Order.id != order.id,
                Order.status.in_(["PENDING_CONFIRMATION", "OPEN"]),
            )
            .limit(1),
        )
        if active_order_result.scalar_one_or_none() is not None:
            return

        result = await db.execute(
            select(RestaurantTable).where(RestaurantTable.id == order.table_id),
        )
        table = result.scalar_one_or_none()
        if table is None:
            return

        table.status = "FREE"
        table.current_guests = None
        db.add(table)

    async def _ensure_table_accepts_qr_order(
        self,
        db: AsyncSession,
        *,
        table_id: int,
    ) -> RestaurantTable:
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

        return table

    async def _set_order_table_status(
        self,
        db: AsyncSession,
        *,
        order: Order,
        status: str,
    ) -> None:
        if order.table_id is None:
            return

        result = await db.execute(
            select(RestaurantTable).where(RestaurantTable.id == order.table_id),
        )
        table = result.scalar_one_or_none()
        if table is None:
            raise ValueError("Restaurant table does not exist.")

        table.status = status
        db.add(table)

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
        shift = await crud_employee_shift.get_open_by_user(db, user_id=waiter_id)
        if shift is None:
            raise ValueError("Start shift first.")

        order.shift_id = shift.id
        order.status = "OPEN"
        order.estimated_time = max(item_estimates) if item_estimates else None

        await self._set_order_table_status(
            db,
            order=order,
            status="OCCUPIED",
        )
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
    ) -> OrderTransferLog:
        if order.waiter_id == to_waiter_id:
            raise ValueError("Order already belongs to this waiter.")

        if order.status in {"CLOSED", "PAID", "CANCELLED", "REJECTED", "MERGED"}:
            raise ValueError("Only active orders can be transferred.")

        shift = await crud_employee_shift.get_open_by_user(db, user_id=to_waiter_id)
        if shift is None:
            raise ValueError("Receiving waiter must have an active shift.")

        transfer_log = await order_transfer_log.transfer_order(
            db,
            order=order,
            to_waiter_id=to_waiter_id,
            shift_id=shift.id,
        )
        await websocket_manager.broadcast_many(
            channels=["waiters", "managers"],
            event="order_transferred",
            data={
                "order_id": order.id,
                "from_waiter_id": transfer_log.from_waiter_id,
                "to_waiter_id": transfer_log.to_waiter_id,
            },
        )
        return transfer_log

    async def list_active_waiters_for_transfer(
        self,
        db: AsyncSession,
        *,
        exclude_waiter_id: int,
    ) -> list[dict]:
        active_statuses = ["OPEN", "IN_PROGRESS", "PENDING_CONFIRMATION"]
        result = await db.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                func.count(func.distinct(Order.id)).label("open_orders_count"),
            )
            .join(EmployeeShift, EmployeeShift.user_id == User.id)
            .outerjoin(
                Order,
                (Order.waiter_id == User.id) & (Order.status.in_(active_statuses)),
            )
            .where(
                User.role.in_(["WAITER", "MANAGER"]),
                User.is_active.is_(True),
                EmployeeShift.status == "OPEN",
                User.id != exclude_waiter_id,
            )
            .group_by(User.id)
            .order_by(User.first_name, User.last_name),
        )
        return [
            {
                "id": row.id,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "open_orders_count": row.open_orders_count,
            }
            for row in result.all()
        ]

    async def list_transferable_orders(
        self,
        db: AsyncSession,
        *,
        waiter_id: int,
    ) -> list[Order]:
        result = await db.execute(
            select(Order)
            .where(
                Order.waiter_id == waiter_id,
                Order.status.in_(["OPEN", "IN_PROGRESS"]),
            )
            .order_by(Order.created_at.asc()),
        )
        return list(result.scalars().all())

    async def transfer_all_orders(
        self,
        db: AsyncSession,
        *,
        from_waiter_id: int,
        to_waiter_id: int,
    ) -> list[OrderTransferLog]:
        orders = await self.list_transferable_orders(db, waiter_id=from_waiter_id)
        if not orders:
            raise ValueError("Selected waiter has no transferable orders.")

        logs: list[OrderTransferLog] = []
        for order in orders:
            logs.append(
                await self.transfer_order(
                    db,
                    order=order,
                    to_waiter_id=to_waiter_id,
                ),
            )
        return logs

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

        if item_request.course_number <= 0:
            raise ValueError("Course number must be greater than zero.")

        product = await self._get_active_product(db, product_id=item_request.product_id)
        modifier_total = Decimal("0.00")

        order_item = OrderItem(
            order_id=order_id,
            product_id=product.id,
            quantity=item_request.quantity,
            position=item_request.position,
            course_number=item_request.course_number,
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
