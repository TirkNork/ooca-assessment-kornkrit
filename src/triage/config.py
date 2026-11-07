"""Application settings, loaded from environment variables (and `.env` if present)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    # None = use the model's default (some reasoning models reject a temperature).
    openai_temperature: float | None = Field(default=0.0, ge=0, le=2)
    openai_timeout_s: float = Field(default=60.0, gt=0)

    # Set to /app/data in the Docker image; the relative default resolves from the working dir.
    data_dir: Path = Path("data")
    max_tool_iterations: int = Field(default=6, ge=1)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"


@lru_cache
def get_settings() -> Settings:
    return Settings()
