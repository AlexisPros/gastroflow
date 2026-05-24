from app.crud.base import CRUDBase
from app.models.modifier import Modifier
from app.schemas.modifier import ModifierCreate, ModifierUpdate


modifier = CRUDBase[Modifier, ModifierCreate, ModifierUpdate](Modifier)
