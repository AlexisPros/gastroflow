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
    step_name: str | None = None
    step_description: str | None = None


class KitchenOrderItemRead(OrmBaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    notes: str | None = None
    course_number: int
    status: str
    created_at: datetime
    kitchen_tasks: list[KitchenTaskRead]


class KitchenOrderRead(OrmBaseModel):
    id: int
    table_id: int | None = None
    table_number: str | None = None
    waiter_name: str | None = None
    created_at: datetime
    status: str
    estimated_time: int | None = None
    items: list[KitchenOrderItemRead]


class KitchenSectionTaskRead(OrmBaseModel):
    id: int
    order_id: int
    order_item_id: int
    kitchen_section_id: int
    order_created_at: datetime
    item_created_at: datetime
    order_estimated_time: int | None = None
    table_number: str | None = None
    product_name: str
    quantity: int
    notes: str | None = None
    course_number: int
    status: str
    estimated_time: int | None = None
    step_name: str | None = None
    step_description: str | None = None
    step_sequence: int | None = None
    depends_on_sequence: int | None = None
    can_start: bool = False
    blocked_by_step_name: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
