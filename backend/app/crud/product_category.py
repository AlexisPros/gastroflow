from app.crud.base import CRUDBase
from app.models.product_category import ProductCategory
from app.schemas.product_category import ProductCategoryCreate, ProductCategoryUpdate


product_category = CRUDBase[
    ProductCategory,
    ProductCategoryCreate,
    ProductCategoryUpdate,
](ProductCategory)
