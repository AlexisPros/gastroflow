from datetime import date
from decimal import Decimal

from app.schemas.base import OrmBaseModel


class ReportSoldItem(OrmBaseModel):
    product_id: int
    product_name: str
    quantity: int
    total: Decimal


class ReportPaymentMethod(OrmBaseModel):
    method: str
    count: int
    total: Decimal


class ReportDiscount(OrmBaseModel):
    discount_id: int | None = None
    name: str
    type: str
    value: Decimal | None = None
    uses: int
    total_discount_amount: Decimal


class DailySalesReport(OrmBaseModel):
    report_date: date
    orders_count: int
    items_count: int
    total_sales: Decimal
    total_tips: Decimal
    total_discounts: Decimal
    cash_total: Decimal
    card_total: Decimal
    other_payment_total: Decimal
    sold_items: list[ReportSoldItem]
    discounts: list[ReportDiscount]
    payment_methods: list[ReportPaymentMethod]


class ProductionSectionReport(OrmBaseModel):
    section_id: int
    section_name: str
    tasks_count: int
    completed_tasks_count: int
    items_count: int
    estimated_minutes: int
    actual_minutes: int
    sold_items: list[ReportSoldItem]


class DailyProductionReport(OrmBaseModel):
    report_date: date
    scope: str
    sections: list[ProductionSectionReport]
    tasks_count: int
    completed_tasks_count: int
    items_count: int
    estimated_minutes: int
    actual_minutes: int


class DailyOperationsReport(OrmBaseModel):
    report_date: date
    sales: DailySalesReport
    kitchen: DailyProductionReport
    bar: DailyProductionReport
    production_total: DailyProductionReport
