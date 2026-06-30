from datetime import date
from fastapi import APIRouter, Query

from app.api.deps import DbSession, RequireAdminManager, raise_bad_request
from app.schemas import DailyOperationsReport, DailyProductionReport, DailySalesReport
from app.schemas.reports import AdvancedSalesReport, WarehouseReport, UserActionLogReport
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


@router.get("/sales/advanced", response_model=AdvancedSalesReport)
async def get_advanced_sales_report(
    db: DbSession,
    period: str = Query(..., description="week, month, quarter, half_year, or year"),
    date_str: str | None = Query(None, alias="date", description="Base date formatted as YYYY-MM-DD"),
    user_id: int | None = Query(None, description="Filter by a specific waiter"),
):
    try:
        return await report_service.build_advanced_sales_report(
            db,
            period=period,
            date_str=date_str,
            user_id=user_id,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.get("/warehouse", response_model=WarehouseReport)
async def get_warehouse_report(
    db: DbSession,
    period: str = Query(..., description="day, week, or month"),
    date_str: str | None = Query(None, alias="date", description="Base date formatted as YYYY-MM-DD"),
    document_type: str | None = Query(None, description="ALL, PZ, MM, RW, etc."),
):
    try:
        return await report_service.build_warehouse_report(
            db,
            document_type=document_type,
            period=period,
            date_str=date_str,
        )
    except ValueError as exc:
        raise_bad_request(exc)


@router.get("/logs", response_model=list[UserActionLogReport])
async def get_user_action_logs(
    db: DbSession,
    date_str: str | None = Query(None, alias="date", description="Log date formatted as YYYY-MM-DD"),
    user_id: int | None = Query(None, description="Filter logs by a specific user"),
):
    try:
        return await report_service.build_user_action_logs(
            db,
            user_id=user_id,
            date_str=date_str,
        )
    except ValueError as exc:
        raise_bad_request(exc)
