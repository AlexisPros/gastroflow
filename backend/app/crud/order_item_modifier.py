from app.crud.base import CRUDBase
from app.models.order_item_modifier import OrderItemModifier
from app.schemas.order_item_modifier import (
    OrderItemModifierCreate,
    OrderItemModifierUpdate,
)


order_item_modifier = CRUDBase[
    OrderItemModifier,
    OrderItemModifierCreate,
    OrderItemModifierUpdate,
](OrderItemModifier)
