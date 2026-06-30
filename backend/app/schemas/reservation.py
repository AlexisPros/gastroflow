from datetime import datetime
from decimal import Decimal

from pydantic import EmailStr, Field, model_validator

from app.schemas.base import OrmBaseModel


class ReservationItemInput(OrmBaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)


class ReservationCreate(OrmBaseModel):
    table_ids: list[int] = Field(min_length=1)
    customer_name: str = Field(min_length=1, max_length=150)
    customer_phone: str = Field(min_length=3, max_length=50)
    customer_email: EmailStr | None = None
    invoice_nip: str | None = Field(default=None, min_length=10, max_length=20)
    guest_count: int = Field(gt=0)
    reservation_time: datetime
    duration_minutes: int = Field(default=120, ge=30, le=720)
    notes: str | None = Field(default=None, max_length=500)
    items: list[ReservationItemInput] = Field(default_factory=list)
    payment_method: str = "ON_SITE"
    cash_received: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_unique_tables(self):
        if len(self.table_ids) != len(set(self.table_ids)):
            raise ValueError("Reservation tables must be unique.")
        return self


class ReservationUpdate(OrmBaseModel):
    table_ids: list[int] | None = None
    customer_name: str | None = Field(default=None, min_length=1, max_length=150)
    customer_phone: str | None = Field(default=None, min_length=3, max_length=50)
    customer_email: EmailStr | None = None
    invoice_nip: str | None = Field(default=None, min_length=10, max_length=20)
    guest_count: int | None = Field(default=None, gt=0)
    reservation_time: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=30, le=720)
    notes: str | None = Field(default=None, max_length=500)
    items: list[ReservationItemInput] | None = None


class ReservationTableSummary(OrmBaseModel):
    id: int
    table_number: str


class ReservationItemRead(OrmBaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    notes: str | None = None


class ReservationPaymentRead(OrmBaseModel):
    id: int
    method: str
    amount: Decimal
    cash_received: Decimal | None = None
    change_given: Decimal | None = None
    status: str
    created_at: datetime


class ReservationRead(OrmBaseModel):
    id: int
    table_id: int
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    invoice_nip: str | None = None
    guest_count: int
    reservation_time: datetime
    duration_minutes: int
    status: str
    notes: str | None = None
    total_amount: Decimal
    prepaid_amount: Decimal
    payment_status: str
    created_by_user_id: int | None = None
    started_order_id: int | None = None
    started_at: datetime | None = None
    created_at: datetime
    tables: list[ReservationTableSummary] = Field(default_factory=list)
    items: list[ReservationItemRead] = Field(default_factory=list)
    payments: list[ReservationPaymentRead] = Field(default_factory=list)
