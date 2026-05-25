from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_item import OrderItem
from app.models.product_ingredient import ProductIngredient
from app.models.stock_item import StockItem
from app.models.stock_movement import StockMovement


StockConsumption = tuple[StockItem, Decimal, Decimal]


class StockService:
    async def apply_movement(
        self,
        db: AsyncSession,
        *,
        stock_item: StockItem,
        type: str,
        quantity_delta: Decimal,
        description: str | None = None,
        prevent_negative: bool = True,
    ) -> StockMovement:
        new_quantity = stock_item.quantity + quantity_delta
        if prevent_negative and new_quantity < 0:
            raise ValueError("Stock quantity cannot be negative.")

        stock_item.quantity = new_quantity
        movement = StockMovement(
            stock_item_id=stock_item.id,
            type=type,
            quantity=abs(quantity_delta),
            description=description,
        )

        db.add(stock_item)
        db.add(movement)
        await db.commit()
        await db.refresh(stock_item)
        await db.refresh(movement)
        return movement

    async def consume_ingredients_for_order_item(
        self,
        db: AsyncSession,
        *,
        order_item: OrderItem,
        warehouse_id: int,
    ) -> list[StockMovement]:
        ingredients = await self._get_product_ingredients(
            db,
            product_id=order_item.product_id,
        )
        consumptions: list[StockConsumption] = []
        movements: list[StockMovement] = []

        for product_ingredient in ingredients:
            stock_item = await self._get_stock_item(
                db,
                warehouse_id=warehouse_id,
                ingredient_id=product_ingredient.ingredient_id,
            )
            quantity_delta = -(product_ingredient.quantity * order_item.quantity)

            new_quantity = stock_item.quantity + quantity_delta
            if new_quantity < 0:
                raise ValueError("Not enough stock to consume ingredient.")

            consumptions.append((stock_item, quantity_delta, new_quantity))

        for stock_item, quantity_delta, new_quantity in consumptions:
            stock_item.quantity = new_quantity
            movement = StockMovement(
                stock_item_id=stock_item.id,
                type="CONSUMPTION",
                quantity=abs(quantity_delta),
                description=f"Order item #{order_item.id}",
            )

            db.add(stock_item)
            db.add(movement)
            movements.append(movement)

        await db.commit()

        for movement in movements:
            await db.refresh(movement)

        return movements

    async def _get_product_ingredients(
        self,
        db: AsyncSession,
        *,
        product_id: int,
    ) -> list[ProductIngredient]:
        result = await db.execute(
            select(ProductIngredient).where(ProductIngredient.product_id == product_id),
        )
        return list(result.scalars().all())

    async def _get_stock_item(
        self,
        db: AsyncSession,
        *,
        warehouse_id: int,
        ingredient_id: int,
    ) -> StockItem:
        result = await db.execute(
            select(StockItem).where(
                StockItem.warehouse_id == warehouse_id,
                StockItem.ingredient_id == ingredient_id,
            ),
        )
        stock_item = result.scalar_one_or_none()

        if stock_item is None:
            raise ValueError("Stock item does not exist for this warehouse.")

        return stock_item


stock_service = StockService()
