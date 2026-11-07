"""End-to-end graph wiring with a scripted LLM: real tools and data, no API key needed."""

import json
from typing import Any

import pytest
from fakes import ScriptedChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import TypeAdapter

from triage.config import Settings, get_settings
from triage.graph import build_graph
from triage.graph.nodes import EscalationDraft
from triage.models import (
    Action,
    IssueType,
    Product,
    RiskFlag,
    Sentiment,
    Team,
    Ticket,
    TriageResult,
    Urgency,
)
from triage.repositories import Repositories
from triage.service import TriageService


@pytest.fixture(scope="module")
def tickets(data_dir) -> dict[str, Ticket]:
    raw = (data_dir / "sample_tickets.json").read_bytes()
    return {t.ticket_id: t for t in TypeAdapter(list[Ticket]).validate_json(raw)}


def _tool_call(name: str, **args: Any) -> dict[str, Any]:
    return {"name": name, "args": args, "id": f"call_{name}"}


def _triage(action: Action, **overrides: Any) -> TriageResult:
    fields = {
        "summary": "summary",
        "urgency": Urgency.LOW,
        "products": [Product.CRM],
        "issue_types": [IssueType.USAGE_QUESTION],
        "sentiment": Sentiment.NEUTRAL,
        "language": "en",
        "risk_flags": [],
        "kb_article_ids": [],
        "action": action,
        "reasoning": "because",
    }
    return TriageResult(**(fields | overrides))


def _run(
    llm: ScriptedChatModel,
    repositories: Repositories,
    ticket: Ticket,
    settings: Settings | None = None,
):
    graph = build_graph(llm, repositories, settings or get_settings())
    return TriageService(graph, model_name="scripted").triage(ticket)


def test_escalation_runs_tools_and_writes_handoff(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(
        script=[
            AIMessage(
                "",
                tool_calls=[
                    _tool_call("get_customer_history", customer_id="C-1001"),
                    _tool_call("get_billing_transactions", customer_id="C-1001"),
                ],
            ),
            AIMessage("Three pending charges, plan not activated."),
            _triage(
                Action.ESCALATE_HUMAN,
                urgency=Urgency.CRITICAL,
                issue_types=[IssueType.BILLING],
                risk_flags=[RiskFlag.CHARGEBACK_THREAT],
            ),
            EscalationDraft(handoff_summary="- 3 pending charges", customer_reply="We're on it."),
        ]
    )

    output = _run(llm, repositories, tickets["T-1001"])

    assert output.triage.action is Action.ESCALATE_HUMAN
    assert output.assigned_team is Team.BILLING
    assert output.handoff_summary == "- 3 pending charges"
    assert output.suggested_reply == "We're on it."
    assert output.metadata.tool_calls == ["get_customer_history", "get_billing_transactions"]
    assert not llm.script, "every scripted response should be consumed"

    # The tools really ran against the data, and their results reached the next model call.
    agent_second_call = llm.calls[1]["messages"]
    tool_results = [m for m in agent_second_call if isinstance(m, ToolMessage)]
    billing = json.loads(tool_results[1].content)
    assert billing["subscription_status"] == "upgrade_pending"


def test_auto_respond_drafts_a_reply_without_a_team(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(
        script=[
            AIMessage("", tool_calls=[_tool_call("search_knowledge_base", query="dark mode")]),
            AIMessage("KB-020 covers it."),
            _triage(Action.AUTO_RESPOND, kb_article_ids=["KB-020"]),
            AIMessage("Hi! Dark mode is rolling out..."),
        ]
    )

    output = _run(llm, repositories, tickets["T-1003"])

    assert output.assigned_team is None
    assert output.suggested_reply == "Hi! Dark mode is rolling out..."
    assert output.handoff_summary is None


def test_route_specialist_needs_no_extra_llm_call(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(
        script=[
            AIMessage("Nothing to look up."),
            _triage(Action.ROUTE_SPECIALIST, issue_types=[IssueType.FEATURE_REQUEST]),
        ]
    )

    output = _run(llm, repositories, tickets["T-1003"])

    assert output.assigned_team is Team.PRODUCT
    assert output.suggested_reply is None
    assert "feature_request" in (output.handoff_summary or "")


def test_agent_sees_system_prompt_profile_and_full_thread(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(
        script=[AIMessage("ok"), _triage(Action.ROUTE_SPECIALIST)],
    )
    _run(llm, repositories, tickets["T-1002"])

    first_call = llm.calls[0]
    assert first_call["tools_bound"]
    context = next(m for m in first_call["messages"] if isinstance(m, HumanMessage)).text
    assert '"region": "asia"' in context
    assert "ระบบเข้าไม่ได้ครับ" in context and "region Asia" in context


def test_tool_budget_forces_the_agent_to_conclude(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(
        script=[
            AIMessage("", tool_calls=[_tool_call("get_customer_history", customer_id="C-3001")]),
            AIMessage("Done."),
            _triage(Action.ROUTE_SPECIALIST),
        ]
    )
    settings = get_settings().model_copy(update={"max_tool_iterations": 1})

    _run(llm, repositories, tickets["T-1003"], settings)

    assert [c["tools_bound"] for c in llm.calls[:2]] == [True, False]
