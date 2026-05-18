from app.schemas.base import OrmBaseModel


class ProductIngredientBase(OrmBaseModel):
    product_id: int
    ingredient_id: int
    quantity: float


class ProductIngredientCreate(ProductIngredientBase):
    pass


class ProductIngredientUpdate(OrmBaseModel):
    product_id: int | None = None
    ingredient_id: int | None = None
    quantity: float | None = None


class ProductIngredientRead(ProductIngredientBase):
    id: int
