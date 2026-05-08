"""Global configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTOPSY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    db_path: Path = Field(default=Path(".autopsyai.db"))
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    color: bool = True

    @field_validator("db_path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        return Path(v).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
