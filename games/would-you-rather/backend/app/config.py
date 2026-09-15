from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, overridable via environment variables
    (prefixed REVELRY_) or a .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="REVELRY_", extra="ignore")

    app_name: str = "Revelry - Would You Rather Live"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3400"]
    frontend_base_url: str = "http://localhost:3400"


@lru_cache
def get_settings() -> Settings:
    return Settings()
