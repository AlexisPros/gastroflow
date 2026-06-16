from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.schemas.base import OrmBaseModel


class EmployeeShiftReportBase(OrmBaseModel):
    shift_id: int
    user_id: int
    orders_count: int = 0
    items_count: int = 0
    total_sales: Decimal = Decimal("0.00")
    total_tips: Decimal = Decimal("0.00")
    total_discounts: Decimal = Decimal("0.00")
    cash_total: Decimal = Decimal("0.00")
    card_total: Decimal = Decimal("0.00")
    other_payment_total: Decimal = Decimal("0.00")
    report_data: dict[str, Any] = Field(default_factory=dict)


class EmployeeShiftReportCreate(EmployeeShiftReportBase):
    pass


class EmployeeShiftReportUpdate(OrmBaseModel):
    report_data: dict[str, Any] | None = None


class EmployeeShiftReportPreview(EmployeeShiftReportBase):
    pass


class EmployeeShiftReportRead(EmployeeShiftReportBase):
    id: int
    created_at: datetime
