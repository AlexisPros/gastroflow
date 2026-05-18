from app.schemas.base import OrmBaseModel


class IngredientBase(OrmBaseModel):
    name: str
    unit: str
    is_active: bool = True


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(OrmBaseModel):
    name: str | None = None
    unit: str | None = None
    is_active: bool | None = None


class IngredientRead(IngredientBase):
    id: int
