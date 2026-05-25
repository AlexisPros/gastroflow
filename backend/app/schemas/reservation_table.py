from app.schemas.base import OrmBaseModel


class ReservationTableBase(OrmBaseModel):
    reservation_id: int
    table_id: int


class ReservationTableCreate(ReservationTableBase):
    pass


class ReservationTableUpdate(OrmBaseModel):
    reservation_id: int | None = None
    table_id: int | None = None


class ReservationTableRead(ReservationTableBase):
    id: int
