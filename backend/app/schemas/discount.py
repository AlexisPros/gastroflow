from app.schemas.base import OrmBaseModel


class DiscountBase(OrmBaseModel):
    name: str
    type: str
    value: float
    is_active: bool = True


class DiscountCreate(DiscountBase):
    pass


class DiscountUpdate(OrmBaseModel):
    name: str | None = None
    type: str | None = None
    value: float | None = None
    is_active: bool | None = None


class DiscountRead(DiscountBase):
    id: int
