"""Application settings, loaded from environment variables (and `.env` if present)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # An empty variable (e.g. `OPENAI_TEMPERATURE=`) means "not set" for optional fields.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_parse_none_str="", extra="ignore"
    )

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    # None = don't send a temperature (use the model's default);
    openai_temperature: float | None = Field(default=None, ge=0, le=2)
    openai_timeout_s: float = Field(default=60.0, gt=0)
    # The OpenAI SDK retries 429/5xx/connection errors with backoff and honours Retry-After.
    openai_max_retries: int = Field(default=3, ge=0)
    # Client-side throttle (e.g. for batch eval runs); None = no limit.
    openai_requests_per_second: float | None = Field(default=None, gt=0)

    # Set to /app/data in the Docker image; the relative default resolves from the working dir.
    data_dir: Path = Path("data")
    max_tool_iterations: int = Field(default=6, ge=1)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
