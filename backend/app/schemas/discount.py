from app.schemas.base import OrmBaseModel
from decimal import Decimal


class DiscountBase(OrmBaseModel):
    name: str
    type: str
    value: Decimal
    is_active: bool = True


class DiscountCreate(DiscountBase):
    pass


class DiscountUpdate(OrmBaseModel):
    name: str | None = None
    type: str | None = None
    value: Decimal | None = None
    is_active: bool | None = None


class DiscountRead(DiscountBase):
    id: int
