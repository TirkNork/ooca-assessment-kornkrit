"""End-to-end graph wiring with a scripted LLM: real tools and data, no API key needed."""

import json
import logging
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


def test_policy_overrides_the_llm_and_is_reported(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    # The model proposes an automatic reply citing an article it never retrieved.
    llm = ScriptedChatModel(
        script=[
            AIMessage("No lookups needed."),
            _triage(Action.AUTO_RESPOND, kb_article_ids=["KB-999"]),
        ]
    )

    output = _run(llm, repositories, tickets["T-1003"])

    assert output.triage.action is Action.ROUTE_SPECIALIST
    assert output.assigned_team is Team.TECHNICAL_SUPPORT
    assert output.suggested_reply is None
    assert output.policy_overrides[0].startswith("auto_respond_needs_grounding:")


def test_enterprise_outage_is_escalated_even_if_the_llm_routes_it(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(
        script=[
            AIMessage("Looks like an outage."),
            _triage(Action.ROUTE_SPECIALIST, urgency=Urgency.HIGH, issue_types=[IssueType.OUTAGE]),
            EscalationDraft(handoff_summary="- outage", customer_reply="กำลังตรวจสอบ"),
        ]
    )

    output = _run(llm, repositories, tickets["T-1002"])  # C-2001 is Enterprise

    assert (output.triage.action, output.triage.urgency) == (
        Action.ESCALATE_HUMAN,
        Urgency.CRITICAL,
    )
    assert output.assigned_team is Team.ENGINEERING_ONCALL
    assert output.policy_overrides[0].startswith("enterprise_outage:")


def test_llm_failure_falls_back_to_a_human_instead_of_raising(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(script=[TimeoutError("OpenAI did not respond")])

    output = _run(llm, repositories, tickets["T-1001"])

    assert output.fallback_reason is not None and "TimeoutError" in output.fallback_reason
    assert output.triage.action is Action.ESCALATE_HUMAN
    assert output.triage.urgency is Urgency.HIGH
    assert output.assigned_team is Team.TECHNICAL_SUPPORT
    assert "T-1001" in (output.handoff_summary or "")
    assert output.metadata.trace_id


def test_successful_run_has_no_fallback_reason(
    repositories: Repositories, tickets: dict[str, Ticket]
) -> None:
    llm = ScriptedChatModel(script=[AIMessage("ok"), _triage(Action.ROUTE_SPECIALIST)])
    assert _run(llm, repositories, tickets["T-1003"]).fallback_reason is None


def test_llm_failure_is_logged_with_traceback(
    repositories: Repositories, tickets: dict[str, Ticket], caplog: pytest.LogCaptureFixture
) -> None:
    llm = ScriptedChatModel(script=[TimeoutError("OpenAI did not respond")])

    with caplog.at_level(logging.ERROR, logger="triage"):
        _run(llm, repositories, tickets["T-1001"])

    [record] = caplog.records
    assert "triage failed: ticket=T-1001" in record.getMessage()
    assert record.exc_info is not None and record.exc_info[0] is TimeoutError
