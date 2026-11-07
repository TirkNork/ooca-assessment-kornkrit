from datetime import date
from typing import Any

import pytest

from triage.models import (
    Action,
    CustomerProfile,
    IssueType,
    Plan,
    Product,
    ProductSubscription,
    RiskFlag,
    Sentiment,
    TriageResult,
    Urgency,
)
from triage.policy import PolicyContext, PolicyEngine, Requirement
from triage.policy.rules import (
    auto_respond_needs_grounding,
    chargeback_threat,
    enterprise_outage,
    money_needs_human,
)


def _triage(**overrides: Any) -> TriageResult:
    fields = {
        "summary": "s",
        "urgency": Urgency.LOW,
        "products": [Product.CRM],
        "issue_types": [IssueType.USAGE_QUESTION],
        "sentiment": Sentiment.NEUTRAL,
        "language": "en",
        "risk_flags": [],
        "kb_article_ids": ["KB-1"],
        "action": Action.AUTO_RESPOND,
        "reasoning": "r",
    }
    return TriageResult(**(fields | overrides))


def _customer(plan: Plan) -> CustomerProfile:
    return CustomerProfile(
        customer_id="C-1",
        name="n",
        plan=plan,
        region="asia",
        seats=10,
        customer_since=date(2026, 1, 1),
        products=[ProductSubscription(product=Product.CRM, since=date(2026, 1, 1))],
    )


def _ctx(triage: TriageResult, plan: Plan = Plan.PRO, retrieved=("KB-1",)) -> PolicyContext:
    return PolicyContext(
        triage=triage, customer=_customer(plan), retrieved_kb_ids=frozenset(retrieved)
    )


# --- individual rules ---------------------------------------------------------------------


def test_chargeback_threat_requires_escalation() -> None:
    req = chargeback_threat(_ctx(_triage(risk_flags=[RiskFlag.CHARGEBACK_THREAT])))
    assert req is not None
    assert (req.min_action, req.min_urgency) == (Action.ESCALATE_HUMAN, Urgency.HIGH)
    assert chargeback_threat(_ctx(_triage())) is None


def test_duplicate_billing_charges_cannot_be_auto_answered() -> None:
    triage = _triage(issue_types=[IssueType.BILLING], risk_flags=[RiskFlag.DUPLICATE_CHARGES])
    req = money_needs_human(_ctx(triage))
    assert req is not None and req.min_action is Action.ROUTE_SPECIALIST
    assert money_needs_human(_ctx(_triage(issue_types=[IssueType.BILLING]))) is None


@pytest.mark.parametrize(("plan", "applies"), [(Plan.ENTERPRISE, True), (Plan.PRO, False)])
def test_enterprise_outage_is_critical(plan: Plan, applies: bool) -> None:
    req = enterprise_outage(_ctx(_triage(issue_types=[IssueType.OUTAGE]), plan=plan))
    assert (req is not None) is applies
    if req:
        assert (req.min_urgency, req.min_action) == (Urgency.CRITICAL, Action.ESCALATE_HUMAN)


def test_enterprise_outage_ignores_unknown_customer() -> None:
    ctx = PolicyContext(
        triage=_triage(issue_types=[IssueType.OUTAGE]), customer=None, retrieved_kb_ids=frozenset()
    )
    assert enterprise_outage(ctx) is None


@pytest.mark.parametrize(
    ("cited", "retrieved", "applies"),
    [
        (["KB-1"], ["KB-1", "KB-2"], False),  # grounded
        ([], ["KB-1"], True),  # cites nothing
        (["KB-9"], ["KB-1"], True),  # cites an article the search never returned
    ],
)
def test_auto_respond_must_cite_retrieved_articles(
    cited: list[str], retrieved: list[str], applies: bool
) -> None:
    ctx = _ctx(_triage(kb_article_ids=cited), retrieved=retrieved)
    assert (auto_respond_needs_grounding(ctx) is not None) is applies


def test_grounding_rule_only_checks_auto_respond() -> None:
    triage = _triage(action=Action.ROUTE_SPECIALIST, kb_article_ids=[])
    assert auto_respond_needs_grounding(_ctx(triage)) is None


# --- engine ---------------------------------------------------------------------------------


def test_engine_raises_to_the_highest_floor_and_records_each_change() -> None:
    triage = _triage(
        urgency=Urgency.MEDIUM,
        issue_types=[IssueType.BILLING],
        risk_flags=[RiskFlag.CHARGEBACK_THREAT, RiskFlag.DUPLICATE_CHARGES],
    )

    result = PolicyEngine().apply(_ctx(triage))

    assert result.triage.action is Action.ESCALATE_HUMAN
    assert result.triage.urgency is Urgency.HIGH
    # money_needs_human's floor (route_specialist) is already met, so only one change is logged.
    assert result.overrides == [
        "chargeback_threat: urgency medium -> high, action auto_respond -> escalate_human "
        "(a threatened chargeback needs a human before it is filed)"
    ]


def test_engine_never_lowers_severity() -> None:
    triage = _triage(urgency=Urgency.CRITICAL, action=Action.ESCALATE_HUMAN)

    def wants_less(ctx: PolicyContext) -> Requirement:
        return Requirement(
            rule="r", reason="x", min_urgency=Urgency.LOW, min_action=Action.AUTO_RESPOND
        )

    result = PolicyEngine(rules=(wants_less,)).apply(_ctx(triage))

    assert result.triage == triage
    assert result.overrides == []


def test_engine_leaves_compliant_triage_untouched() -> None:
    triage = _triage()
    result = PolicyEngine().apply(_ctx(triage))
    assert result.triage == triage and result.overrides == []
