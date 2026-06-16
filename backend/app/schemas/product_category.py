from app.schemas.base import OrmBaseModel


class ProductCategoryBase(OrmBaseModel):
    parent_category_id: int | None = None
    name: str
    department: str = "KITCHEN"
    is_active: bool = True


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryUpdate(OrmBaseModel):
    parent_category_id: int | None = None
    name: str | None = None
    department: str | None = None
    is_active: bool | None = None


class ProductCategoryRead(ProductCategoryBase):
    id: int
