from app.schemas.base import OrmBaseModel


class ProductKitchenStepBase(OrmBaseModel):
    product_id: int
    kitchen_section_id: int
    name: str
    description: str | None = None
    sequence: int = 1
    estimated_time: int | None = None
    is_active: bool = True


class ProductKitchenStepCreate(ProductKitchenStepBase):
    pass


class ProductKitchenStepUpdate(OrmBaseModel):
    product_id: int | None = None
    kitchen_section_id: int | None = None
    name: str | None = None
    description: str | None = None
    sequence: int | None = None
    estimated_time: int | None = None
    is_active: bool | None = None


class ProductKitchenStepRead(ProductKitchenStepBase):
    id: int
