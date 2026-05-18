from datetime import datetime

from app.schemas.base import OrmBaseModel


class InvoiceBase(OrmBaseModel):
    order_id: int
    nip: str
    company_name: str
    invoice_number: str
    status: str = "CREATED"


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(OrmBaseModel):
    order_id: int | None = None
    nip: str | None = None
    company_name: str | None = None
    invoice_number: str | None = None
    status: str | None = None


class InvoiceRead(InvoiceBase):
    id: int
    created_at: datetime
