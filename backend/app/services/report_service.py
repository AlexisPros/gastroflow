from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount import Discount
from app.models.employee_shift_report import EmployeeShiftReport
from app.models.kitchen_section import KitchenSection
from app.models.kitchen_task import KitchenTask
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.reservation_payment import ReservationPayment
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
from app.schemas.reports import (
    ChartDataPoint,
    EmployeeProductivityCompare,
    AdvancedSalesReport,
    WarehouseReportDocument,
    WarehouseReport,
    UserActionLogReport,
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
        start_at, end_at = self._day_bounds(current_date)
        payment_methods = await self._build_payment_methods(
            db, order_ids=order_ids, reservation_payment_window=(start_at, end_at)
        )

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
            total_sales=sum((item.total for item in payment_methods), Decimal("0.00")),
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
        reservation_payment_window: tuple[datetime, datetime] | None = None,
    ) -> list[ReportPaymentMethod]:
        if not order_ids and reservation_payment_window is None:
            return []

        grouped: dict[str, ReportPaymentMethod] = defaultdict(
            lambda: ReportPaymentMethod(method="", count=0, total=Decimal("0.00")),
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
        if reservation_payment_window is not None:
            start_at, end_at = reservation_payment_window
            reservation_result = await db.execute(
                select(ReservationPayment).where(
                    ReservationPayment.status == "COMPLETED",
                    ReservationPayment.created_at >= start_at,
                    ReservationPayment.created_at < end_at,
                )
            )
            payments.extend(reservation_result.scalars().all())
        for payment in payments:
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

    async def build_advanced_sales_report(
        self,
        db: AsyncSession,
        *,
        period: str,
        date_str: str | None = None,
        user_id: int | None = None,
    ) -> AdvancedSalesReport:
        base_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_str
            else datetime.now(timezone.utc).date()
        )

        if period == "week":
            start_date = base_date - timedelta(days=base_date.weekday())
            end_date = start_date + timedelta(days=7)
        elif period == "month":
            start_date = base_date.replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)
        elif period == "quarter":
            quarter = (base_date.month - 1) // 3
            start_date = base_date.replace(month=quarter * 3 + 1, day=1)
            if start_date.month > 9:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 3)
        elif period == "half_year":
            half = 0 if base_date.month <= 6 else 1
            start_date = base_date.replace(month=half * 6 + 1, day=1)
            if half == 0:
                end_date = start_date.replace(month=7)
            else:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
        elif period == "year":
            start_date = base_date.replace(month=1, day=1)
            end_date = start_date.replace(year=start_date.year + 1)
        else:
            raise ValueError("Invalid period")

        start_datetime = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_datetime = datetime.combine(end_date, time.min, tzinfo=timezone.utc)

        stmt = (
            select(EmployeeShiftReport)
            .where(
                EmployeeShiftReport.created_at >= start_datetime,
                EmployeeShiftReport.created_at < end_datetime,
            )
        )
        if user_id is not None:
            stmt = stmt.where(EmployeeShiftReport.user_id == user_id)

        result = await db.execute(stmt)
        shift_reports = list(result.scalars().all())

        # Aggregate metrics from employee shift reports
        orders_count = sum(r.orders_count for r in shift_reports)
        items_count = sum(r.items_count for r in shift_reports)
        total_sales = sum(r.total_sales for r in shift_reports)
        total_tips = sum(r.total_tips for r in shift_reports)
        total_discounts = sum(r.total_discounts for r in shift_reports)
        cash_total = sum(r.cash_total for r in shift_reports)
        card_total = sum(r.card_total for r in shift_reports)
        other_payment_total = sum(r.other_payment_total for r in shift_reports)

        # Aggregate sold items
        sold_items_grouped = {}
        for r in shift_reports:
            r_sold = r.report_data.get("sold_items", [])
            for item in r_sold:
                p_id = item["product_id"]
                p_name = item["product_name"]
                qty = item["quantity"]
                tot = Decimal(str(item["total"]))
                
                row = sold_items_grouped.setdefault(p_id, {
                    "product_id": p_id,
                    "product_name": p_name,
                    "quantity": 0,
                    "total": Decimal("0.00")
                })
                row["quantity"] += qty
                row["total"] += tot

        sold_items = [
            ReportSoldItem(
                product_id=row["product_id"],
                product_name=row["product_name"],
                quantity=row["quantity"],
                total=row["total"]
            )
            for row in sold_items_grouped.values()
        ]

        # Aggregate discounts
        discounts_grouped = {}
        for r in shift_reports:
            r_disc = r.report_data.get("discounts", [])
            for disc in r_disc:
                disc_id = disc.get("discount_id")
                name = disc["name"]
                dtype = disc["type"]
                val = Decimal(str(disc["value"])) if disc.get("value") is not None else None
                uses = disc["uses"]
                total_discount_amount = Decimal(str(disc["total_discount_amount"]))

                row = discounts_grouped.setdefault(disc_id, {
                    "discount_id": disc_id,
                    "name": name,
                    "type": dtype,
                    "value": val,
                    "uses": 0,
                    "total_discount_amount": Decimal("0.00")
                })
                row["uses"] += uses
                row["total_discount_amount"] += total_discount_amount

        discounts = [
            ReportDiscount(
                discount_id=row["discount_id"],
                name=row["name"],
                type=row["type"],
                value=row["value"],
                uses=row["uses"],
                total_discount_amount=row["total_discount_amount"]
            )
            for row in discounts_grouped.values()
        ]

        # Aggregate payment methods
        payment_methods_grouped = {}
        for r in shift_reports:
            r_payments = r.report_data.get("payment_methods", [])
            for pm in r_payments:
                method = pm["method"]
                count = pm["count"]
                total = Decimal(str(pm["total"]))

                row = payment_methods_grouped.setdefault(method, {
                    "method": method,
                    "count": 0,
                    "total": Decimal("0.00")
                })
                row["count"] += count
                row["total"] += total

        payment_methods = [
            ReportPaymentMethod(
                method=row["method"],
                count=row["count"],
                total=row["total"]
            )
            for row in payment_methods_grouped.values()
        ]

        # Build chart data
        buckets = []
        if period in {"week", "month"}:
            current = start_date
            while current < end_date:
                buckets.append((current, current + timedelta(days=1), current.strftime("%Y-%m-%d")))
                current += timedelta(days=1)
        elif period == "quarter":
            current = start_date
            week_idx = 1
            while current < end_date:
                next_week = current + timedelta(days=7)
                buckets.append((current, next_week, f"Tydzień {week_idx} ({current.strftime('%m-%d')})"))
                current = next_week
                week_idx += 1
        elif period in {"half_year", "year"}:
            current = start_date
            while current < end_date:
                if current.month == 12:
                    nxt = current.replace(year=current.year + 1, month=1)
                else:
                    nxt = current.replace(month=current.month + 1)
                buckets.append((current, nxt, current.strftime("%Y-%m")))
                current = nxt

        chart_data_points = []
        if buckets:
            for b_start, b_end, label in buckets:
                b_start_dt = datetime.combine(b_start, time.min, tzinfo=timezone.utc)
                b_end_dt = datetime.combine(b_end, time.min, tzinfo=timezone.utc)
                val = sum(
                    ((r.total_sales - r.total_tips) for r in shift_reports if r.created_at >= b_start_dt and r.created_at < b_end_dt),
                    Decimal("0.00")
                )
                chart_data_points.append(ChartDataPoint(label=label, value=val))

        total_sales_no_tips = total_sales - total_tips
        average_check = (total_sales_no_tips / orders_count) if orders_count > 0 else Decimal("0.00")
        unique_days = {r.created_at.date() for r in shift_reports}
        active_days_count = len(unique_days)
        average_daily_sales = (total_sales_no_tips / active_days_count) if active_days_count > 0 else Decimal("0.00")

        # Build employee comparison
        employee_comparison = []
        if user_id is None:
            from app.models.user import User
            users_res = await db.execute(select(User))
            users_dict = {u.id: u for u in users_res.scalars().all()}

            reports_by_waiter = defaultdict(list)
            for r in shift_reports:
                reports_by_waiter[r.user_id].append(r)

            for w_id, w_reports in reports_by_waiter.items():
                user = users_dict.get(w_id)
                if not user:
                    continue

                w_total_sales = sum((r.total_sales for r in w_reports), Decimal("0.00"))
                w_total_tips = sum((r.total_tips for r in w_reports), Decimal("0.00"))

                w_items_grouped = {}
                for r in w_reports:
                    r_sold = r.report_data.get("sold_items", [])
                    for item in r_sold:
                        p_id = item["product_id"]
                        p_name = item["product_name"]
                        qty = item["quantity"]
                        tot = Decimal(str(item["total"]))

                        row = w_items_grouped.setdefault(p_id, {
                            "product_id": p_id,
                            "product_name": p_name,
                            "quantity": 0,
                            "total": Decimal("0.00")
                        })
                        row["quantity"] += qty
                        row["total"] += tot

                w_sold_items = [
                    ReportSoldItem(
                        product_id=row["product_id"],
                        product_name=row["product_name"],
                        quantity=row["quantity"],
                        total=row["total"]
                    )
                    for row in w_items_grouped.values()
                ]

                employee_comparison.append(
                    EmployeeProductivityCompare(
                        user_id=user.id,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        total_sales=w_total_sales,
                        total_tips=w_total_tips,
                        sold_items=w_sold_items,
                    )
                )

        return AdvancedSalesReport(
            start_date=start_date,
            end_date=end_date - timedelta(days=1),
            orders_count=orders_count,
            items_count=items_count,
            total_sales=total_sales,
            total_tips=total_tips,
            total_discounts=total_discounts,
            cash_total=cash_total,
            card_total=card_total,
            other_payment_total=other_payment_total,
            sold_items=sold_items,
            discounts=discounts,
            payment_methods=payment_methods,
            chart_data=chart_data_points,
            average_check=average_check,
            average_daily_sales=average_daily_sales,
            employee_comparison=employee_comparison,
        )

    async def build_warehouse_report(
        self,
        db: AsyncSession,
        *,
        document_type: str | None = None,
        period: str,
        date_str: str | None = None,
    ) -> WarehouseReport:
        base_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_str
            else datetime.now(timezone.utc).date()
        )

        if period == "day":
            start_date = base_date
            end_date = base_date + timedelta(days=1)
        elif period == "week":
            start_date = base_date - timedelta(days=base_date.weekday())
            end_date = start_date + timedelta(days=7)
        elif period == "month":
            start_date = base_date.replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)
        else:
            raise ValueError("Invalid period for warehouse report")

        from app.models.warehouse_document import WarehouseDocument

        stmt = (
            select(WarehouseDocument)
            .where(
                WarehouseDocument.operation_date >= start_date,
                WarehouseDocument.operation_date < end_date,
            )
        )
        if document_type and document_type != "ALL":
            stmt = stmt.where(WarehouseDocument.document_type == document_type.upper())

        from app.models.warehouse_document_item import WarehouseDocumentItem
        from app.schemas.reports import WarehouseReportDocumentItem, WarehouseUnitBreakdown

        stmt = stmt.order_by(WarehouseDocument.operation_date.desc(), WarehouseDocument.id.desc())
        stmt = stmt.options(
            selectinload(WarehouseDocument.source_warehouse),
            selectinload(WarehouseDocument.destination_warehouse),
            selectinload(WarehouseDocument.issued_by_user),
            selectinload(WarehouseDocument.items).selectinload(WarehouseDocumentItem.ingredient),
        )

        res = await db.execute(stmt)
        documents = res.scalars().all()

        docs_report = []
        total_positions = 0
        units_agg = defaultdict(Decimal)

        for doc in documents:
            items_count = sum((item.quantity for item in doc.items), Decimal("0.00"))
            total_positions += len(doc.items)

            doc_items = []
            for item in doc.items:
                units_agg[item.ingredient.unit] += item.quantity
                doc_items.append(
                    WarehouseReportDocumentItem(
                        id=item.id,
                        ingredient_id=item.ingredient_id,
                        ingredient_name=item.ingredient.name,
                        quantity=item.quantity,
                        unit=item.ingredient.unit,
                        unit_price=item.unit_price,
                        total_value=item.total_value,
                        book_quantity=item.book_quantity,
                        actual_quantity=item.actual_quantity,
                        difference_quantity=item.difference_quantity,
                        difference_value=item.difference_value,
                    )
                )

            docs_report.append(
                WarehouseReportDocument(
                    id=doc.id,
                    document_number=doc.document_number,
                    document_type=doc.document_type,
                    operation_date=doc.operation_date,
                    status=doc.status,
                    source_warehouse_name=doc.source_warehouse.name if doc.source_warehouse else None,
                    destination_warehouse_name=doc.destination_warehouse.name if doc.destination_warehouse else None,
                    issued_by_user_name=f"{doc.issued_by_user.first_name} {doc.issued_by_user.last_name}" if doc.issued_by_user else None,
                    items_count=items_count,
                    reason=doc.reason,
                    description=doc.description,
                    items=doc_items,
                )
            )

        unit_breakdown = [
            WarehouseUnitBreakdown(unit=u, total_quantity=q)
            for u, q in sorted(units_agg.items())
        ]

        return WarehouseReport(
            start_date=start_date,
            end_date=end_date - timedelta(days=1),
            document_count=len(documents),
            total_positions_count=total_positions,
            unit_breakdown=unit_breakdown,
            documents=docs_report,
        )

    async def build_user_action_logs(
        self,
        db: AsyncSession,
        *,
        user_id: int | None = None,
        date_str: str | None = None,
    ) -> list[UserActionLogReport]:
        base_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_str
            else datetime.now(timezone.utc).date()
        )
        start_datetime = datetime.combine(base_date, time.min, tzinfo=timezone.utc)
        end_datetime = start_datetime + timedelta(days=1)

        from app.models.order_action_log import OrderActionLog

        stmt = (
            select(OrderActionLog)
            .where(
                OrderActionLog.created_at >= start_datetime,
                OrderActionLog.created_at < end_datetime,
            )
        )
        if user_id is not None:
            stmt = stmt.where(OrderActionLog.user_id == user_id)

        stmt = stmt.order_by(OrderActionLog.created_at.desc())
        stmt = stmt.options(
            selectinload(OrderActionLog.user)
        )

        res = await db.execute(stmt)
        logs = res.scalars().all()

        report_logs = []
        for log in logs:
            report_logs.append(
                UserActionLogReport(
                    id=log.id,
                    user_id=log.user_id,
                    user_name=f"{log.user.first_name} {log.user.last_name}" if log.user else "System",
                    action_type=log.action_type,
                    description=log.description,
                    created_at=log.created_at,
                    order_id=log.order_id,
                )
            )
        return report_logs

    def _day_bounds(self, report_date: date) -> tuple[datetime, datetime]:
        start_at = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
        return start_at, start_at + timedelta(days=1)


report_service = ReportService()
