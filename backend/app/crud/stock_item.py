from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.stock_item import StockItem
from app.schemas.stock_item import StockItemCreate, StockItemUpdate


class CRUDStockItem(CRUDBase[StockItem, StockItemCreate, StockItemUpdate]):
    async def get_by_warehouse_and_ingredient(
        self,
        db: AsyncSession,
        *,
        warehouse_id: int,
        ingredient_id: int,
    ) -> StockItem | None:
        result = await db.execute(
            select(StockItem).where(
                StockItem.warehouse_id == warehouse_id,
                StockItem.ingredient_id == ingredient_id,
            ),
        )
        return result.scalar_one_or_none()


stock_item = CRUDStockItem(StockItem)
