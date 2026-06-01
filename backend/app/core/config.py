from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    RECEIPTS_DIR: str = "backend/generated_receipts"
    PUBLIC_MENU_BASE_URL: str = "http://localhost:3000/qr"


settings = Settings() #type: ignore
