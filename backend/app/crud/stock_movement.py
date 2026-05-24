from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.stock_item import StockItem
from app.models.stock_movement import StockMovement
from app.schemas.stock_movement import StockMovementCreate, StockMovementUpdate


class CRUDStockMovement(CRUDBase[StockMovement, StockMovementCreate, StockMovementUpdate]):
    async def record(
        self,
        db: AsyncSession,
        *,
        stock_item_id: int,
        type: str,
        quantity: Decimal,
        description: str | None = None,
    ) -> StockMovement:
        db_obj = StockMovement(
            stock_item_id=stock_item_id,
            type=type,
            quantity=quantity,
            description=description,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def record_and_apply(
        self,
        db: AsyncSession,
        *,
        stock_item: StockItem,
        type: str,
        quantity_delta: Decimal,
        description: str | None = None,
        prevent_negative: bool = True,
    ) -> StockMovement:
        quantity_delta_decimal = Decimal(str(quantity_delta))
        new_quantity = stock_item.quantity + quantity_delta_decimal

        if prevent_negative and new_quantity < 0:
            raise ValueError("Stock quantity cannot be negative.")

        stock_item.quantity = new_quantity

        db_obj = StockMovement(
            stock_item_id=stock_item.id,
            type=type,
            quantity=abs(quantity_delta_decimal),
            description=description,
        )

        db.add(stock_item)
        db.add(db_obj)
        await db.commit()
        await db.refresh(stock_item)
        await db.refresh(db_obj)
        return db_obj


stock_movement = CRUDStockMovement(StockMovement)
