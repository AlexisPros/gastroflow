from fastapi import APIRouter, status

from app.api.deps import DbSession, RequireOrderRole, get_or_404, raise_bad_request
from app.crud import order as crud_order
from app.schemas import (
    BillSegmentRead,
    BillSplitFinalizeRequest,
    BillSplitMoveItemsRequest,
    BillSplitSplitItemRequest,
    BillSplitViewRead,
    OrderRead,
)
from app.services import bill_split_service

router = APIRouter(
    tags=["Bill split"],
    dependencies=[RequireOrderRole],
)


@router.get("/orders/{order_id}/bill-split", response_model=BillSplitViewRead)
async def get_bill_split(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await bill_split_service.get_view(db, order=order)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post(
    "/orders/{order_id}/bill-split/segments",
    response_model=BillSegmentRead,
)
async def create_bill_segment(order_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        segment = await bill_split_service.create_segment(db, order=order)
        view = await bill_split_service.get_view(db, order=order)
    except ValueError as exc:
        raise_bad_request(exc)

    return next(item for item in view.segments if item.id == segment.id)


@router.post(
    "/orders/{order_id}/bill-split/move-items",
    response_model=BillSplitViewRead,
)
async def move_bill_split_items(
    order_id: int,
    body: BillSplitMoveItemsRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await bill_split_service.move_items(
            db,
            order=order,
            target_segment_id=body.target_segment_id,
            items=body.items,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post(
    "/orders/{order_id}/bill-split/split-item",
    response_model=BillSplitViewRead,
)
async def split_bill_item(
    order_id: int,
    body: BillSplitSplitItemRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await bill_split_service.split_item(
            db,
            order=order,
            order_item_id=body.order_item_id,
            target_segment_ids=body.target_segment_ids,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.delete(
    "/orders/{order_id}/bill-split/segments/{segment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_bill_segment(order_id: int, segment_id: int, db: DbSession):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        await bill_split_service.delete_segment(
            db,
            order=order,
            segment_id=segment_id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post(
    "/orders/{order_id}/bill-split/finalize",
    response_model=list[OrderRead],
)
async def finalize_bill_split(
    order_id: int,
    body: BillSplitFinalizeRequest,
    db: DbSession,
):
    order = await get_or_404(
        crud_obj=crud_order,
        db=db,
        id=order_id,
        entity_name="order",
    )
    try:
        return await bill_split_service.finalize(
            db,
            order=order,
            segment_guest_counts={
                item.segment_id: item.guest_count
                for item in body.segment_guest_counts
            },
        )
    except ValueError as exc:
        raise_bad_request(exc)
