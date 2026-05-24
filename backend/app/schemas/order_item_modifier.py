from app.schemas.base import OrmBaseModel
from decimal import Decimal

class OrderItemModifierBase(OrmBaseModel):
    order_item_id: int
    product_modifier_id: int
    price: Decimal = Decimal("0.00")


class OrderItemModifierCreate(OrderItemModifierBase):
    pass


class OrderItemModifierUpdate(OrmBaseModel):
    order_item_id: int | None = None
    product_modifier_id: int | None = None
    price: Decimal | None = None

 
class OrderItemModifierRead(OrderItemModifierBase):
    id: int
