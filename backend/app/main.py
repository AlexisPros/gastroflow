from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI()
app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "message": "GastroFlow API is running",
        "database": settings.DATABASE_URL
    }
