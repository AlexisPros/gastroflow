from app.schemas.base import OrmBaseModel
from decimal import Decimal

class ProductModifierBase(OrmBaseModel):
    product_id: int
    modifier_id: int
    price_override: Decimal | None = None
    is_active: bool = True


class ProductModifierCreate(ProductModifierBase):
    pass


class ProductModifierUpdate(OrmBaseModel):
    product_id: int | None = None
    modifier_id: int | None = None
    price_override: Decimal | None = None
    is_active: bool | None = None


class ProductModifierRead(ProductModifierBase):
    id: int
