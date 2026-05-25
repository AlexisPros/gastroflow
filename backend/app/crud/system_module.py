from app.crud.base import CRUDBase
from app.models.system_module import SystemModule
from app.schemas.system_module import SystemModuleCreate, SystemModuleUpdate


system_module = CRUDBase[SystemModule, SystemModuleCreate, SystemModuleUpdate](
    SystemModule,
)
