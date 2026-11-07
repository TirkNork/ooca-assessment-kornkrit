from datetime import UTC, datetime, timedelta, timezone

import pytest

from triage.graph.context import render_ticket_context
from triage.models import IssueType, Message, Team, Ticket
from triage.routing import assign_team


@pytest.mark.parametrize(
    ("issue_types", "team"),
    [
        ([IssueType.OUTAGE, IssueType.BILLING], Team.BILLING),
        ([IssueType.OUTAGE], Team.ENGINEERING_ONCALL),
        ([IssueType.BILLING], Team.BILLING),
        ([IssueType.BUG, IssueType.FEATURE_REQUEST], Team.TECHNICAL_SUPPORT),
        ([IssueType.FEATURE_REQUEST], Team.PRODUCT),
        ([IssueType.USAGE_QUESTION], Team.TECHNICAL_SUPPORT),
        ([IssueType.OTHER], Team.TECHNICAL_SUPPORT),
    ],
)
def test_assign_team_follows_priority_order(issue_types: list[IssueType], team: Team) -> None:
    assert assign_team(issue_types) is team


def test_context_renders_thread_in_utc_and_flags_missing_profile() -> None:
    bangkok = timezone(timedelta(hours=7))
    ticket = Ticket(
        ticket_id="T-1",
        customer_id="C-404",
        messages=[
            Message(sent_at=datetime(2026, 11, 7, 14, tzinfo=bangkok), content="first"),
            Message(sent_at=datetime(2026, 11, 7, 9, 30, tzinfo=UTC), content="second"),
        ],
    )

    text = render_ticket_context(ticket, customer=None)

    assert '"note": "profile not found"' in text
    assert "[2026-11-07 07:00 UTC] customer: first" in text
    assert "Current time: 2026-11-07 09:30 UTC" in text
