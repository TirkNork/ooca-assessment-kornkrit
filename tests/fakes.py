"""Test doubles."""

import hashlib
import math
from collections import Counter
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import Field

from triage.embeddings import EMBEDDING_DIMENSIONS
from triage.repositories.file.bm25_knowledge_base import tokenize


class ScriptedChatModel(BaseChatModel):
    """Chat model that returns pre-scripted responses in order.

    Plain calls must be scripted with an `AIMessage`; structured-output calls with an instance of
    the requested schema. A scripted exception is raised, to simulate API failures. Every call
    is recorded so tests can assert on what the graph sent. Copies made by `bind_tools` share
    the same script and call log.
    """

    # Typed as Any so pydantic stores the scripted objects as-is instead of coercing them.
    script: list[Any] = Field(default_factory=list)
    calls: list[dict[str, Any]] = Field(default_factory=list)
    tools_bound: bool = False

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self.model_copy(update={"tools_bound": True})

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable:
        return RunnableLambda(lambda messages: self._next(messages, expected=schema))

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        message = self._next(messages, expected=AIMessage)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _next(self, messages: Any, expected: type) -> Any:
        if not self.script:
            raise AssertionError(f"unexpected extra LLM call (wanted {expected.__name__})")
        response = self.script.pop(0)
        if isinstance(response, Exception):
            raise response
        if not isinstance(response, expected):
            raise AssertionError(f"scripted {type(response).__name__}, graph wanted {expected}")
        self.calls.append(
            {"messages": messages, "kind": expected.__name__, "tools_bound": self.tools_bound}
        )
        return response


class HashingEmbedder:
    """Deterministic bag-of-words embedding: texts sharing words get similar vectors, so vector
    search behaves sensibly in tests without calling an embedding API."""

    def __init__(self) -> None:
        self.embedded_texts = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_texts += len(texts)
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token, count in Counter(tokenize(text)).items():
            index = int(hashlib.md5(token.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS
            vector[index] += count
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
