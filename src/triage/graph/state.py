from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from triage.models import CustomerProfile, Team, Ticket, TriageResult


class TriageState(TypedDict, total=False):
    ticket: Ticket
    customer: CustomerProfile | None
    messages: Annotated[list[AnyMessage], add_messages]
    llm_triage: TriageResult  # as classified by the model
    triage: TriageResult  # after policy rules
    policy_overrides: list[str]
    assigned_team: Team | None
    suggested_reply: str | None
    handoff_summary: str | None
