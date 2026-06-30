from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import employee_shift as crud_employee_shift
from app.crud import employee_shift_report as crud_employee_shift_report
from app.models.discount import Discount
from app.models.employee_shift import EmployeeShift
from app.models.employee_shift_report import EmployeeShiftReport
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.reservation_payment import ReservationPayment
from app.models.product import Product
from app.models.user import User


class ShiftService:
    async def start_shift(
        self,
        db: AsyncSession,
        *,
        user: User,
        opening_note: str | None = None,
    ) -> EmployeeShift:
        open_shift = await crud_employee_shift.get_open_by_user(
            db,
            user_id=user.id,
        )
        if open_shift is not None:
            return open_shift

        shift = EmployeeShift(
            user_id=user.id,
            opening_note=opening_note,
            status="OPEN",
        )
        db.add(shift)
        await db.commit()
        await db.refresh(shift)
        return shift

    async def get_current_shift(
        self,
        db: AsyncSession,
        *,
        user: User,
    ) -> EmployeeShift | None:
        return await crud_employee_shift.get_open_by_user(db, user_id=user.id)

    async def preview_current_shift_report(
        self,
        db: AsyncSession,
        *,
        user: User,
    ) -> EmployeeShiftReport | None:
        shift = await self.get_current_shift(db, user=user)
        if shift is None:
            return None

        return await self._build_report(db, shift=shift)

    async def require_open_shift(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> EmployeeShift:
        open_shift = await crud_employee_shift.get_open_by_user(
            db,
            user_id=user_id,
        )
        if open_shift is None:
            raise ValueError("Start shift first.")

        return open_shift

    async def close_current_shift(
        self,
        db: AsyncSession,
        *,
        user: User,
        closing_note: str | None = None,
    ) -> EmployeeShiftReport:
        shift = await self.require_open_shift(db, user_id=user.id)
        existing_report = await crud_employee_shift_report.get_by_shift(
            db,
            shift_id=shift.id,
        )
        if existing_report is not None:
            return existing_report

        await self._ensure_shift_has_no_active_orders(db, shift=shift)

        await crud_employee_shift.close(
            db,
            db_obj=shift,
            closing_note=closing_note,
        )
        report = await self._build_report(db, shift=shift)

        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report

    async def _ensure_shift_has_no_active_orders(
        self,
        db: AsyncSession,
        *,
        shift: EmployeeShift,
    ) -> None:
        result = await db.execute(
            select(Order).where(
                Order.shift_id == shift.id,
                Order.status.in_(["PENDING_CONFIRMATION", "OPEN", "IN_PROGRESS"]),
            ),
        )
        active_order = result.scalar_one_or_none()
        if active_order is not None:
            raise ValueError("Close active orders before ending shift.")

    async def _build_report(
        self,
        db: AsyncSession,
        *,
        shift: EmployeeShift,
    ) -> EmployeeShiftReport:
        orders = await self._get_closed_shift_orders(db, shift_id=shift.id)
        order_ids = [order.id for order in orders]

        sold_items = await self._build_sold_items(db, order_ids=order_ids)
        discounts = await self._build_discounts_breakdown(db, orders=orders)
        payment_methods = await self._build_payment_methods(
            db, order_ids=order_ids, shift_id=shift.id
        )

        total_sales = sum(
            (Decimal(item["total"]) for item in payment_methods),
            Decimal("0.00"),
        )
        total_tips = sum((order.tip_amount for order in orders), Decimal("0.00"))
        total_discounts = sum(
            (order.discount_amount for order in orders),
            Decimal("0.00"),
        )

        payment_totals = {
            item["method"]: Decimal(item["total"])
            for item in payment_methods
        }

        return EmployeeShiftReport(
            shift_id=shift.id,
            user_id=shift.user_id,
            orders_count=len(orders),
            items_count=sum(item["quantity"] for item in sold_items),
            total_sales=total_sales,
            total_tips=total_tips,
            total_discounts=total_discounts,
            cash_total=payment_totals.get("CASH", Decimal("0.00")),
            card_total=payment_totals.get("CARD", Decimal("0.00")),
            other_payment_total=sum(
                total
                for method, total in payment_totals.items()
                if method not in {"CASH", "CARD"}
            ),
            report_data={
                "sold_items": sold_items,
                "discounts": discounts,
                "payment_methods": payment_methods,
            },
        )

    async def _get_closed_shift_orders(
        self,
        db: AsyncSession,
        *,
        shift_id: int,
    ) -> list[Order]:
        result = await db.execute(
            select(Order).where(
                Order.shift_id == shift_id,
                Order.status == "CLOSED",
            ),
        )
        return list(result.scalars().all())

    async def _build_sold_items(
        self,
        db: AsyncSession,
        *,
        order_ids: list[int],
    ) -> list[dict[str, Any]]:
        if not order_ids:
            return []

        result = await db.execute(
            select(OrderItem, Product)
            .join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id.in_(order_ids)),
        )

        grouped: dict[int, dict[str, Any]] = {}
        for order_item, product in result.all():
            row = grouped.setdefault(
                product.id,
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity": 0,
                    "total": Decimal("0.00"),
                },
            )
            row["quantity"] += order_item.quantity
            row["total"] += order_item.total_price

        return [
            {
                **row,
                "total": str(row["total"]),
            }
            for row in grouped.values()
        ]

    async def _build_discounts_breakdown(
        self,
        db: AsyncSession,
        *,
        orders: list[Order],
    ) -> list[dict[str, Any]]:
        discount_ids = {
            order.discount_id
            for order in orders
            if order.discount_id is not None and order.discount_amount > 0
        }
        discounts_by_id: dict[int, Discount] = {}
        if discount_ids:
            result = await db.execute(
                select(Discount).where(Discount.id.in_(discount_ids)),
            )
            discounts_by_id = {
                discount.id: discount
                for discount in result.scalars().all()
            }

        grouped: dict[int | None, dict[str, Any]] = {}
        for order in orders:
            if order.discount_amount <= 0:
                continue

            discount = (
                discounts_by_id.get(order.discount_id)
                if order.discount_id is not None
                else None
            )
            row = grouped.setdefault(
                order.discount_id,
                {
                    "discount_id": order.discount_id,
                    "name": discount.name if discount is not None else "Unknown discount",
                    "type": discount.type if discount is not None else "UNKNOWN",
                    "value": str(discount.value) if discount is not None else None,
                    "uses": 0,
                    "total_discount_amount": Decimal("0.00"),
                },
            )
            row["uses"] += 1
            row["total_discount_amount"] += order.discount_amount

        return [
            {
                **row,
                "total_discount_amount": str(row["total_discount_amount"]),
            }
            for row in grouped.values()
        ]

    async def _build_payment_methods(
        self,
        db: AsyncSession,
        *,
        order_ids: list[int],
        shift_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if not order_ids and shift_id is None:
            return []

        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"method": "", "count": 0, "total": Decimal("0.00")},
        )
        payments: list[Payment | ReservationPayment] = []
        if order_ids:
            result = await db.execute(
                select(Payment).where(
                    Payment.order_id.in_(order_ids),
                    Payment.status == "COMPLETED",
                ),
            )
            payments.extend(result.scalars().all())
        if shift_id is not None:
            reservation_result = await db.execute(
                select(ReservationPayment).where(
                    ReservationPayment.shift_id == shift_id,
                    ReservationPayment.status == "COMPLETED",
                )
            )
            payments.extend(reservation_result.scalars().all())
        for payment in payments:
            method = payment.method.upper()
            row = grouped[method]
            row["method"] = method
            row["count"] += 1
            row["total"] += payment.amount

        return [
            {
                **row,
                "total": str(row["total"]),
            }
            for row in grouped.values()
        ]


shift_service = ShiftService()
