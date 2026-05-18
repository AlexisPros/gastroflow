from datetime import datetime

from app.schemas.base import OrmBaseModel


class ReservationBase(OrmBaseModel):
    table_id: int
    customer_name: str
    customer_phone: str
    guest_count: int
    reservation_time: datetime
    notes: str | None = None


class ReservationCreate(ReservationBase):
    pass


class ReservationUpdate(OrmBaseModel):
    table_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    guest_count: int | None = None
    reservation_time: datetime | None = None
    status: str | None = None
    notes: str | None = None


class ReservationRead(ReservationBase):
    id: int
    status: str
    created_at: datetime
