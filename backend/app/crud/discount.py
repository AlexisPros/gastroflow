from app.crud.base import CRUDBase
from app.models.discount import Discount
from app.schemas.discount import DiscountCreate, DiscountUpdate


discount = CRUDBase[Discount, DiscountCreate, DiscountUpdate](Discount)
