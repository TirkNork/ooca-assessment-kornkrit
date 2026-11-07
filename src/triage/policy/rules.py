"""Business rules that guard the LLM's triage.

A rule inspects the context and returns a `Requirement` (a floor for urgency and/or action) or
None. Rules can only raise severity, never lower it, so adding a rule can never make triage less
safe. To add a rule, write a function with the `Rule` signature and add it to `DEFAULT_RULES`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from triage.models import Action, CustomerProfile, IssueType, Plan, RiskFlag, TriageResult, Urgency


@dataclass(frozen=True)
class PolicyContext:
    triage: TriageResult
    customer: CustomerProfile | None
    retrieved_kb_ids: frozenset[str]
    """KB articles the search tool actually returned during this run."""


@dataclass(frozen=True)
class Requirement:
    rule: str
    reason: str
    min_urgency: Urgency | None = None
    min_action: Action | None = None


Rule = Callable[[PolicyContext], Requirement | None]


def chargeback_threat(ctx: PolicyContext) -> Requirement | None:
    if RiskFlag.CHARGEBACK_THREAT in ctx.triage.risk_flags:
        return Requirement(
            rule="chargeback_threat",
            reason="a threatened chargeback needs a human before it is filed",
            min_urgency=Urgency.HIGH,
            min_action=Action.ESCALATE_HUMAN,
        )
    return None


def money_needs_human(ctx: PolicyContext) -> Requirement | None:
    if (
        IssueType.BILLING in ctx.triage.issue_types
        and RiskFlag.DUPLICATE_CHARGES in ctx.triage.risk_flags
    ):
        return Requirement(
            rule="money_needs_human",
            reason="only the billing team can refund or void charges",
            min_action=Action.ROUTE_SPECIALIST,
        )
    return None


def enterprise_outage(ctx: PolicyContext) -> Requirement | None:
    is_enterprise = ctx.customer is not None and ctx.customer.plan is Plan.ENTERPRISE
    if is_enterprise and IssueType.OUTAGE in ctx.triage.issue_types:
        return Requirement(
            rule="enterprise_outage",
            reason="an outage for an Enterprise customer is a P1 under the SLA",
            min_urgency=Urgency.CRITICAL,
            min_action=Action.ESCALATE_HUMAN,
        )
    return None


def auto_respond_needs_grounding(ctx: PolicyContext) -> Requirement | None:
    if ctx.triage.action is not Action.AUTO_RESPOND:
        return None
    cited = set(ctx.triage.kb_article_ids)
    if not cited or not cited <= ctx.retrieved_kb_ids:
        return Requirement(
            rule="auto_respond_needs_grounding",
            reason="an automatic reply must cite KB articles the search actually returned",
            min_action=Action.ROUTE_SPECIALIST,
        )
    return None


DEFAULT_RULES: tuple[Rule, ...] = (
    chargeback_threat,
    money_needs_human,
    enterprise_outage,
    auto_respond_needs_grounding,
)
