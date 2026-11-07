import pytest
from pydantic import SecretStr

from triage.config import Settings
from triage.llm import MissingApiKeyError, build_chat_model


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, openai_api_key=SecretStr("sk-test"), **overrides)


def test_missing_api_key_fails_with_a_clear_error() -> None:
    with pytest.raises(MissingApiKeyError, match="OPENAI_API_KEY"):
        build_chat_model(Settings(_env_file=None, openai_api_key=None))


def test_retries_and_timeout_come_from_settings() -> None:
    llm = build_chat_model(_settings(openai_max_retries=5, openai_timeout_s=12))
    assert llm.max_retries == 5
    assert llm.request_timeout == 12
    assert llm.rate_limiter is None


def test_rate_limiter_is_enabled_when_configured() -> None:
    llm = build_chat_model(_settings(openai_requests_per_second=2))
    assert llm.rate_limiter is not None
