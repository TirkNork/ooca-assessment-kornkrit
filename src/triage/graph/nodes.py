"""Graph nodes. Each takes the current state and returns only the keys it changes."""

import json
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from triage.graph.context import render_ticket_context
from triage.graph.state import TriageState
from triage.models import TriageResult
from triage.policy import PolicyContext, PolicyEngine
from triage.prompts import load_prompt
from triage.repositories import CustomerRepository
from triage.routing import assign_team


class EscalationDraft(BaseModel):
    handoff_summary: str = Field(description="Internal handoff notes for the human team, English.")
    customer_reply: str = Field(description="Holding reply to the customer, in their language.")


class TriageNodes:
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        customers: CustomerRepository,
        policy: PolicyEngine,
        max_tool_rounds: int,
    ) -> None:
        self._llm = llm
        self._llm_with_tools = llm.bind_tools(tools)
        self._classifier = llm.with_structured_output(TriageResult)
        self._escalation_writer = llm.with_structured_output(EscalationDraft)
        self._customers = customers
        self._policy = policy
        self._max_tool_rounds = max_tool_rounds

    def load_context(self, state: TriageState) -> TriageState:
        ticket = state["ticket"]
        customer = self._customers.get_profile(ticket.customer_id)
        return {
            "customer": customer,
            "messages": [
                SystemMessage(load_prompt("system")),
                HumanMessage(render_ticket_context(ticket, customer)),
            ],
        }

    def agent(self, state: TriageState) -> TriageState:
        # Once the tool budget is spent, call the model without tools so it must conclude.
        within_budget = _tool_rounds(state["messages"]) < self._max_tool_rounds
        llm = self._llm_with_tools if within_budget else self._llm
        return {"messages": [llm.invoke(state["messages"])]}

    def classify(self, state: TriageState) -> TriageState:
        prompt = HumanMessage(load_prompt("classify"))
        return {"llm_triage": self._classifier.invoke([*state["messages"], prompt])}

    def apply_policy(self, state: TriageState) -> TriageState:
        result = self._policy.apply(
            PolicyContext(
                triage=state["llm_triage"],
                customer=state.get("customer"),
                retrieved_kb_ids=_retrieved_kb_ids(state["messages"]),
            )
        )
        return {"triage": result.triage, "policy_overrides": result.overrides}

    def auto_respond(self, state: TriageState) -> TriageState:
        prompt = load_prompt("auto_respond").format(language=state["triage"].language)
        reply = self._llm.invoke([*state["messages"], HumanMessage(prompt)])
        return {"assigned_team": None, "suggested_reply": reply.text}

    def route_specialist(self, state: TriageState) -> TriageState:
        triage = state["triage"]
        return {
            "assigned_team": assign_team(triage.issue_types),
            "handoff_summary": _specialist_handoff(triage),
        }

    def escalate_human(self, state: TriageState) -> TriageState:
        triage = state["triage"]
        team = assign_team(triage.issue_types)
        prompt = load_prompt("escalate").format(team=team.value, language=triage.language)
        draft = self._escalation_writer.invoke([*state["messages"], HumanMessage(prompt)])
        return {
            "assigned_team": team,
            "handoff_summary": draft.handoff_summary,
            "suggested_reply": draft.customer_reply,
        }


def route_after_agent(state: TriageState) -> Literal["tools", "classify"]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "classify"


def route_by_action(state: TriageState) -> str:
    """Action nodes are named after the action they perform."""
    return state["triage"].action.value


def _retrieved_kb_ids(messages: list[AnyMessage]) -> frozenset[str]:
    ids: set[str] = set()
    for m in messages:
        if isinstance(m, ToolMessage) and m.name == "search_knowledge_base":
            try:
                hits = json.loads(m.text)
            except json.JSONDecodeError:
                continue
            if isinstance(hits, list):
                ids.update(
                    h["article_id"] for h in hits if isinstance(h, dict) and "article_id" in h
                )
    return frozenset(ids)


def _tool_rounds(messages: list[AnyMessage]) -> int:
    return sum(1 for m in messages if isinstance(m, AIMessage) and m.tool_calls)


def _specialist_handoff(triage: TriageResult) -> str:
    def join(values: list) -> str:
        return ", ".join(str(v) for v in values) or "none"

    return "\n".join(
        [
            triage.summary,
            f"Urgency: {triage.urgency} | Products: {join(triage.products)} | "
            f"Issues: {join(triage.issue_types)}",
            f"Risk flags: {join(triage.risk_flags)} | KB: {join(triage.kb_article_ids)}",
            f"Reasoning: {triage.reasoning}",
        ]
    )
