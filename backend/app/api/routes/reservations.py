from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import DbSession, get_or_404, raise_bad_request, require_roles
from app.crud import reservation as crud_reservation
from app.crud import reservation_table as crud_reservation_table
from app.crud import restaurant_table as crud_restaurant_table
from app.schemas import ReservationRead, ReservationTableRead
from app.services import reservation_service

RESERVATION_ROLES = {"ADMIN", "MANAGER", "WAITER"}

router = APIRouter(
    tags=["Reservations"],
    dependencies=[Depends(require_roles(RESERVATION_ROLES))],
)


class SeatReservationRequest(BaseModel):
    table_id: int


class ReservationTablesRequest(BaseModel):
    table_ids: list[int] = Field(min_length=1)


class ReservationTablesSearchRequest(BaseModel):
    table_ids: list[int] = Field(min_length=1)
    reservation_time: datetime


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationRead)
async def confirm_reservation(reservation_id: int, db: DbSession):
    reservation = await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    return await reservation_service.confirm(db, reservation=reservation)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead)
async def cancel_reservation(reservation_id: int, db: DbSession):
    reservation = await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    return await reservation_service.cancel(db, reservation=reservation)


@router.post("/reservations/{reservation_id}/seat", response_model=ReservationRead)
async def seat_reservation(
    reservation_id: int,
    body: SeatReservationRequest,
    db: DbSession,
):
    reservation = await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    table = await get_or_404(
        crud_obj=crud_restaurant_table,
        db=db,
        id=body.table_id,
        entity_name="restaurant table",
    )
    try:
        return await reservation_service.seat_guests(
            db,
            reservation=reservation,
            table=table,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/reservations/{reservation_id}/tables", response_model=ReservationRead)
async def assign_reservation_tables(
    reservation_id: int,
    body: ReservationTablesRequest,
    db: DbSession,
):
    reservation = await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    for table_id in body.table_ids:
        await get_or_404(
            crud_obj=crud_restaurant_table,
            db=db,
            id=table_id,
            entity_name="restaurant table",
        )

    try:
        return await reservation_service.assign_tables(
            db,
            reservation=reservation,
            table_ids=body.table_ids,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.get(
    "/reservations/{reservation_id}/tables",
    response_model=list[ReservationTableRead],
)
async def list_reservation_tables(reservation_id: int, db: DbSession):
    await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    return await crud_reservation_table.get_by_reservation(
        db,
        reservation_id=reservation_id,
    )


@router.delete("/reservations/{reservation_id}/tables")
async def clear_reservation_tables(reservation_id: int, db: DbSession):
    await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    await crud_reservation_table.delete_by_reservation(
        db,
        reservation_id=reservation_id,
    )
    return {"deleted": True}


@router.post("/reservations/{reservation_id}/seat-tables", response_model=ReservationRead)
async def seat_reservation_at_tables(
    reservation_id: int,
    body: ReservationTablesRequest,
    db: DbSession,
):
    reservation = await get_or_404(
        crud_obj=crud_reservation,
        db=db,
        id=reservation_id,
        entity_name="reservation",
    )
    tables = [
        await get_or_404(
            crud_obj=crud_restaurant_table,
            db=db,
            id=table_id,
            entity_name="restaurant table",
        )
        for table_id in body.table_ids
    ]
    try:
        return await reservation_service.seat_guests_at_tables(
            db,
            reservation=reservation,
            tables=tables,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.get("/reservations/search/by-table", response_model=list[ReservationRead])
async def find_reservations_by_table(
    table_id: int,
    reservation_time: datetime,
    db: DbSession,
):
    return await reservation_service.find_table_reservations(
        db,
        table_id=table_id,
        reservation_time=reservation_time,
    )


@router.post("/reservations/search/by-tables", response_model=list[ReservationRead])
async def find_reservations_by_tables(
    body: ReservationTablesSearchRequest,
    db: DbSession,
):
    return await reservation_service.find_reservations_for_any_table(
        db,
        table_ids=body.table_ids,
        reservation_time=body.reservation_time,
    )
