from app.schemas.base import OrmBaseModel


class OrderItemModifierBase(OrmBaseModel):
    order_item_id: int
    product_modifier_id: int
    price: float = 0


class OrderItemModifierCreate(OrderItemModifierBase):
    pass


class OrderItemModifierUpdate(OrmBaseModel):
    order_item_id: int | None = None
    product_modifier_id: int | None = None
    price: float | None = None


class OrderItemModifierRead(OrderItemModifierBase):
    id: int
