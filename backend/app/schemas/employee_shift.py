from datetime import datetime

from app.schemas.base import OrmBaseModel


class EmployeeShiftBase(OrmBaseModel):
    user_id: int
    status: str = "OPEN"
    opening_note: str | None = None
    closing_note: str | None = None


class EmployeeShiftCreate(EmployeeShiftBase):
    pass


class EmployeeShiftUpdate(OrmBaseModel):
    ended_at: datetime | None = None
    status: str | None = None
    opening_note: str | None = None
    closing_note: str | None = None


class EmployeeShiftRead(EmployeeShiftBase):
    id: int
    started_at: datetime
    ended_at: datetime | None = None
