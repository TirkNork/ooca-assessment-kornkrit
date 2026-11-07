"""Entry point for triaging tickets. CLI, API and any future UI call this, never the graph."""

import logging
from time import perf_counter
from uuid import uuid4

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph.state import CompiledStateGraph

from triage.config import Settings, get_settings
from triage.graph import build_graph
from triage.llm import build_chat_model
from triage.models import (
    Action,
    IssueType,
    RunMetadata,
    Sentiment,
    Team,
    Ticket,
    TriageOutput,
    TriageResult,
    Urgency,
)
from triage.prompts import PROMPT_VERSION
from triage.repositories import build_repositories

logger = logging.getLogger(__name__)


class TriageService:
    def __init__(self, graph: CompiledStateGraph, model_name: str) -> None:
        self._graph = graph
        self._model_name = model_name

    def triage(self, ticket: Ticket) -> TriageOutput:
        """Triage one ticket. Never raises for a failure inside the agent: the ticket is handed
        to a human instead, so it cannot be silently dropped."""
        trace_id = uuid4().hex
        usage = UsageMetadataCallbackHandler()
        started = perf_counter()

        def metadata(tool_calls: list[str]) -> RunMetadata:
            return RunMetadata(
                trace_id=trace_id,
                model=self._model_name,
                prompt_version=PROMPT_VERSION,
                latency_ms=round((perf_counter() - started) * 1000),
                total_tokens=sum(u["total_tokens"] for u in usage.usage_metadata.values()),
                tool_calls=tool_calls,
            )

        try:
            state = self._graph.invoke(
                {"ticket": ticket},
                config={
                    "callbacks": [usage],
                    "run_name": "triage_ticket",
                    "metadata": {"trace_id": trace_id, "ticket_id": ticket.ticket_id},
                },
            )
        except Exception as exc:
            # Boundary of the agent: LLM outages, exhausted retries, invalid model output, etc.
            logger.exception("triage failed for ticket %s (trace %s)", ticket.ticket_id, trace_id)
            return _fallback_output(ticket, exc, metadata(tool_calls=[]))

        return TriageOutput(
            ticket_id=ticket.ticket_id,
            triage=state["triage"],
            assigned_team=state.get("assigned_team"),
            suggested_reply=state.get("suggested_reply"),
            handoff_summary=state.get("handoff_summary"),
            policy_overrides=state.get("policy_overrides", []),
            metadata=metadata(tool_calls=_tool_calls(state["messages"])),
        )


def build_service(settings: Settings | None = None) -> TriageService:
    settings = settings or get_settings()
    graph = build_graph(build_chat_model(settings), build_repositories(settings), settings)
    return TriageService(graph, model_name=settings.openai_model)


def _fallback_output(ticket: Ticket, error: Exception, metadata: RunMetadata) -> TriageOutput:
    reason = f"automatic triage failed: {type(error).__name__}: {error}"
    return TriageOutput(
        ticket_id=ticket.ticket_id,
        triage=TriageResult(
            summary="Automatic triage failed; this ticket needs manual triage.",
            urgency=Urgency.HIGH,  # unknown impact: assume it matters until a human looks
            products=[],
            issue_types=[IssueType.OTHER],
            sentiment=Sentiment.NEUTRAL,
            language="und",  # ISO 639 code for "undetermined"
            risk_flags=[],
            kb_article_ids=[],
            action=Action.ESCALATE_HUMAN,
            reasoning=reason,
        ),
        assigned_team=Team.TECHNICAL_SUPPORT,
        handoff_summary=f"Please triage ticket {ticket.ticket_id} manually ({reason}).",
        fallback_reason=reason,
        metadata=metadata,
    )


def _tool_calls(messages: list[AnyMessage]) -> list[str]:
    return [call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]
