"""Triage results.

`TriageResult` is the LLM's structured output, so every field carries a description:
those descriptions become part of the JSON schema the model is asked to fill.
"""

from pydantic import BaseModel, Field

from triage.models.enums import (
    Action,
    IssueType,
    Product,
    RiskFlag,
    Sentiment,
    Team,
    Urgency,
)


class TriageResult(BaseModel):
    summary: str = Field(description="One-sentence summary of the customer's problem(s).")
    urgency: Urgency = Field(description="How quickly a human must act on this ticket.")
    products: list[Product] = Field(
        min_length=1,
        description=(
            "Products affected by the ticket. Infer from the messages and the products the "
            "customer subscribes to; list several if the issue spans products."
        ),
    )
    issue_types: list[IssueType] = Field(
        min_length=1, description="All distinct issues raised in the thread (may be several)."
    )
    sentiment: Sentiment = Field(
        description=(
            "Customer sentiment, judged from the whole thread with most weight on the latest "
            "message."
        )
    )
    language: str = Field(description="ISO 639-1 code of the language the customer writes in.")
    risk_flags: list[RiskFlag] = Field(
        description="Business-risk signals explicitly supported by the thread or tool results."
    )
    kb_article_ids: list[str] = Field(
        description="IDs of knowledge base articles that are relevant to answering this ticket."
    )
    action: Action = Field(description="Proposed next action.")
    reasoning: str = Field(description="Short justification for urgency and action.")


class RunMetadata(BaseModel):
    trace_id: str
    model: str
    prompt_version: str
    latency_ms: int = 0
    total_tokens: int = 0
    tool_calls: list[str] = Field(default_factory=list)


class TriageOutput(BaseModel):
    """Final result returned to callers (CLI, API, ...)."""

    ticket_id: str
    triage: TriageResult = Field(description="Triage after policy rules were applied.")
    assigned_team: Team | None = None
    suggested_reply: str | None = Field(
        default=None, description="Draft reply to the customer; never sent automatically here."
    )
    handoff_summary: str | None = Field(
        default=None, description="Context for the human or specialist who picks this up."
    )
    policy_overrides: list[str] = Field(default_factory=list)
    metadata: RunMetadata
