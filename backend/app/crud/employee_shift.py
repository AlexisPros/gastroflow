from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.employee_shift import EmployeeShift
from app.schemas.employee_shift import EmployeeShiftCreate, EmployeeShiftUpdate


class CRUDEmployeeShift(
    CRUDBase[EmployeeShift, EmployeeShiftCreate, EmployeeShiftUpdate],
):
    async def get_open_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
    ) -> EmployeeShift | None:
        result = await db.execute(
            select(EmployeeShift).where(
                EmployeeShift.user_id == user_id,
                EmployeeShift.status == "OPEN",
            ),
        )
        return result.scalar_one_or_none()

    async def close(
        self,
        db: AsyncSession,
        *,
        db_obj: EmployeeShift,
        closing_note: str | None = None,
    ) -> EmployeeShift:
        db_obj.status = "CLOSED"
        db_obj.ended_at = datetime.now(timezone.utc)
        db_obj.closing_note = closing_note

        db.add(db_obj)
        await db.flush()
        return db_obj


employee_shift = CRUDEmployeeShift(EmployeeShift)
