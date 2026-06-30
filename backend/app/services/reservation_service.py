from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.websocket_manager import websocket_manager
from app.crud import employee_shift as crud_employee_shift
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.reservation import Reservation
from app.models.reservation_item import ReservationItem
from app.models.reservation_payment import ReservationPayment
from app.models.reservation_table import ReservationTable
from app.models.restaurant_table import RestaurantTable
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.order_service import OrderItemRequest, order_service


ACTIVE_STATUSES = {"PENDING", "CONFIRMED"}
MANAGEMENT_ROLES = {"ADMIN", "MANAGER", "WAITER"}


class ReservationService:
    def query(self):
        return select(Reservation).options(
            selectinload(Reservation.table),
            selectinload(Reservation.reservation_tables).selectinload(ReservationTable.table),
            selectinload(Reservation.items).selectinload(ReservationItem.product),
            selectinload(Reservation.payments),
        )

    async def list(self, db: AsyncSession) -> list[Reservation]:
        await self.sync_table_statuses(db, commit=False)
        result = await db.execute(self.query().order_by(Reservation.reservation_time.asc()))
        await db.commit()
        return list(result.scalars().unique().all())

    async def confirm(self, db: AsyncSession, *, reservation: Reservation) -> Reservation:
        reservation.status = "CONFIRMED"
        db.add(reservation)
        await db.commit()
        return reservation

    async def assign_tables(
        self, db: AsyncSession, *, reservation: Reservation, table_ids: list[int]
    ) -> Reservation:
        if not table_ids or len(table_ids) != len(set(table_ids)):
            raise ValueError("Reservation tables must be non-empty and unique.")
        reservation.table_id = table_ids[0]
        await db.execute(
            delete(ReservationTable).where(ReservationTable.reservation_id == reservation.id)
        )
        self._replace_tables(db, reservation=reservation, table_ids=table_ids)
        db.add(reservation)
        await db.commit()
        return reservation

    async def find_table_reservations(
        self, db: AsyncSession, *, table_id: int, reservation_time: datetime
    ) -> list[Reservation]:
        result = await db.execute(
            select(Reservation)
            .outerjoin(ReservationTable, ReservationTable.reservation_id == Reservation.id)
            .where(
                or_(Reservation.table_id == table_id, ReservationTable.table_id == table_id),
                Reservation.reservation_time == reservation_time,
                Reservation.status != "CANCELLED",
            )
        )
        return list(result.scalars().unique().all())

    async def get(self, db: AsyncSession, reservation_id: int) -> Reservation | None:
        result = await db.execute(self.query().where(Reservation.id == reservation_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        data: ReservationCreate,
        user_id: int,
        user_role: str,
    ) -> Reservation:
        self._require_manager_role(user_role)
        if data.reservation_time <= datetime.now(timezone.utc):
            raise ValueError("Reservation time must be in the future.")
        tables = await self._get_tables(db, data.table_ids)
        await self._ensure_tables_available(
            db,
            table_ids=data.table_ids,
            starts_at=data.reservation_time,
            duration_minutes=data.duration_minutes,
        )
        products = await self._get_products(db, [item.product_id for item in data.items])
        total = sum(
            (products[item.product_id].price * item.quantity for item in data.items),
            Decimal("0.00"),
        )
        payment_method = data.payment_method.upper()
        if payment_method not in {"ON_SITE", "CASH", "CARD"}:
            raise ValueError("Unknown reservation payment method.")

        reservation = Reservation(
            table_id=tables[0].id,
            customer_name=data.customer_name.strip(),
            customer_phone=data.customer_phone.strip(),
            customer_email=str(data.customer_email) if data.customer_email else None,
            invoice_nip=data.invoice_nip,
            guest_count=data.guest_count,
            reservation_time=data.reservation_time,
            duration_minutes=data.duration_minutes,
            status="CONFIRMED",
            notes=data.notes,
            total_amount=total,
            prepaid_amount=Decimal("0.00"),
            payment_status="UNPAID",
            created_by_user_id=user_id,
        )
        db.add(reservation)
        await db.flush()
        self._replace_tables(db, reservation=reservation, table_ids=data.table_ids)
        self._replace_items(db, reservation=reservation, items=data.items, products=products)

        if payment_method != "ON_SITE":
            if total <= 0:
                raise ValueError("An empty reservation cannot be prepaid.")
            shift = await crud_employee_shift.get_open_by_user(db, user_id=user_id)
            if shift is None:
                raise ValueError("Start shift before accepting a reservation prepayment.")
            cash_received = None
            change_given = None
            if payment_method == "CASH":
                cash_received = data.cash_received or total
                if cash_received < total:
                    raise ValueError("Cash received cannot be lower than the reservation total.")
                change_given = cash_received - total
            db.add(
                ReservationPayment(
                    reservation_id=reservation.id,
                    user_id=user_id,
                    shift_id=shift.id,
                    method=payment_method,
                    amount=total,
                    cash_received=cash_received,
                    change_given=change_given,
                )
            )
            reservation.prepaid_amount = total
            reservation.payment_status = "PREPAID"

        await self._mark_reserved_if_due(db, reservation=reservation, tables=tables)
        await db.commit()
        created = await self.get(db, reservation.id)
        assert created is not None
        await websocket_manager.broadcast_many(
            channels=["floor", "waiters", "kitchen", "bar"],
            event="reservation_created",
            data={"reservation_id": reservation.id, "table_ids": data.table_ids},
        )
        return created

    async def update(
        self,
        db: AsyncSession,
        *,
        reservation: Reservation,
        data: ReservationUpdate,
        user_role: str,
    ) -> Reservation:
        self._require_manager_role(user_role)
        if reservation.status in {"STARTED", "CANCELLED", "COMPLETED"}:
            raise ValueError("This reservation can no longer be edited.")
        payload = data.model_dump(exclude_unset=True, exclude={"table_ids", "items"})
        table_ids = data.table_ids if "table_ids" in data.model_fields_set else None
        item_inputs = data.items if "items" in data.model_fields_set else None
        starts_at = payload.get("reservation_time", reservation.reservation_time)
        duration = payload.get("duration_minutes", reservation.duration_minutes)
        if starts_at <= datetime.now(timezone.utc):
            raise ValueError("Reservation time must be in the future.")

        current_ids = [link.table_id for link in reservation.reservation_tables] or [reservation.table_id]
        selected_ids = table_ids or current_ids
        await self._get_tables(db, selected_ids)
        await self._ensure_tables_available(
            db,
            table_ids=selected_ids,
            starts_at=starts_at,
            duration_minutes=duration,
            exclude_reservation_id=reservation.id,
        )
        for key, value in payload.items():
            if key == "customer_email" and value is not None:
                value = str(value)
            setattr(reservation, key, value)
        if table_ids is not None:
            await db.execute(delete(ReservationTable).where(ReservationTable.reservation_id == reservation.id))
            reservation.table_id = table_ids[0]
            self._replace_tables(db, reservation=reservation, table_ids=table_ids)
        if item_inputs is not None:
            if reservation.prepaid_amount > 0:
                raise ValueError("Prepaid reservation items cannot be edited.")
            products = await self._get_products(db, [item.product_id for item in item_inputs])
            await db.execute(delete(ReservationItem).where(ReservationItem.reservation_id == reservation.id))
            self._replace_items(db, reservation=reservation, items=item_inputs, products=products)
            reservation.total_amount = sum(
                (products[item.product_id].price * item.quantity for item in item_inputs),
                Decimal("0.00"),
            )
        db.add(reservation)
        await self.sync_table_statuses(db, commit=False)
        await db.commit()
        updated = await self.get(db, reservation.id)
        assert updated is not None
        return updated

    async def cancel(self, db: AsyncSession, *, reservation: Reservation, user_role: str) -> Reservation:
        self._require_manager_role(user_role)
        if reservation.status == "STARTED":
            raise ValueError("Started reservation cannot be cancelled.")
        if reservation.prepaid_amount > 0:
            raise ValueError("Refund the prepayment before cancelling this reservation.")
        reservation.status = "CANCELLED"
        db.add(reservation)
        await self.sync_table_statuses(db, commit=False)
        await db.commit()
        result = await self.get(db, reservation.id)
        assert result is not None
        return result

    async def start(
        self,
        db: AsyncSession,
        *,
        reservation: Reservation,
        user_id: int,
        user_role: str,
    ) -> Order:
        self._require_manager_role(user_role)
        if reservation.status not in ACTIVE_STATUSES:
            raise ValueError("Reservation is not available to start.")
        if reservation.started_order_id is not None:
            raise ValueError("Reservation has already been started.")
        links = reservation.reservation_tables
        table_ids = [link.table_id for link in links] or [reservation.table_id]
        # If the reservation has prepaid amount (prepaid), start with an empty check/order (items = []).
        # If it's unpaid (payment on site), include preordered items in the order so they can be prepared and billed.
        should_include_items = (reservation.prepaid_amount <= 0)

        order = await order_service.create_order_with_items(
            db,
            table_id=table_ids[0],
            waiter_id=user_id,
            guest_count=reservation.guest_count,
            source="RESERVATION",
            idempotency_key=f"reservation:{reservation.id}",
            items=[
                OrderItemRequest(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    position=index,
                    notes=item.notes,
                )
                for index, item in enumerate(reservation.items)
            ] if should_include_items else [],
            allow_empty=True,
            allow_reserved_table=True,
        )
        order.reservation_id = reservation.id
        order.reservation_prepaid_amount = reservation.prepaid_amount
        reservation.started_order_id = order.id
        reservation.started_at = datetime.now(timezone.utc)
        reservation.status = "STARTED"

        if should_include_items and reservation.items:
            order_res = await db.execute(
                select(Order)
                .options(
                    selectinload(Order.items).selectinload(OrderItem.kitchen_tasks)
                )
                .where(Order.id == order.id)
            )
            order = order_res.scalar_one()

            for item in order.items:
                item.status = "PENDING"
                db.add(item)
                for task in item.kitchen_tasks:
                    task.status = "PENDING"
                    db.add(task)
            from app.services.stock_service import stock_service
            await stock_service.consume_order_stock(db, order_id=order.id)

        for index, link in enumerate(links):
            link.table.status = "OCCUPIED"
            link.table.current_guests = reservation.guest_count if index == 0 else 0
            db.add(link.table)
        db.add(order)
        db.add(reservation)
        await db.commit()
        await db.refresh(order)
        await websocket_manager.broadcast_many(
            channels=["floor", "waiters", "kitchen", "bar"],
            event="reservation_started",
            data={"reservation_id": reservation.id, "order_id": order.id, "table_ids": table_ids},
        )
        return order

    async def complete_prepaid(
        self,
        db: AsyncSession,
        *,
        reservation: Reservation,
        user_id: int,
        user_role: str,
    ) -> Order:
        self._require_manager_role(user_role)
        if reservation.status != "STARTED" or reservation.started_order_id is None:
            raise ValueError("Only a started reservation can be completed.")
        if reservation.prepaid_amount <= 0 or reservation.prepaid_amount < reservation.total_amount:
            raise ValueError("Only a fully prepaid reservation can be completed here.")
        from app.services.payment_service import payment_service

        order, _, _ = await payment_service.close_order_with_payments(
            db,
            order_id=reservation.started_order_id,
            user_id=user_id,
            can_manage_all=user_role in {"ADMIN", "MANAGER"},
            payments=[],
        )
        return order

    async def sync_table_statuses(self, db: AsyncSession, *, commit: bool = True) -> None:
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=2)
        result = await db.execute(
            self.query().where(
                Reservation.status.in_(ACTIVE_STATUSES),
                Reservation.reservation_time <= horizon,
            )
        )
        # PostgreSQL cannot multiply an interval through every test dialect, so filter the end in Python.
        active = [
            reservation
            for reservation in result.scalars().unique().all()
            if reservation.reservation_time + timedelta(minutes=reservation.duration_minutes) > now
        ]
        reserved_ids = {
            table_id
            for reservation in active
            for table_id in (
                [link.table_id for link in reservation.reservation_tables]
                or [reservation.table_id]
            )
        }
        tables_result = await db.execute(select(RestaurantTable).where(RestaurantTable.status == "RESERVED"))
        for table in tables_result.scalars().all():
            if table.id not in reserved_ids:
                table.status = "FREE"
                table.current_guests = None
                db.add(table)
        if reserved_ids:
            due_tables = await db.execute(select(RestaurantTable).where(RestaurantTable.id.in_(reserved_ids)))
            for table in due_tables.scalars().all():
                if table.status == "FREE":
                    table.status = "RESERVED"
                    db.add(table)
        if commit:
            await db.commit()

    async def _mark_reserved_if_due(
        self, db: AsyncSession, *, reservation: Reservation, tables: list[RestaurantTable]
    ) -> None:
        if reservation.reservation_time <= datetime.now(timezone.utc) + timedelta(hours=2):
            for table in tables:
                if table.status == "FREE":
                    table.status = "RESERVED"
                    db.add(table)

    async def _get_tables(self, db: AsyncSession, table_ids: list[int]) -> list[RestaurantTable]:
        result = await db.execute(
            select(RestaurantTable).where(
                RestaurantTable.id.in_(table_ids), RestaurantTable.is_active.is_(True)
            )
        )
        by_id = {table.id: table for table in result.scalars().all()}
        if len(by_id) != len(set(table_ids)):
            raise ValueError("One or more selected tables do not exist.")
        return [by_id[table_id] for table_id in table_ids]

    async def _get_products(self, db: AsyncSession, product_ids: list[int]) -> dict[int, Product]:
        if not product_ids:
            return {}
        result = await db.execute(
            select(Product).where(Product.id.in_(set(product_ids)), Product.is_active.is_(True))
        )
        products = {product.id: product for product in result.scalars().all()}
        if len(products) != len(set(product_ids)):
            raise ValueError("One or more preorder products are unavailable.")
        return products

    async def _ensure_tables_available(
        self,
        db: AsyncSession,
        *,
        table_ids: list[int],
        starts_at: datetime,
        duration_minutes: int,
        exclude_reservation_id: int | None = None,
    ) -> None:
        ends_at = starts_at + timedelta(minutes=duration_minutes)
        result = await db.execute(
            select(Reservation)
            .outerjoin(ReservationTable, ReservationTable.reservation_id == Reservation.id)
            .where(
                or_(
                    Reservation.table_id.in_(table_ids),
                    ReservationTable.table_id.in_(table_ids),
                ),
                Reservation.status.in_(ACTIVE_STATUSES),
                Reservation.reservation_time < ends_at,
            )
        )
        for existing in result.scalars().unique().all():
            if existing.id == exclude_reservation_id:
                continue
            if existing.reservation_time + timedelta(minutes=existing.duration_minutes) > starts_at:
                raise ValueError("Selected table already has a reservation in this time range.")

    def _replace_tables(self, db: AsyncSession, *, reservation: Reservation, table_ids: list[int]) -> None:
        for table_id in table_ids:
            db.add(ReservationTable(reservation_id=reservation.id, table_id=table_id))

    def _replace_items(self, db: AsyncSession, *, reservation: Reservation, items, products) -> None:
        for item in items:
            unit_price = products[item.product_id].price
            db.add(
                ReservationItem(
                    reservation_id=reservation.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=unit_price,
                    total_price=unit_price * item.quantity,
                    notes=item.notes,
                )
            )

    @staticmethod
    def _require_manager_role(role: str) -> None:
        if role not in MANAGEMENT_ROLES:
            raise PermissionError("Only service staff can manage reservations.")


reservation_service = ReservationService()
