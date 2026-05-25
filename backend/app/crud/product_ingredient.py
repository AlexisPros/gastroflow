from app.crud.base import CRUDBase
from app.models.product_ingredient import ProductIngredient
from app.schemas.product_ingredient import ProductIngredientCreate, ProductIngredientUpdate


product_ingredient = CRUDBase[
    ProductIngredient,
    ProductIngredientCreate,
    ProductIngredientUpdate,
](ProductIngredient)
