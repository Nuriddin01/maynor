from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = Field(default="TEST_TOKEN")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/sleep_support_bot.db")
    app_timezone: str = Field(default="UTC")
    log_level: str = Field(default="INFO")
    alarm_repeat_interval_seconds: int = Field(default=60, ge=15, le=3600)
    max_alarm_repeat_attempts: int = Field(default=3, ge=1, le=10)
    alarm_code_length: int = Field(default=4, ge=4, le=8)
    default_language: str = Field(default="ru")
    default_time_format: str = Field(default="24h")
    project_name: str = Field(default="Sleep Support Bot")
    data_dir: Path = Field(default=Path("./data"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SSB_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
