from app.crud.base import CRUDBase
from app.models.product_modifier import ProductModifier
from app.schemas.product_modifier import ProductModifierCreate, ProductModifierUpdate


product_modifier = CRUDBase[
    ProductModifier,
    ProductModifierCreate,
    ProductModifierUpdate,
](ProductModifier)
