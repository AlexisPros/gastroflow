from datetime import datetime

from app.schemas.base import OrmBaseModel


class KitchenTaskBase(OrmBaseModel):
    order_item_id: int
    kitchen_section_id: int
    product_kitchen_step_id: int | None = None
    assigned_user_id: int | None = None
    estimated_time: int | None = None


class KitchenTaskCreate(KitchenTaskBase):
    pass


class KitchenTaskUpdate(OrmBaseModel):
    order_item_id: int | None = None
    kitchen_section_id: int | None = None
    product_kitchen_step_id: int | None = None
    assigned_user_id: int | None = None
    status: str | None = None
    estimated_time: int | None = None


class KitchenTaskRead(KitchenTaskBase):
    id: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
