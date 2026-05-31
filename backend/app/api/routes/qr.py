from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import DbSession, raise_bad_request
from app.crud import restaurant_table as crud_restaurant_table
from app.schemas import OrderRead
from app.services import order_service
from app.services.order_service import OrderItemRequest

router = APIRouter(tags=["QR"])


class PublicQRTableRead(BaseModel):
    id: int
    table_number: str
    status: str
    qr_code_url: str | None = None
    is_active: bool


class QROrderItemInput(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)
    notes: str | None = None
    product_modifier_ids: list[int] = Field(default_factory=list)


class CreateQRPendingOrderRequest(BaseModel):
    guest_count: int = Field(gt=0)
    items: list[QROrderItemInput] = Field(min_length=1)


async def get_table_by_qr_token(qr_token: str, db: DbSession):
    table = await crud_restaurant_table.get_by_qr_token(
        db,
        qr_token=qr_token,
    )
    if table is None or not table.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR table not found.",
        )

    return table


@router.get("/qr/{qr_token}/table", response_model=PublicQRTableRead)
async def get_qr_table(qr_token: str, db: DbSession):
    return await get_table_by_qr_token(qr_token, db)


@router.post("/qr/{qr_token}/orders", response_model=OrderRead)
async def create_qr_pending_order(
    qr_token: str,
    body: CreateQRPendingOrderRequest,
    db: DbSession,
):
    table = await get_table_by_qr_token(qr_token, db)

    try:
        return await order_service.create_pending_qr_order(
            db,
            table_id=table.id,
            guest_count=body.guest_count,
            items=[
                OrderItemRequest(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    notes=item.notes,
                    product_modifier_ids=item.product_modifier_ids,
                )
                for item in body.items
            ],
        )
    except ValueError as exc:
        raise_bad_request(exc)
