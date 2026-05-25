from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
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

    async def find_table_reservations(
        self,
        db: AsyncSession,
        *,
        table_id: int,
        reservation_time: datetime,
    ) -> list[Reservation]:
        result = await db.execute(
            select(Reservation).where(
                Reservation.table_id == table_id,
                Reservation.reservation_time == reservation_time,
                Reservation.status != "CANCELLED",
            ),
        )
        return list(result.scalars().all())


reservation_service = ReservationService()
