from datetime import datetime

from app.schemas.base import OrmBaseModel


class ProductBase(OrmBaseModel):
    category_id: int
    kitchen_section_id: int | None = None
    name: str
    description: str | None = None
    price: float
    preparation_time: int | None = None
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(OrmBaseModel):
    category_id: int | None = None
    kitchen_section_id: int | None = None
    name: str | None = None
    description: str | None = None
    price: float | None = None
    preparation_time: int | None = None
    is_active: bool | None = None


class ProductRead(ProductBase):
    id: int
    created_at: datetime
