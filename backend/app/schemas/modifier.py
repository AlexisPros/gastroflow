from app.schemas.base import OrmBaseModel


class ModifierBase(OrmBaseModel):
    name: str
    price: float = 0
    is_active: bool = True


class ModifierCreate(ModifierBase):
    pass


class ModifierUpdate(OrmBaseModel):
    name: str | None = None
    price: float | None = None
    is_active: bool | None = None


class ModifierRead(ModifierBase):
    id: int
