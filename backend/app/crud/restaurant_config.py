from app.crud.base import CRUDBase
from app.models.restaurant_config import RestaurantConfig
from app.schemas.restaurant_config import RestaurantConfigCreate, RestaurantConfigUpdate


restaurant_config = CRUDBase[
    RestaurantConfig,
    RestaurantConfigCreate,
    RestaurantConfigUpdate,
](RestaurantConfig)
