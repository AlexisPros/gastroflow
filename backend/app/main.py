from fastapi import FastAPI

from app.core.config import settings

app = FastAPI()


@app.get("/")
async def root():
    return {
        "message": "GastroFlow API is running",
        "database": settings.DATABASE_URL
    }