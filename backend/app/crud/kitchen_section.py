from app.crud.base import CRUDBase
from app.models.kitchen_section import KitchenSection
from app.schemas.kitchen_section import KitchenSectionCreate, KitchenSectionUpdate


kitchen_section = CRUDBase[
    KitchenSection,
    KitchenSectionCreate,
    KitchenSectionUpdate,
](KitchenSection)
