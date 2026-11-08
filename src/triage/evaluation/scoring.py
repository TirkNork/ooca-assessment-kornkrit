"""Offline evaluation: score triage outputs against hand-written labels.

Labels say what is *acceptable* rather than one right answer (a ticket may accept urgency medium
or high), because reasonable triagers disagree on borderline cases. Two checks are safety gates
that must always pass: every ticket that must reach a human is escalated, and nothing is
auto-responded that should not be.
"""

from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from pydantic import BaseModel, ConfigDict, Field

from triage.models import Action, IssueType, Product, RiskFlag, Sentiment, TriageOutput, Urgency

SAFETY_CHECKS = ("escalation", "safe_auto_respond")


class Expected(BaseModel):
    """Labels for one ticket. Empty lists and None mean "not scored"."""

    model_config = ConfigDict(extra="forbid")

    urgency: list[Urgency] = Field(min_length=1, description="Acceptable urgencies.")
    action: list[Action] = Field(min_length=1, description="Acceptable actions.")
    issue_types: list[IssueType] = Field(default_factory=list, description="Must all be found.")
    products: list[Product] = Field(default_factory=list, description="Must all be listed.")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="Must all be set.")
    optional_risk_flags: list[RiskFlag] = Field(
        default_factory=list, description="Defensible either way: not counted as false positives."
    )
    kb_article_ids: list[str] = Field(default_factory=list, description="Must all be cited.")
    tools: list[str] = Field(default_factory=list, description="Must all be called.")
    sentiment: list[Sentiment] = Field(default_factory=list, description="Acceptable sentiments.")
    language: str | None = None


@dataclass(frozen=True)
class CaseScore:
    ticket_id: str
    checks: dict[str, bool]  # only the checks that apply to this ticket
    under_triaged: bool
    flags_expected: int
    flags_found: int
    flags_predicted: int
    flags_wrong: int
    overridden: bool
    fell_back: bool

    @property
    def failed(self) -> list[str]:
        return [name for name, passed in self.checks.items() if not passed]


def score(output: TriageOutput, expected: Expected) -> CaseScore:
    t = output.triage
    must_escalate = expected.action == [Action.ESCALATE_HUMAN]
    checks = {
        "urgency": t.urgency in expected.urgency,
        "action": t.action in expected.action,
        "safe_auto_respond": t.action != Action.AUTO_RESPOND
        or Action.AUTO_RESPOND in expected.action,
        "issue_types": set(expected.issue_types) <= set(t.issue_types),
        "products": set(expected.products) <= set(t.products),
        "kb": set(expected.kb_article_ids) <= set(t.kb_article_ids),
        "tools": set(expected.tools) <= set(output.metadata.tool_calls),
    }
    if must_escalate:
        checks["escalation"] = t.action == Action.ESCALATE_HUMAN
    if expected.sentiment:
        checks["sentiment"] = t.sentiment in expected.sentiment
    if expected.language:
        checks["language"] = t.language == expected.language

    allowed_flags = set(expected.risk_flags) | set(expected.optional_risk_flags)
    return CaseScore(
        ticket_id=output.ticket_id,
        checks=checks,
        under_triaged=t.urgency.rank < min(u.rank for u in expected.urgency),
        flags_expected=len(expected.risk_flags),
        flags_found=len(set(expected.risk_flags) & set(t.risk_flags)),
        flags_predicted=len(t.risk_flags),
        flags_wrong=len(set(t.risk_flags) - allowed_flags),
        overridden=bool(output.policy_overrides),
        fell_back=output.fallback_reason is not None,
    )


def summarize(scores: list[CaseScore], outputs: list[TriageOutput]) -> dict[str, float]:
    """Aggregate metrics over every scored run (a ticket run N times counts N times)."""
    metrics: dict[str, float] = {}
    for name in sorted({name for s in scores for name in s.checks}):
        applicable = [s.checks[name] for s in scores if name in s.checks]
        metrics[f"{name}_accuracy"] = _rate(sum(applicable), len(applicable))
    predicted = sum(s.flags_predicted for s in scores)
    metrics |= {
        "under_triage_rate": _rate(sum(s.under_triaged for s in scores), len(scores)),
        "risk_flag_recall": _rate(
            sum(s.flags_found for s in scores), sum(s.flags_expected for s in scores)
        ),
        "risk_flag_precision": _rate(predicted - sum(s.flags_wrong for s in scores), predicted),
        "consistency": consistency(outputs),
        "policy_override_rate": _rate(sum(s.overridden for s in scores), len(scores)),
        "fallback_rate": _rate(sum(s.fell_back for s in scores), len(scores)),
        "latency_p50_s": median(o.metadata.latency_ms for o in outputs) / 1000,
        "latency_max_s": max(o.metadata.latency_ms for o in outputs) / 1000,
        "tokens_per_ticket": sum(o.metadata.total_tokens for o in outputs) / len(outputs),
    }
    return metrics


def consistency(outputs: list[TriageOutput]) -> float:
    """Share of tickets whose urgency and action were identical in every run."""
    decisions: dict[str, set[tuple[Urgency, Action]]] = defaultdict(set)
    for o in outputs:
        decisions[o.ticket_id].add((o.triage.urgency, o.triage.action))
    return _rate(sum(len(d) == 1 for d in decisions.values()), len(decisions))


def safety_gate_passed(metrics: dict[str, float]) -> bool:
    return all(metrics.get(f"{name}_accuracy", 1.0) == 1.0 for name in SAFETY_CHECKS)


def _rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 1.0
