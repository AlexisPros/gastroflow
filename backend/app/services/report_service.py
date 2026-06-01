from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import Discount
from app.models.kitchen_section import KitchenSection
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.schemas.daily_report import (
    DailyOperationsReport,
    DailyProductionReport,
    DailySalesReport,
    ProductionSectionReport,
    ReportDiscount,
    ReportPaymentMethod,
    ReportSoldItem,
)


class ReportService:
    async def build_daily_sales_report(
        self,
        db: AsyncSession,
        *,
        report_date: date | None = None,
    ) -> DailySalesReport:
        current_date = report_date or datetime.now(timezone.utc).date()
        orders = await self._get_closed_orders_for_day(db, report_date=current_date)
        order_ids = [order.id for order in orders]

        sold_items = await self._build_sold_items(db, order_ids=order_ids)
        discounts = await self._build_discounts_breakdown(db, orders=orders)
        payment_methods = await self._build_payment_methods(db, order_ids=order_ids)

        payment_totals = {
            item.method: item.total
            for item in payment_methods
        }
        other_payment_total = sum(
            (
                total
                for method, total in payment_totals.items()
                if method not in {"CASH", "CARD"}
            ),
            Decimal("0.00"),
        )

        return DailySalesReport(
            report_date=current_date,
            orders_count=len(orders),
            items_count=sum(item.quantity for item in sold_items),
            total_sales=sum((order.total_amount for order in orders), Decimal("0.00")),
            total_tips=sum((order.tip_amount for order in orders), Decimal("0.00")),
            total_discounts=sum(
                (order.discount_amount for order in orders),
                Decimal("0.00"),
            ),
            cash_total=payment_totals.get("CASH", Decimal("0.00")),
            card_total=payment_totals.get("CARD", Decimal("0.00")),
            other_payment_total=other_payment_total,
            sold_items=sold_items,
            discounts=discounts,
            payment_methods=payment_methods,
        )

    async def build_daily_production_report(
        self,
        db: AsyncSession,
        *,
        scope: str,
        report_date: date | None = None,
    ) -> DailyProductionReport:
        current_date = report_date or datetime.now(timezone.utc).date()
        section_rows = await self._get_production_rows(
            db,
            report_date=current_date,
            scope=scope,
        )
        sections = self._group_production_rows(section_rows)

        return DailyProductionReport(
            report_date=current_date,
            scope=scope.upper(),
            sections=sections,
            tasks_count=sum(section.tasks_count for section in sections),
            completed_tasks_count=sum(
                section.completed_tasks_count
                for section in sections
            ),
            items_count=sum(section.items_count for section in sections),
            estimated_minutes=sum(
                section.estimated_minutes
                for section in sections
            ),
            actual_minutes=sum(section.actual_minutes for section in sections),
        )

    async def build_daily_operations_report(
        self,
        db: AsyncSession,
        *,
        report_date: date | None = None,
    ) -> DailyOperationsReport:
        current_date = report_date or datetime.now(timezone.utc).date()
        sales = await self.build_daily_sales_report(db, report_date=current_date)
        kitchen = await self.build_daily_production_report(
            db,
            report_date=current_date,
            scope="KITCHEN",
        )
        bar = await self.build_daily_production_report(
            db,
            report_date=current_date,
            scope="BAR",
        )
        production_total = await self.build_daily_production_report(
            db,
            report_date=current_date,
            scope="ALL",
        )

        return DailyOperationsReport(
            report_date=current_date,
            sales=sales,
            kitchen=kitchen,
            bar=bar,
            production_total=production_total,
        )

    async def _get_closed_orders_for_day(
        self,
        db: AsyncSession,
        *,
        report_date: date,
    ) -> list[Order]:
        start_at, end_at = self._day_bounds(report_date)
        result = await db.execute(
            select(Order).where(
                Order.status == "CLOSED",
                Order.closed_at >= start_at,
                Order.closed_at < end_at,
            ),
        )
        return list(result.scalars().all())

    async def _get_production_rows(
        self,
        db: AsyncSession,
        *,
        report_date: date,
        scope: str,
    ) -> list[tuple[KitchenTask, KitchenSection, OrderItem, Product]]:
        start_at, end_at = self._day_bounds(report_date)
        statement = (
            select(KitchenTask, KitchenSection, OrderItem, Product)
            .join(KitchenSection, KitchenTask.kitchen_section_id == KitchenSection.id)
            .join(OrderItem, KitchenTask.order_item_id == OrderItem.id)
            .join(Product, OrderItem.product_id == Product.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.status == "CLOSED",
                Order.closed_at >= start_at,
                Order.closed_at < end_at,
            )
        )

        normalized_scope = scope.upper()
        if normalized_scope == "BAR":
            statement = statement.where(KitchenSection.name.ilike("bar"))
        elif normalized_scope == "KITCHEN":
            statement = statement.where(KitchenSection.name.not_ilike("bar"))
        elif normalized_scope != "ALL":
            raise ValueError("Unknown report scope.")

        result = await db.execute(statement)
        return cast(
            list[tuple[KitchenTask, KitchenSection, OrderItem, Product]],
            list(result.all()),
        )

    def _group_production_rows(
        self,
        rows: list[tuple[KitchenTask, KitchenSection, OrderItem, Product]],
    ) -> list[ProductionSectionReport]:
        grouped: dict[int, ProductionSectionReport] = {}
        for task, section, order_item, product in rows:
            section_row = grouped.setdefault(
                section.id,
                ProductionSectionReport(
                    section_id=section.id,
                    section_name=section.name,
                    tasks_count=0,
                    completed_tasks_count=0,
                    items_count=0,
                    estimated_minutes=0,
                    actual_minutes=0,
                    sold_items=[],
                ),
            )
            section_row.tasks_count += 1
            section_row.items_count += order_item.quantity
            section_row.estimated_minutes += (task.estimated_time or 0) * order_item.quantity
            if task.status == "COMPLETED":
                section_row.completed_tasks_count += 1
            if task.started_at is not None and task.completed_at is not None:
                section_row.actual_minutes += max(
                    0,
                    int((task.completed_at - task.started_at).total_seconds() // 60),
                )

            self._add_sold_item(
                section_row.sold_items,
                product_id=product.id,
                product_name=product.name,
                quantity=order_item.quantity,
                total=order_item.total_price,
            )

        return list(grouped.values())

    async def _build_sold_items(
        self,
        db: AsyncSession,
        *,
        order_ids: list[int],
    ) -> list[ReportSoldItem]:
        if not order_ids:
            return []

        result = await db.execute(
            select(OrderItem, Product)
            .join(Product, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id.in_(order_ids)),
        )

        grouped: list[ReportSoldItem] = []
        for order_item, product in result.all():
            self._add_sold_item(
                grouped,
                product_id=product.id,
                product_name=product.name,
                quantity=order_item.quantity,
                total=order_item.total_price,
            )

        return grouped

    async def _build_discounts_breakdown(
        self,
        db: AsyncSession,
        *,
        orders: list[Order],
    ) -> list[ReportDiscount]:
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

        grouped: dict[int | None, ReportDiscount] = {}
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
                ReportDiscount(
                    discount_id=order.discount_id,
                    name=discount.name if discount is not None else "Unknown discount",
                    type=discount.type if discount is not None else "UNKNOWN",
                    value=discount.value if discount is not None else None,
                    uses=0,
                    total_discount_amount=Decimal("0.00"),
                ),
            )
            row.uses += 1
            row.total_discount_amount += order.discount_amount

        return list(grouped.values())

    async def _build_payment_methods(
        self,
        db: AsyncSession,
        *,
        order_ids: list[int],
    ) -> list[ReportPaymentMethod]:
        if not order_ids:
            return []

        result = await db.execute(
            select(Payment).where(
                Payment.order_id.in_(order_ids),
                Payment.status == "COMPLETED",
            ),
        )

        grouped: dict[str, ReportPaymentMethod] = defaultdict(
            lambda: ReportPaymentMethod(method="", count=0, total=Decimal("0.00")),
        )
        for payment in result.scalars().all():
            method = payment.method.upper()
            row = grouped[method]
            row.method = method
            row.count += 1
            row.total += payment.amount

        return list(grouped.values())

    def _add_sold_item(
        self,
        rows: list[ReportSoldItem],
        *,
        product_id: int,
        product_name: str,
        quantity: int,
        total: Decimal,
    ) -> None:
        for row in rows:
            if row.product_id == product_id:
                row.quantity += quantity
                row.total += total
                return

        rows.append(
            ReportSoldItem(
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                total=total,
            ),
        )

    def _day_bounds(self, report_date: date) -> tuple[datetime, datetime]:
        start_at = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
        return start_at, start_at + timedelta(days=1)


report_service = ReportService()
