from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, overridable via environment variables
    (prefixed REVELRY_) or a .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="REVELRY_", extra="ignore")

    app_name: str = "Revelry - Mafia"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./revelry.db"
    cors_origins: list[str] = ["http://localhost:3000"]
    frontend_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
