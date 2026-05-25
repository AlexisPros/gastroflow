from app.crud.base import CRUDBase
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


product = CRUDBase[Product, ProductCreate, ProductUpdate](Product)
