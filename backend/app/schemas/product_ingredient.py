from app.schemas.base import OrmBaseModel
from decimal import Decimal

class ProductIngredientBase(OrmBaseModel):
    product_id: int
    ingredient_id: int
    quantity: Decimal


class ProductIngredientCreate(ProductIngredientBase):
    pass


class ProductIngredientUpdate(OrmBaseModel):
    product_id: int | None = None
    ingredient_id: int | None = None
    quantity: Decimal | None = None


class ProductIngredientRead(ProductIngredientBase):
    id: int
