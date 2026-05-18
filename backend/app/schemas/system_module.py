from app.schemas.base import OrmBaseModel


class SystemModuleBase(OrmBaseModel):
    restaurant_config_id: int
    name: str
    is_enabled: bool = False


class SystemModuleCreate(SystemModuleBase):
    pass


class SystemModuleUpdate(OrmBaseModel):
    restaurant_config_id: int | None = None
    name: str | None = None
    is_enabled: bool | None = None


class SystemModuleRead(SystemModuleBase):
    id: int
