"""Text embeddings for knowledge base search."""

from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from triage.config import Settings
from triage.llm import MissingApiKeyError

EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def build_embedder(settings: Settings) -> Embedder:
    if settings.openai_api_key is None:
        raise MissingApiKeyError("OPENAI_API_KEY is not set (needed for embeddings).")
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        dimensions=EMBEDDING_DIMENSIONS,
        api_key=settings.openai_api_key,
        max_retries=settings.openai_max_retries,
    )
