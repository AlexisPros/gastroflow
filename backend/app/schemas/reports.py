from datetime import date, datetime
from decimal import Decimal
from app.schemas.base import OrmBaseModel
from app.schemas.daily_report import ReportSoldItem, ReportDiscount, ReportPaymentMethod


class ChartDataPoint(OrmBaseModel):
    label: str
    value: Decimal


class EmployeeProductivityCompare(OrmBaseModel):
    user_id: int
    first_name: str
    last_name: str
    total_sales: Decimal
    total_tips: Decimal
    sold_items: list[ReportSoldItem]


class AdvancedSalesReport(OrmBaseModel):
    start_date: date
    end_date: date
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
    chart_data: list[ChartDataPoint]
    average_check: Decimal
    average_daily_sales: Decimal
    employee_comparison: list[EmployeeProductivityCompare]


class WarehouseUnitBreakdown(OrmBaseModel):
    unit: str
    total_quantity: Decimal


class WarehouseReportDocumentItem(OrmBaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal | None = None
    total_value: Decimal | None = None
    book_quantity: Decimal | None = None
    actual_quantity: Decimal | None = None
    difference_quantity: Decimal | None = None
    difference_value: Decimal | None = None


class WarehouseReportDocument(OrmBaseModel):
    id: int
    document_number: str
    document_type: str
    operation_date: date
    status: str
    source_warehouse_name: str | None = None
    destination_warehouse_name: str | None = None
    issued_by_user_name: str | None = None
    items_count: Decimal
    reason: str | None = None
    description: str | None = None
    items: list[WarehouseReportDocumentItem] = []


class WarehouseReport(OrmBaseModel):
    start_date: date
    end_date: date
    document_count: int
    total_positions_count: int
    unit_breakdown: list[WarehouseUnitBreakdown]
    documents: list[WarehouseReportDocument]


class UserActionLogReport(OrmBaseModel):
    id: int
    user_id: int
    user_name: str
    action_type: str
    description: str | None = None
    created_at: datetime
    order_id: int
