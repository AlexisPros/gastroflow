from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    RECEIPTS_DIR: str = "backend/generated_receipts"

    class Config:
        env_file = ".env"


settings = Settings() #type: ignore
