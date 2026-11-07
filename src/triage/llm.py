"""Chat model construction."""

from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import ChatOpenAI

from triage.config import Settings


class MissingApiKeyError(RuntimeError):
    pass


def build_chat_model(settings: Settings) -> BaseChatModel:
    if settings.openai_api_key is None:
        raise MissingApiKeyError("OPENAI_API_KEY is not set (add it to .env).")
    rate_limiter = (
        InMemoryRateLimiter(requests_per_second=settings.openai_requests_per_second)
        if settings.openai_requests_per_second
        else None
    )
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        timeout=settings.openai_timeout_s,
        max_retries=settings.openai_max_retries,
        rate_limiter=rate_limiter,
        api_key=settings.openai_api_key,
    )
