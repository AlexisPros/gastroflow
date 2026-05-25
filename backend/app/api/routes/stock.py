from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DbSession, get_or_404, raise_bad_request
from app.crud import order_item as crud_order_item
from app.crud import stock_item as crud_stock_item
from app.schemas import StockMovementRead
from app.schemas.stock_item import StockItemRead
from app.services import stock_service

router = APIRouter(tags=["Stock"])


class ApplyStockMovementRequest(BaseModel):
    type: str
    quantity_delta: Decimal
    description: str | None = None
    prevent_negative: bool = True


class ConsumeOrderItemStockRequest(BaseModel):
    warehouse_id: int


@router.get(
    "/stock-items/by-warehouse-and-ingredient",
    response_model=StockItemRead,
)
async def get_stock_item_by_warehouse_and_ingredient(
    warehouse_id: int,
    ingredient_id: int,
    db: DbSession,
):
    stock_item = await crud_stock_item.get_by_warehouse_and_ingredient(
        db,
        warehouse_id=warehouse_id,
        ingredient_id=ingredient_id,
    )
    if stock_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="stock item not found.",
        )

    return stock_item


@router.post(
    "/stock-items/{stock_item_id}/movements/apply",
    response_model=StockMovementRead,
)
async def apply_stock_movement(
    stock_item_id: int,
    body: ApplyStockMovementRequest,
    db: DbSession,
):
    stock_item = await get_or_404(
        crud_obj=crud_stock_item,
        db=db,
        id=stock_item_id,
        entity_name="stock item",
    )
    try:
        return await stock_service.apply_movement(
            db,
            stock_item=stock_item,
            type=body.type,
            quantity_delta=body.quantity_delta,
            description=body.description,
            prevent_negative=body.prevent_negative,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post(
    "/order-items/{order_item_id}/consume-stock",
    response_model=list[StockMovementRead],
)
async def consume_stock_for_order_item(
    order_item_id: int,
    body: ConsumeOrderItemStockRequest,
    db: DbSession,
):
    order_item = await get_or_404(
        crud_obj=crud_order_item,
        db=db,
        id=order_item_id,
        entity_name="order item",
    )
    try:
        return await stock_service.consume_ingredients_for_order_item(
            db,
            order_item=order_item,
            warehouse_id=body.warehouse_id,
        )
    except ValueError as exc:
        raise_bad_request(exc)
