from datetime import datetime

from app.schemas.base import OrmBaseModel


class KitchenTaskBase(OrmBaseModel):
    order_item_id: int
    kitchen_section_id: int
    assigned_user_id: int | None = None
    status: str = "NEW"
    estimated_time: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class KitchenTaskCreate(KitchenTaskBase):
    pass


class KitchenTaskUpdate(OrmBaseModel):
    order_item_id: int | None = None
    kitchen_section_id: int | None = None
    assigned_user_id: int | None = None
    status: str | None = None
    estimated_time: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class KitchenTaskRead(KitchenTaskBase):
    id: int
