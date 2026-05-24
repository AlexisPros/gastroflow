from app.schemas.base import OrmBaseModel
from decimal import Decimal

class ModifierBase(OrmBaseModel):
    name: str
    price: Decimal = Decimal("0.00")
    is_active: bool = True


class ModifierCreate(ModifierBase):
    pass


class ModifierUpdate(OrmBaseModel):
    name: str | None = None
    price: Decimal | None = None
    is_active: bool | None = None


class ModifierRead(ModifierBase):
    id: int
