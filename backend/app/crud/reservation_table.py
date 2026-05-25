from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.reservation_table import ReservationTable
from app.schemas.reservation_table import ReservationTableCreate, ReservationTableUpdate


class CRUDReservationTable(
    CRUDBase[ReservationTable, ReservationTableCreate, ReservationTableUpdate],
):
    async def get_by_reservation(
        self,
        db: AsyncSession,
        *,
        reservation_id: int,
    ) -> list[ReservationTable]:
        result = await db.execute(
            select(ReservationTable).where(
                ReservationTable.reservation_id == reservation_id,
            ),
        )
        return list(result.scalars().all())

    async def delete_by_reservation(
        self,
        db: AsyncSession,
        *,
        reservation_id: int,
    ) -> None:
        reservation_tables = await self.get_by_reservation(
            db,
            reservation_id=reservation_id,
        )
        for reservation_table in reservation_tables:
            await db.delete(reservation_table)

        await db.commit()


reservation_table = CRUDReservationTable(ReservationTable)
