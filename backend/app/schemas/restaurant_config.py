from datetime import datetime

from app.schemas.base import OrmBaseModel


class RestaurantConfigBase(OrmBaseModel):
    restaurant_name: str
    currency: str = "PLN"


class RestaurantConfigCreate(RestaurantConfigBase):
    pass


class RestaurantConfigUpdate(OrmBaseModel):
    restaurant_name: str | None = None
    currency: str | None = None


class RestaurantConfigRead(RestaurantConfigBase):
    id: int
    created_at: datetime
