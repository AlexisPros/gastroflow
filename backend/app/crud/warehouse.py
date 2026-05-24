from app.crud.base import CRUDBase
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate


warehouse = CRUDBase[Warehouse, WarehouseCreate, WarehouseUpdate](Warehouse)
