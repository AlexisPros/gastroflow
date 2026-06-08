from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm.exc import StaleDataError

from app.api.router import api_router
from app.core.config import settings

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):517[3-9]",
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
