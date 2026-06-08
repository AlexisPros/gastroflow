from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import websocket_manager
from app.models.bill_segment import BillSegment
from app.models.bill_segment_item import BillSegmentItem
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_item_modifier import OrderItemModifier
from app.models.product import Product
from app.schemas.bill_split import (
    BillSegmentItemRead,
    BillSegmentRead,
    BillSplitMoveItemInput,
    BillSplitOriginalItemRead,
    BillSplitViewRead,
)
from app.services.discount_service import discount_service

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.001")


class BillSplitService:
    async def get_view(self, db: AsyncSession, *, order: Order) -> BillSplitViewRead:
        self._ensure_order_can_split(order)
        segments = await self._get_segments(db, order_id=order.id)
        if len(segments) < 2:
            for _ in range(2 - len(segments)):
                await self.create_segment(db, order=order)
            segments = await self._get_segments(db, order_id=order.id)

        original_items = await self._build_original_items(db, order=order)
        segment_reads = await self._build_segment_reads(db, order_id=order.id)
        unassigned_total = sum(
            (
                self._line_total(item.unit_price, item.remaining_quantity)
                for item in original_items
            ),
            Decimal("0.00"),
        )

        return BillSplitViewRead(
            order_id=order.id,
            original_items=original_items,
            segments=segment_reads,
            unassigned_total=self._money(unassigned_total),
        )

    async def create_segment(self, db: AsyncSession, *, order: Order) -> BillSegment:
        self._ensure_order_can_split(order)
        position = await self._get_next_segment_position(db, order_id=order.id)
        segment = BillSegment(
            order_id=order.id,
            name=f"Check {position + 1}",
            position=position,
            status="OPEN",
        )
        db.add(segment)
        await db.commit()
        await db.refresh(segment)
        return segment

    async def delete_segment(
        self,
        db: AsyncSession,
        *,
        order: Order,
        segment_id: int,
    ) -> None:
        self._ensure_order_can_split(order)
        segment = await self._get_segment(db, order_id=order.id, segment_id=segment_id)
        if segment is None:
            raise ValueError("Bill segment does not exist.")

        item_count_result = await db.execute(
            select(func.count(BillSegmentItem.id)).where(
                BillSegmentItem.bill_segment_id == segment.id,
            ),
        )
        if item_count_result.scalar_one() > 0:
            raise ValueError("Only empty bill segments can be deleted.")

        await db.delete(segment)
        await db.commit()

    async def move_items(
        self,
        db: AsyncSession,
        *,
        order: Order,
        target_segment_id: int,
        items: list[BillSplitMoveItemInput],
    ) -> BillSplitViewRead:
        self._ensure_order_can_split(order)
        if not items:
            raise ValueError("At least one item is required.")

        target_segment = await self._get_segment(
            db,
            order_id=order.id,
            segment_id=target_segment_id,
        )
        if target_segment is None:
            raise ValueError("Target bill segment does not belong to this order.")

        for item_input in items:
            order_item = await self._get_order_item(
                db,
                order_id=order.id,
                order_item_id=item_input.order_item_id,
            )
            available_quantity = await self._get_remaining_quantity(
                db,
                order_item=order_item,
            )
            move_quantity = self._quantity(item_input.quantity or available_quantity)
            self._validate_move_quantity(
                move_quantity=move_quantity,
                available_quantity=available_quantity,
            )
            await self._add_or_update_segment_item(
                db,
                segment=target_segment,
                order_item=order_item,
                quantity=move_quantity,
            )

        await db.commit()
        return await self.get_view(db, order=order)

    async def split_item(
        self,
        db: AsyncSession,
        *,
        order: Order,
        order_item_id: int,
        target_segment_ids: list[int],
    ) -> BillSplitViewRead:
        self._ensure_order_can_split(order)
        if len(set(target_segment_ids)) < 2:
            raise ValueError("Select at least two bill segments.")

        segments = [
            await self._get_segment(db, order_id=order.id, segment_id=segment_id)
            for segment_id in target_segment_ids
        ]
        if any(segment is None for segment in segments):
            raise ValueError("All bill segments must belong to this order.")

        order_item = await self._get_order_item(
            db,
            order_id=order.id,
            order_item_id=order_item_id,
        )
        await db.execute(
            delete(BillSegmentItem).where(
                BillSegmentItem.original_order_item_id == order_item.id,
            ),
        )

        segment_count = Decimal(len(segments))
        share_quantity = self._quantity(Decimal(order_item.quantity) / segment_count)
        unit_total = self._unit_total(order_item)
        allocated_total = Decimal("0.00")
        allocated_quantity = Decimal("0.000")

        for index, segment in enumerate(segments):
            if segment is None:
                continue
            if index == len(segments) - 1:
                total_price = self._money(order_item.total_price - allocated_total)
                quantity = self._quantity(
                    Decimal(order_item.quantity) - allocated_quantity,
                )
            else:
                total_price = self._money(unit_total * share_quantity)
                allocated_total += total_price
                quantity = share_quantity
                allocated_quantity += quantity

            db.add(
                BillSegmentItem(
                    bill_segment_id=segment.id,
                    original_order_item_id=order_item.id,
                    product_id=order_item.product_id,
                    quantity=quantity,
                    unit_price=unit_total,
                    total_price=total_price,
                    notes=order_item.notes,
                ),
            )

        await db.commit()
        return await self.get_view(db, order=order)

    async def finalize(
        self,
        db: AsyncSession,
        *,
        order: Order,
        segment_guest_counts: dict[int, int],
    ) -> list[Order]:
        self._ensure_order_can_split(order)
        segments = await self._get_segments(db, order_id=order.id)
        segment_items_by_segment = await self._get_segment_items_by_segment(
            db,
            order_id=order.id,
        )
        non_empty_segments = [
            segment
            for segment in segments
            if segment_items_by_segment.get(segment.id)
        ]
        if not non_empty_segments:
            raise ValueError("At least one non-empty bill segment is required.")

        original_items = await self._build_original_items(db, order=order)
        unassigned_quantity = sum(
            (item.remaining_quantity for item in original_items),
            Decimal("0.000"),
        )
        if unassigned_quantity > Decimal("0.000"):
            raise ValueError("All items must be assigned to checks before finalizing.")

        for segment in non_empty_segments:
            guest_count = segment_guest_counts.get(segment.id)
            if guest_count is None or guest_count <= 0:
                raise ValueError("Guest count is required for every split check.")

        next_sequence = await self._get_next_split_sequence(db, order=order)
        created_orders: list[Order] = []

        segment_orders: dict[int, Order] = {}
        for index, segment in enumerate(non_empty_segments):
            split_order = Order(
                table_id=order.table_id,
                waiter_id=order.waiter_id,
                shift_id=order.shift_id,
                guest_count=segment_guest_counts[segment.id],
                source=order.source,
                status=order.status,
                split_parent_order_id=order.id,
                split_sequence=next_sequence + index,
                total_amount=Decimal("0.00"),
                subtotal_amount=Decimal("0.00"),
                discount_amount=Decimal("0.00"),
                tip_amount=Decimal("0.00"),
            )
            db.add(split_order)
            await db.flush()

            created_orders.append(split_order)
            segment_orders[segment.id] = split_order

        allocations_by_item: dict[int, list[tuple[Order, BillSegmentItem]]] = {}
        for segment in non_empty_segments:
            split_order = segment_orders[segment.id]
            for segment_item in segment_items_by_segment.get(segment.id, []):
                allocations_by_item.setdefault(
                    segment_item.original_order_item_id,
                    [],
                ).append((split_order, segment_item))

        for order_item_id, allocations in allocations_by_item.items():
            source_item = await self._get_order_item(
                db,
                order_id=order.id,
                order_item_id=order_item_id,
            )
            await self._apply_item_allocations(
                db,
                source_item=source_item,
                allocations=allocations,
            )

        order.status = "CANCELLED"
        order.table_id = None

        orders_to_recalculate = [order, *created_orders]
        for order_to_recalculate in orders_to_recalculate:
            await self._recalculate_order_without_commit(
                db,
                order=order_to_recalculate,
                keep_discount=order_to_recalculate.id == order.id,
            )

        await db.execute(
            delete(BillSegmentItem).where(
                BillSegmentItem.bill_segment_id.in_(
                    [segment.id for segment in segments],
                ),
            ),
        )
        await db.execute(
            delete(BillSegment).where(BillSegment.order_id == order.id),
        )

        await db.commit()
        for order_to_refresh in orders_to_recalculate:
            await db.refresh(order_to_refresh)

        await websocket_manager.broadcast_many(
            channels=["waiters", "managers"],
            event="bill_split_finalized",
            data={
                "order_id": order.id,
                "split_order_ids": [split_order.id for split_order in created_orders],
            },
        )
        return created_orders

    async def _build_original_items(
        self,
        db: AsyncSession,
        *,
        order: Order,
    ) -> list[BillSplitOriginalItemRead]:
        assigned_by_item = await self._get_assigned_quantities(db, order_id=order.id)
        result = await db.execute(
            select(OrderItem, Product)
            .join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.position.asc(), OrderItem.id.asc()),
        )

        items: list[BillSplitOriginalItemRead] = []
        for order_item, product in result.all():
            quantity = self._quantity(Decimal(order_item.quantity))
            assigned_quantity = self._quantity(
                assigned_by_item.get(order_item.id, Decimal("0.000")),
            )
            remaining_quantity = self._quantity(quantity - assigned_quantity)
            items.append(
                BillSplitOriginalItemRead(
                    id=order_item.id,
                    product_id=order_item.product_id,
                    product_name=product.name,
                    quantity=quantity,
                    assigned_quantity=assigned_quantity,
                    remaining_quantity=remaining_quantity,
                    unit_price=self._unit_total(order_item),
                    total_price=order_item.total_price,
                    notes=order_item.notes,
                ),
            )

        return items

    async def _build_segment_reads(
        self,
        db: AsyncSession,
        *,
        order_id: int,
    ) -> list[BillSegmentRead]:
        segments = await self._get_segments(db, order_id=order_id)
        result = await db.execute(
            select(BillSegmentItem, Product)
            .join(Product, BillSegmentItem.product_id == Product.id)
            .join(BillSegment, BillSegmentItem.bill_segment_id == BillSegment.id)
            .where(BillSegment.order_id == order_id)
            .order_by(BillSegment.position.asc(), BillSegmentItem.id.asc()),
        )
        items_by_segment: dict[int, list[BillSegmentItemRead]] = {}
        for segment_item, product in result.all():
            items_by_segment.setdefault(segment_item.bill_segment_id, []).append(
                BillSegmentItemRead(
                    id=segment_item.id,
                    bill_segment_id=segment_item.bill_segment_id,
                    original_order_item_id=segment_item.original_order_item_id,
                    product_id=segment_item.product_id,
                    product_name=product.name,
                    quantity=segment_item.quantity,
                    unit_price=segment_item.unit_price,
                    total_price=segment_item.total_price,
                    notes=segment_item.notes,
                    modifier_snapshot=segment_item.modifier_snapshot,
                ),
            )

        return [
            BillSegmentRead(
                id=segment.id,
                order_id=segment.order_id,
                name=segment.name,
                position=segment.position,
                status=segment.status,
                total_amount=self._money(
                    sum(
                        (
                            item.total_price
                            for item in items_by_segment.get(segment.id, [])
                        ),
                        Decimal("0.00"),
                    ),
                ),
                created_at=segment.created_at,
                items=items_by_segment.get(segment.id, []),
            )
            for segment in segments
        ]

    async def _get_segments(self, db: AsyncSession, *, order_id: int) -> list[BillSegment]:
        result = await db.execute(
            select(BillSegment)
            .where(BillSegment.order_id == order_id)
            .order_by(BillSegment.position.asc(), BillSegment.id.asc()),
        )
        return list(result.scalars().all())

    async def _get_segment(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        segment_id: int,
    ) -> BillSegment | None:
        result = await db.execute(
            select(BillSegment).where(
                BillSegment.id == segment_id,
                BillSegment.order_id == order_id,
            ),
        )
        return result.scalar_one_or_none()

    async def _get_segment_items_by_segment(
        self,
        db: AsyncSession,
        *,
        order_id: int,
    ) -> dict[int, list[BillSegmentItem]]:
        result = await db.execute(
            select(BillSegmentItem)
            .join(BillSegment, BillSegmentItem.bill_segment_id == BillSegment.id)
            .where(BillSegment.order_id == order_id)
            .order_by(BillSegment.position.asc(), BillSegmentItem.id.asc()),
        )
        items_by_segment: dict[int, list[BillSegmentItem]] = {}
        for item in result.scalars().all():
            items_by_segment.setdefault(item.bill_segment_id, []).append(item)
        return items_by_segment

    async def _get_order_item(
        self,
        db: AsyncSession,
        *,
        order_id: int,
        order_item_id: int,
    ) -> OrderItem:
        result = await db.execute(
            select(OrderItem).where(
                OrderItem.id == order_item_id,
                OrderItem.order_id == order_id,
            ),
        )
        order_item = result.scalar_one_or_none()
        if order_item is None:
            raise ValueError("Order item does not belong to this order.")
        return order_item

    async def _get_next_segment_position(self, db: AsyncSession, *, order_id: int) -> int:
        result = await db.execute(
            select(func.max(BillSegment.position)).where(BillSegment.order_id == order_id),
        )
        max_position = result.scalar_one_or_none()
        return 0 if max_position is None else max_position + 1

    async def _get_assigned_quantities(
        self,
        db: AsyncSession,
        *,
        order_id: int,
    ) -> dict[int, Decimal]:
        result = await db.execute(
            select(
                BillSegmentItem.original_order_item_id,
                func.coalesce(func.sum(BillSegmentItem.quantity), 0),
            )
            .join(BillSegment, BillSegmentItem.bill_segment_id == BillSegment.id)
            .where(BillSegment.order_id == order_id)
            .group_by(BillSegmentItem.original_order_item_id),
        )
        return {
            int(order_item_id): self._quantity(Decimal(quantity))
            for order_item_id, quantity in result.all()
        }

    async def _get_remaining_quantity(
        self,
        db: AsyncSession,
        *,
        order_item: OrderItem,
    ) -> Decimal:
        assigned_result = await db.execute(
            select(func.coalesce(func.sum(BillSegmentItem.quantity), 0)).where(
                BillSegmentItem.original_order_item_id == order_item.id,
            ),
        )
        assigned = self._quantity(Decimal(assigned_result.scalar_one()))
        return self._quantity(Decimal(order_item.quantity) - assigned)

    async def _add_or_update_segment_item(
        self,
        db: AsyncSession,
        *,
        segment: BillSegment,
        order_item: OrderItem,
        quantity: Decimal,
    ) -> None:
        result = await db.execute(
            select(BillSegmentItem).where(
                BillSegmentItem.bill_segment_id == segment.id,
                BillSegmentItem.original_order_item_id == order_item.id,
            ),
        )
        segment_item = result.scalar_one_or_none()
        unit_total = self._unit_total(order_item)
        if segment_item is None:
            db.add(
                BillSegmentItem(
                    bill_segment_id=segment.id,
                    original_order_item_id=order_item.id,
                    product_id=order_item.product_id,
                    quantity=quantity,
                    unit_price=unit_total,
                    total_price=self._line_total(unit_total, quantity),
                    notes=order_item.notes,
                ),
            )
            return

        segment_item.quantity = self._quantity(segment_item.quantity + quantity)
        segment_item.total_price = self._line_total(unit_total, segment_item.quantity)
        db.add(segment_item)

    async def _apply_item_allocations(
        self,
        db: AsyncSession,
        *,
        source_item: OrderItem,
        allocations: list[tuple[Order, BillSegmentItem]],
    ) -> None:
        source_quantity = self._quantity(Decimal(source_item.quantity))
        allocated_quantity = self._quantity(
            sum(
                (segment_item.quantity for _, segment_item in allocations),
                Decimal("0.000"),
            ),
        )
        if allocated_quantity <= Decimal("0.000"):
            raise ValueError("Split item quantity must be greater than zero.")
        if allocated_quantity > source_quantity:
            raise ValueError("Split item quantity exceeds source item quantity.")

        has_fractional_share = any(
            segment_item.quantity != segment_item.quantity.to_integral_value()
            for _, segment_item in allocations
        )
        if has_fractional_share and allocated_quantity != source_quantity:
            raise ValueError("Fractional split shares must assign the full source item.")

        if allocated_quantity == source_quantity:
            target_order, segment_item = allocations[0]
            source_item.order_id = target_order.id
            self._apply_segment_price_to_order_item(
                order_item=source_item,
                segment_item=segment_item,
                is_fractional_share=(
                    segment_item.quantity != segment_item.quantity.to_integral_value()
                ),
            )
            db.add(source_item)
            await db.flush()

            for target_order, segment_item in allocations[1:]:
                await self._create_copied_order_item(
                    db,
                    source_item=source_item,
                    target_order=target_order,
                    segment_item=segment_item,
                )
            return

        remaining_quantity = source_quantity - allocated_quantity
        if remaining_quantity <= Decimal("0.000"):
            raise ValueError("Source item quantity cannot become empty.")
        if remaining_quantity != remaining_quantity.to_integral_value():
            raise ValueError("Source item remaining quantity must be a whole number.")

        unit_total = source_item.total_price / Decimal(source_item.quantity)
        source_item.quantity = int(remaining_quantity)
        source_item.total_price = self._line_total(unit_total, remaining_quantity)
        db.add(source_item)
        await db.flush()

        for target_order, segment_item in allocations:
            await self._create_copied_order_item(
                db,
                source_item=source_item,
                target_order=target_order,
                segment_item=segment_item,
            )

    async def _create_copied_order_item(
        self,
        db: AsyncSession,
        *,
        source_item: OrderItem,
        target_order: Order,
        segment_item: BillSegmentItem,
    ) -> None:
        is_fractional_share = (
            segment_item.quantity != segment_item.quantity.to_integral_value()
        )
        copied_item = OrderItem(
            order_id=target_order.id,
            product_id=source_item.product_id,
            quantity=1 if is_fractional_share else int(segment_item.quantity),
            position=source_item.position,
            course_number=source_item.course_number,
            unit_price=(
                segment_item.total_price
                if is_fractional_share
                else self._money(segment_item.total_price / segment_item.quantity)
            ),
            total_price=segment_item.total_price,
            status=source_item.status,
            notes=source_item.notes,
        )
        if is_fractional_share:
            share_label = self._format_share(segment_item.quantity)
            copied_item.notes = (
                f"{copied_item.notes}; split share {share_label}"
                if copied_item.notes
                else f"split share {share_label}"
            )

        db.add(copied_item)
        await db.flush()
        await self._copy_modifiers(
            db,
            source_order_item_id=source_item.id,
            target_order_item_id=copied_item.id,
        )

    def _apply_segment_price_to_order_item(
        self,
        *,
        order_item: OrderItem,
        segment_item: BillSegmentItem,
        is_fractional_share: bool,
    ) -> None:
        if is_fractional_share:
            order_item.quantity = 1
            order_item.unit_price = segment_item.total_price
            order_item.total_price = segment_item.total_price
            share_label = self._format_share(segment_item.quantity)
            order_item.notes = (
                f"{order_item.notes}; split share {share_label}"
                if order_item.notes
                else f"split share {share_label}"
            )
            return

        quantity = int(segment_item.quantity)
        order_item.quantity = quantity
        order_item.total_price = segment_item.total_price
        order_item.unit_price = self._money(
            segment_item.total_price / Decimal(quantity),
        )

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
        for modifier in result.scalars().all():
            db.add(
                OrderItemModifier(
                    order_item_id=target_order_item_id,
                    product_modifier_id=modifier.product_modifier_id,
                    price=modifier.price,
                ),
            )

    async def _recalculate_order_without_commit(
        self,
        db: AsyncSession,
        *,
        order: Order,
        keep_discount: bool,
    ) -> None:
        result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id),
        )
        order_items = list(result.scalars().all())
        subtotal_amount = sum(
            (item.total_price for item in order_items),
            Decimal("0.00"),
        )
        order.subtotal_amount = self._money(subtotal_amount)
        if keep_discount and order.discount_id is not None:
            discount = await discount_service._get_active_discount(
                db,
                discount_id=order.discount_id,
            )
            order.discount_amount = discount_service.calculate_discount_amount(
                discount=discount,
                base_total=order.subtotal_amount,
            )
        else:
            order.discount_id = None
            order.discount_amount = Decimal("0.00")
        order.tip_amount = Decimal("0.00")
        order.total_amount = max(
            order.subtotal_amount - order.discount_amount,
            Decimal("0.00"),
        )
        db.add(order)

    async def _get_next_split_sequence(self, db: AsyncSession, *, order: Order) -> int:
        result = await db.execute(
            select(func.max(Order.split_sequence)).where(
                Order.split_parent_order_id == order.id,
            ),
        )
        max_sequence = result.scalar_one_or_none()
        return 1 if max_sequence is None else max_sequence + 1

    def _ensure_order_can_split(self, order: Order) -> None:
        if order.status not in {"OPEN", "IN_PROGRESS"}:
            raise ValueError("Bill splitting is only allowed for active orders.")

    def _validate_move_quantity(
        self,
        *,
        move_quantity: Decimal,
        available_quantity: Decimal,
    ) -> None:
        if move_quantity <= Decimal("0.000"):
            raise ValueError("Quantity must be at least 1.")
        if move_quantity > available_quantity:
            raise ValueError("Quantity cannot exceed available quantity.")

    def _unit_total(self, order_item: OrderItem) -> Decimal:
        return self._money(order_item.total_price / Decimal(order_item.quantity))

    def _line_total(self, unit_price: Decimal, quantity: Decimal) -> Decimal:
        return self._money(unit_price * quantity)

    def _money(self, amount: Decimal) -> Decimal:
        return Decimal(amount).quantize(MONEY, rounding=ROUND_HALF_UP)

    def _quantity(self, quantity: Decimal) -> Decimal:
        return Decimal(quantity).quantize(QUANTITY, rounding=ROUND_HALF_UP)

    def _format_share(self, quantity: Decimal) -> str:
        normalized = quantity.normalize()
        return format(normalized, "f")


bill_split_service = BillSplitService()
