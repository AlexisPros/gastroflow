from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.employee_shift_report import EmployeeShiftReport
from app.schemas.employee_shift_report import (
    EmployeeShiftReportCreate,
    EmployeeShiftReportUpdate,
)


class CRUDEmployeeShiftReport(
    CRUDBase[
        EmployeeShiftReport,
        EmployeeShiftReportCreate,
        EmployeeShiftReportUpdate,
    ],
):
    async def get_by_shift(
        self,
        db: AsyncSession,
        *,
        shift_id: int,
    ) -> EmployeeShiftReport | None:
        result = await db.execute(
            select(EmployeeShiftReport).where(
                EmployeeShiftReport.shift_id == shift_id,
            ),
        )
        return result.scalar_one_or_none()

    async def get_multi_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EmployeeShiftReport]:
        result = await db.execute(
            select(EmployeeShiftReport)
            .where(EmployeeShiftReport.user_id == user_id)
            .order_by(EmployeeShiftReport.created_at.desc())
            .offset(skip)
            .limit(limit),
        )
        return list(result.scalars().all())


employee_shift_report = CRUDEmployeeShiftReport(EmployeeShiftReport)
