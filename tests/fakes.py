"""Test doubles."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    """Chat model that returns pre-scripted responses in order.

    Plain calls must be scripted with an `AIMessage`; structured-output calls with an instance of
    the requested schema. Every call is recorded so tests can assert on what the graph sent.
    Copies made by `bind_tools` share the same script and call log.
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
        if not isinstance(response, expected):
            raise AssertionError(f"scripted {type(response).__name__}, graph wanted {expected}")
        self.calls.append(
            {"messages": messages, "kind": expected.__name__, "tools_bound": self.tools_bound}
        )
        return response
