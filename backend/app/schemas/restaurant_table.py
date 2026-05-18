from app.schemas.base import OrmBaseModel


class RestaurantTableBase(OrmBaseModel):
    table_number: str
    current_guests: int | None = None
    qr_code_url: str | None = None
    is_active: bool = True


class RestaurantTableCreate(RestaurantTableBase):
    pass


class RestaurantTableUpdate(OrmBaseModel):
    table_number: str | None = None
    current_guests: int | None = None
    status: str | None = None
    qr_code_url: str | None = None
    is_active: bool | None = None


class RestaurantTableRead(RestaurantTableBase):
    id: int
    status: str
