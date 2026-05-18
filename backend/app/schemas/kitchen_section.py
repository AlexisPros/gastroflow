from app.schemas.base import OrmBaseModel


class KitchenSectionBase(OrmBaseModel):
    name: str
    is_active: bool = True


class KitchenSectionCreate(KitchenSectionBase):
    pass


class KitchenSectionUpdate(OrmBaseModel):
    name: str | None = None
    is_active: bool | None = None


class KitchenSectionRead(KitchenSectionBase):
    id: int
