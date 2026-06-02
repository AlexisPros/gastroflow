from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession, RequireAdminManager, raise_bad_request
from app.crud import employee_shift_report as crud_employee_shift_report
from app.schemas import (
    EmployeeShiftRead,
    EmployeeShiftReportPreview,
    EmployeeShiftReportRead,
)
from app.services import shift_service

router = APIRouter(tags=["Shifts"])


class StartShiftRequest(BaseModel):
    opening_note: str | None = None


class CloseShiftRequest(BaseModel):
    closing_note: str | None = None


@router.post("/shifts/start", response_model=EmployeeShiftRead)
async def start_shift(
    body: StartShiftRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    return await shift_service.start_shift(
        db,
        user=current_user,
        opening_note=body.opening_note,
    )


@router.get("/shifts/current", response_model=EmployeeShiftRead | None)
async def get_current_shift(current_user: CurrentUser, db: DbSession):
    return await shift_service.get_current_shift(db, user=current_user)


@router.get("/shifts/current/report", response_model=EmployeeShiftReportPreview | None)
async def preview_current_shift_report(current_user: CurrentUser, db: DbSession):
    return await shift_service.preview_current_shift_report(db, user=current_user)


@router.post("/shifts/current/close", response_model=EmployeeShiftReportRead)
async def close_current_shift(
    body: CloseShiftRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    try:
        return await shift_service.close_current_shift(
            db,
            user=current_user,
            closing_note=body.closing_note,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.get(
    "/shift-reports",
    response_model=list[EmployeeShiftReportRead],
    dependencies=[RequireAdminManager],
)
async def list_shift_reports(
    db: DbSession,
    user_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
):
    if user_id is not None:
        return await crud_employee_shift_report.get_multi_by_user(
            db,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )

    return await crud_employee_shift_report.get_multi(db, skip=skip, limit=limit)


@router.get(
    "/shift-reports/{report_id}",
    response_model=EmployeeShiftReportRead,
    dependencies=[RequireAdminManager],
)
async def get_shift_report(report_id: int, db: DbSession):
    report = await crud_employee_shift_report.get(db, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="shift report not found.",
        )

    return report
