import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm.exc import StaleDataError

from app.api.router import api_router
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.reservation_service import reservation_service

logger = logging.getLogger(__name__)


async def reservation_status_worker() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await reservation_service.sync_table_statuses(db)
        except Exception:
            logger.exception("Reservation table status synchronization failed.")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    worker = asyncio.create_task(reservation_status_worker())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.exception_handler(StaleDataError)
async def handle_stale_data_error(
    _request: Request,
    _exc: StaleDataError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": (
                "This order was changed on another device. "
                "Refresh the screen and try again."
            ),
        },
    )


@app.get("/")
async def root():
    return {
        "message": "GastroFlow API is running",
        "database": settings.DATABASE_URL
    }
