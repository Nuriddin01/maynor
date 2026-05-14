from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    database_url: str = Field(default="postgresql+asyncpg://sleep:sleep@postgres:5432/sleep_support", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    telegram_bot_token: str = Field(default="local-mock-token", alias="TELEGRAM_BOT_TOKEN")
    bot_mode: str = Field(default="polling", alias="BOT_MODE")
    admin_token: str = Field(default="change-me-local-admin-token", alias="ADMIN_TOKEN")
    billing_provider: str = Field(default="mock", alias="BILLING_PROVIDER")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    content_path: str = Field(default="content", alias="CONTENT_PATH")
    local_db_path: str = Field(default="local_data/sleep_support.sqlite3", alias="LOCAL_DB_PATH")
    local_server_host: str = Field(default="127.0.0.1", alias="LOCAL_SERVER_HOST")
    local_server_port: int = Field(default=8000, alias="LOCAL_SERVER_PORT")
    encryption_key: str = Field(default="local-development-key-change-me", alias="ENCRYPTION_KEY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


def get_settings() -> Settings:
    return Settings()
