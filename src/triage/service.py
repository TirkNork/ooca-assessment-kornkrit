"""Entry point for triaging tickets. CLI, API and any future UI call this, never the graph."""

from time import perf_counter
from uuid import uuid4

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph.state import CompiledStateGraph

from triage.config import Settings, get_settings
from triage.graph import build_graph
from triage.llm import build_chat_model
from triage.models import RunMetadata, Ticket, TriageOutput
from triage.prompts import PROMPT_VERSION
from triage.repositories import build_repositories


class TriageService:
    def __init__(self, graph: CompiledStateGraph, model_name: str) -> None:
        self._graph = graph
        self._model_name = model_name

    def triage(self, ticket: Ticket) -> TriageOutput:
        trace_id = uuid4().hex
        usage = UsageMetadataCallbackHandler()
        started = perf_counter()
        state = self._graph.invoke(
            {"ticket": ticket},
            config={
                "callbacks": [usage],
                "run_name": "triage_ticket",
                "metadata": {"trace_id": trace_id, "ticket_id": ticket.ticket_id},
            },
        )
        latency_ms = round((perf_counter() - started) * 1000)

        return TriageOutput(
            ticket_id=ticket.ticket_id,
            triage=state["triage"],
            assigned_team=state.get("assigned_team"),
            suggested_reply=state.get("suggested_reply"),
            handoff_summary=state.get("handoff_summary"),
            metadata=RunMetadata(
                trace_id=trace_id,
                model=self._model_name,
                prompt_version=PROMPT_VERSION,
                latency_ms=latency_ms,
                total_tokens=sum(u["total_tokens"] for u in usage.usage_metadata.values()),
                tool_calls=_tool_calls(state["messages"]),
            ),
        )


def build_service(settings: Settings | None = None) -> TriageService:
    settings = settings or get_settings()
    graph = build_graph(build_chat_model(settings), build_repositories(settings), settings)
    return TriageService(graph, model_name=settings.openai_model)


def _tool_calls(messages: list[AnyMessage]) -> list[str]:
    return [call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]
