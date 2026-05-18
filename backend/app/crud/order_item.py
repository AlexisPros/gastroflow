from app.crud.base import CRUDBase
from app.models.order_item import OrderItem
from app.schemas.order_item import OrderItemCreate, OrderItemUpdate


order_item = CRUDBase[OrderItem, OrderItemCreate, OrderItemUpdate](OrderItem)
