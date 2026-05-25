from app.crud.base import CRUDBase
from app.models.ingredient import Ingredient
from app.schemas.ingredient import IngredientCreate, IngredientUpdate


ingredient = CRUDBase[Ingredient, IngredientCreate, IngredientUpdate](Ingredient)
