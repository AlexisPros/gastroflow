from fastapi import APIRouter

from app.api.routes import (
    auth,
    bill_split,
    fiscal,
    floor_plans,
    invoices,
    kitchen,
    orders,
    payments,
    qr,
    reservations,
    reports,
    resources,
    shifts,
    stock,
    websockets,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(orders.router)
api_router.include_router(bill_split.router)
api_router.include_router(kitchen.router)
api_router.include_router(payments.router)
api_router.include_router(qr.router)
api_router.include_router(shifts.router)
api_router.include_router(stock.router)
api_router.include_router(reservations.router)
api_router.include_router(reports.router)
api_router.include_router(floor_plans.router)
api_router.include_router(invoices.router)
api_router.include_router(fiscal.router)
api_router.include_router(resources.router)
api_router.include_router(websockets.router)
