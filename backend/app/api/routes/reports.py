from datetime import date

from fastapi import APIRouter

from app.api.deps import DbSession, RequireAdminManager, raise_bad_request
from app.schemas import DailyOperationsReport, DailyProductionReport, DailySalesReport
from app.services import report_service

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[RequireAdminManager],
)


@router.get("/sales/daily", response_model=DailySalesReport)
async def get_daily_sales_report(
    db: DbSession,
    report_date: date | None = None,
):
    return await report_service.build_daily_sales_report(
        db,
        report_date=report_date,
    )


@router.get("/kitchen/daily", response_model=DailyProductionReport)
async def get_daily_kitchen_report(
    db: DbSession,
    report_date: date | None = None,
):
    return await report_service.build_daily_production_report(
        db,
        report_date=report_date,
        scope="KITCHEN",
    )


@router.get("/bar/daily", response_model=DailyProductionReport)
async def get_daily_bar_report(
    db: DbSession,
    report_date: date | None = None,
):
    return await report_service.build_daily_production_report(
        db,
        report_date=report_date,
        scope="BAR",
    )


@router.get("/operations/daily", response_model=DailyOperationsReport)
async def get_daily_operations_report(
    db: DbSession,
    report_date: date | None = None,
):
    try:
        return await report_service.build_daily_operations_report(
            db,
            report_date=report_date,
        )
    except ValueError as exc:
        raise_bad_request(exc)
