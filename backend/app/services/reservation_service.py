from datetime import datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
from app.models.reservation_table import ReservationTable
from app.models.restaurant_table import RestaurantTable


class ReservationService:
    async def confirm(self, db: AsyncSession, *, reservation: Reservation) -> Reservation:
        reservation.status = "CONFIRMED"

        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)
        return reservation

    async def cancel(self, db: AsyncSession, *, reservation: Reservation) -> Reservation:
        reservation.status = "CANCELLED"

        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)
        return reservation

    async def seat_guests(
        self,
        db: AsyncSession,
        *,
        reservation: Reservation,
        table: RestaurantTable,
    ) -> Reservation:
        if reservation.table_id != table.id:
            raise ValueError("Reservation does not belong to this table.")

        reservation.status = "SEATED"
        table.status = "OCCUPIED"
        table.current_guests = reservation.guest_count

        db.add(reservation)
        db.add(table)
        await db.commit()
        await db.refresh(reservation)
        await db.refresh(table)
        return reservation

    async def assign_tables(
        self,
        db: AsyncSession,
        *,
        reservation: Reservation,
        table_ids: list[int],
    ) -> Reservation:
        if not table_ids:
            raise ValueError("Reservation must have at least one table.")

        if len(table_ids) != len(set(table_ids)):
            raise ValueError("Reservation tables must be unique.")

        reservation.table_id = table_ids[0]

        await db.execute(
            delete(ReservationTable).where(
                ReservationTable.reservation_id == reservation.id,
            )
        )

        for table_id in table_ids:
            db.add(
                ReservationTable(
                    reservation_id=reservation.id,
                    table_id=table_id,
                ),
            )

        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)
        return reservation

    async def seat_guests_at_tables(
        self,
        db: AsyncSession,
        *,
        reservation: Reservation,
        tables: list[RestaurantTable],
    ) -> Reservation:
        if not tables:
            raise ValueError("Reservation must have at least one table.")

        result = await db.execute(
            select(ReservationTable.table_id).where(
                ReservationTable.reservation_id == reservation.id,
            ),
        )
        reservation_table_ids = set(result.scalars().all())

        if reservation_table_ids:
            selected_table_ids = {table.id for table in tables}
            if selected_table_ids != reservation_table_ids:
                raise ValueError("Selected tables do not match this reservation.")
        elif reservation.table_id not in {table.id for table in tables}:
            raise ValueError("Selected tables do not match this reservation.")

        reservation.status = "SEATED"
        reservation.table_id = tables[0].id

        for index, table in enumerate(tables):
            table.status = "OCCUPIED"
            table.current_guests = reservation.guest_count if index == 0 else 0
            db.add(table)

        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)
        return reservation

    async def find_table_reservations(
        self,
        db: AsyncSession,
        *,
        table_id: int,
        reservation_time: datetime,
    ) -> list[Reservation]:
        result = await db.execute(
            select(Reservation)
            .outerjoin(
                ReservationTable,
                ReservationTable.reservation_id == Reservation.id,
            )
            .where(
                or_(
                    Reservation.table_id == table_id,
                    ReservationTable.table_id == table_id,
                ),
                Reservation.reservation_time == reservation_time,
                Reservation.status != "CANCELLED",
            )
        )
        return list(result.scalars().unique().all())

    async def find_reservations_for_any_table(
        self,
        db: AsyncSession,
        *,
        table_ids: list[int],
        reservation_time: datetime,
    ) -> list[Reservation]:
        result = await db.execute(
            select(Reservation)
            .outerjoin(
                ReservationTable,
                ReservationTable.reservation_id == Reservation.id,
            )
            .where(
                or_(
                    Reservation.table_id.in_(table_ids),
                    ReservationTable.table_id.in_(table_ids),
                ),
                Reservation.reservation_time == reservation_time,
                Reservation.status != "CANCELLED",
            ),
        )
        return list(result.scalars().unique().all())


reservation_service = ReservationService()
