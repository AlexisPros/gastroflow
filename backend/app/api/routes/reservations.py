from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, RequireStaffRole, raise_bad_request, raise_forbidden
from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.reservation import Reservation
from app.crud import reservation as crud_reservation
from app.crud import reservation_table as crud_reservation_table
from app.crud import restaurant_table as crud_restaurant_table
from app.schemas.reservation_table import ReservationTableRead
from app.schemas.order import OrderRead
from app.schemas.reservation import (
    ReservationCreate,
    ReservationItemRead,
    ReservationPaymentRead,
    ReservationRead,
    ReservationTableSummary,
    ReservationUpdate,
)
from app.services import reservation_service

router = APIRouter(tags=["Reservations"], dependencies=[RequireStaffRole])


class ReservationTablesRequest(BaseModel):
    table_ids: list[int] = Field(min_length=1)


def to_read(reservation: Reservation) -> ReservationRead:
    return ReservationRead(
        id=reservation.id,
        table_id=reservation.table_id,
        customer_name=reservation.customer_name,
        customer_phone=reservation.customer_phone,
        customer_email=reservation.__dict__.get("customer_email"),
        invoice_nip=reservation.__dict__.get("invoice_nip"),
        guest_count=reservation.guest_count,
        reservation_time=reservation.reservation_time,
        duration_minutes=reservation.__dict__.get("duration_minutes") or 120,
        status=reservation.status,
        notes=reservation.notes,
        total_amount=reservation.__dict__.get("total_amount") or 0,
        prepaid_amount=reservation.__dict__.get("prepaid_amount") or 0,
        payment_status=reservation.__dict__.get("payment_status") or "UNPAID",
        created_by_user_id=reservation.__dict__.get("created_by_user_id"),
        started_order_id=reservation.__dict__.get("started_order_id"),
        started_at=reservation.__dict__.get("started_at"),
        created_at=reservation.created_at,
        tables=[
            ReservationTableSummary(id=link.table.id, table_number=link.table.table_number)
            for link in reservation.__dict__.get("reservation_tables", [])
        ] or (
            [
                ReservationTableSummary(
                    id=reservation.table.id,
                    table_number=reservation.table.table_number,
                )
            ]
            if reservation.__dict__.get("table") is not None
            else []
        ),
        items=[
            ReservationItemRead(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price,
                notes=item.notes,
            )
            for item in reservation.__dict__.get("items", [])
        ],
        payments=[
            ReservationPaymentRead.model_validate(payment)
            for payment in reservation.__dict__.get("payments", [])
        ],
    )


async def get_reservation(db: DbSession, reservation_id: int) -> Reservation:
    reservation = await reservation_service.get(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found.")
    return reservation


@router.get("/reservations", response_model=list[ReservationRead])
async def list_reservations(db: DbSession):
    return [to_read(item) for item in await reservation_service.list(db)]


@router.get("/reservations/menu")
async def reservation_menu(db: DbSession):
    rows = await db.execute(
        select(Product, ProductCategory)
        .join(ProductCategory, Product.category_id == ProductCategory.id)
        .where(Product.is_active.is_(True), ProductCategory.is_active.is_(True))
        .order_by(ProductCategory.name, Product.name)
    )
    return [
        {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "image_url": product.image_url,
            "category_id": category.id,
            "category_name": category.name,
            "department": category.department,
        }
        for product, category in rows.all()
    ]


@router.get("/reservations/{reservation_id:int}", response_model=ReservationRead)
async def read_reservation(reservation_id: int, db: DbSession):
    return to_read(await get_reservation(db, reservation_id))


@router.post("/reservations", response_model=ReservationRead, status_code=201)
async def create_reservation(body: ReservationCreate, db: DbSession, current_user: CurrentUser):
    try:
        reservation = await reservation_service.create(
            db, data=body, user_id=current_user.id, user_role=current_user.role
        )
        return to_read(reservation)
    except PermissionError as exc:
        raise_forbidden(exc)
    except ValueError as exc:
        raise_bad_request(exc)


@router.patch("/reservations/{reservation_id:int}", response_model=ReservationRead)
async def update_reservation(
    reservation_id: int,
    body: ReservationUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    reservation = await get_reservation(db, reservation_id)
    try:
        return to_read(
            await reservation_service.update(
                db, reservation=reservation, data=body, user_role=current_user.role
            )
        )
    except PermissionError as exc:
        raise_forbidden(exc)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/reservations/{reservation_id:int}/cancel", response_model=ReservationRead)
async def cancel_reservation(reservation_id: int, db: DbSession, current_user: CurrentUser):
    reservation = await get_reservation(db, reservation_id)
    try:
        return to_read(
            await reservation_service.cancel(db, reservation=reservation, user_role=current_user.role)
        )
    except PermissionError as exc:
        raise_forbidden(exc)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/reservations/{reservation_id:int}/start", response_model=OrderRead)
async def start_reservation(reservation_id: int, db: DbSession, current_user: CurrentUser):
    reservation = await get_reservation(db, reservation_id)
    try:
        return await reservation_service.start(
            db,
            reservation=reservation,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except PermissionError as exc:
        raise_forbidden(exc)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/reservations/{reservation_id:int}/complete-prepaid", response_model=OrderRead)
async def complete_prepaid_reservation(
    reservation_id: int, db: DbSession, current_user: CurrentUser
):
    reservation = await get_reservation(db, reservation_id)
    try:
        return await reservation_service.complete_prepaid(
            db,
            reservation=reservation,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except PermissionError as exc:
        raise_forbidden(exc)
    except ValueError as exc:
        raise_bad_request(exc)


@router.post("/reservations/sync-table-statuses")
async def sync_reservation_table_statuses(db: DbSession):
    await reservation_service.sync_table_statuses(db)
    return {"synced": True}


# Compatibility endpoints retained for existing clients while the richer flow uses PATCH/start.
@router.post("/reservations/{reservation_id:int}/confirm", response_model=ReservationRead)
async def confirm_reservation(reservation_id: int, db: DbSession, current_user: CurrentUser):
    if current_user.role not in {"ADMIN", "MANAGER", "WAITER"}:
        raise_forbidden(PermissionError("Only service staff can confirm reservations."))
    reservation = await crud_reservation.get(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found.")
    return to_read(await reservation_service.confirm(db, reservation=reservation))


@router.post("/reservations/{reservation_id:int}/tables", response_model=ReservationRead)
async def assign_reservation_tables(
    reservation_id: int, body: ReservationTablesRequest, db: DbSession, current_user: CurrentUser
):
    if current_user.role not in {"ADMIN", "MANAGER", "WAITER"}:
        raise_forbidden(PermissionError("Only service staff can change reservation tables."))
    reservation = await crud_reservation.get(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found.")
    for table_id in body.table_ids:
        if await crud_restaurant_table.get(db, table_id) is None:
            raise HTTPException(status_code=404, detail="Restaurant table not found.")
    return to_read(
        await reservation_service.assign_tables(db, reservation=reservation, table_ids=body.table_ids)
    )


@router.get("/reservations/{reservation_id:int}/tables", response_model=list[ReservationTableRead])
async def list_reservation_tables(reservation_id: int, db: DbSession):
    if await crud_reservation.get(db, reservation_id) is None:
        raise HTTPException(status_code=404, detail="Reservation not found.")
    return await crud_reservation_table.get_by_reservation(db, reservation_id=reservation_id)


@router.get("/reservations/search/by-table", response_model=list[ReservationRead])
async def find_reservations_by_table(table_id: int, reservation_time: datetime, db: DbSession):
    rows = await reservation_service.find_table_reservations(
        db, table_id=table_id, reservation_time=reservation_time
    )
    return [to_read(row) for row in rows]
