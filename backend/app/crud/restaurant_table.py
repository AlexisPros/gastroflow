from app.crud.base import CRUDBase
from app.models.restaurant_table import RestaurantTable
from app.schemas.restaurant_table import RestaurantTableCreate, RestaurantTableUpdate


restaurant_table = CRUDBase[
    RestaurantTable,
    RestaurantTableCreate,
    RestaurantTableUpdate,
](RestaurantTable)
