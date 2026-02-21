from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORD_", env_file=".env", extra="ignore")

    APP_VERSION: str = "1.0.0"
    ENV: str = "development"

    DATABASE_URL: str = Field(..., example="postgresql+asyncpg://postgres:postgres@localhost:5432/fb_orders")
    JWT_SECRET_KEY: str = Field(...)

    # Downstream
    USER_SERVICE_URL: str = "http://user-service:8001"
    INVENTORY_SERVICE_URL: str = "http://inventory-service:8003"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8004"

    HTTP_TIMEOUT: float = 5.0
    MAX_RETRIES: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
