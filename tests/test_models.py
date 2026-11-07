from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from triage.models import Action, Message, Ticket, Urgency


def test_urgency_is_ordered_by_severity() -> None:
    assert Urgency.LOW.rank < Urgency.MEDIUM.rank < Urgency.HIGH.rank < Urgency.CRITICAL.rank


@pytest.mark.parametrize(
    ("current", "floor", "expected"),
    [
        (Urgency.MEDIUM, Urgency.HIGH, Urgency.HIGH),
        (Urgency.CRITICAL, Urgency.HIGH, Urgency.CRITICAL),
        (Urgency.HIGH, Urgency.HIGH, Urgency.HIGH),
    ],
)
def test_at_least_never_lowers_urgency(current: Urgency, floor: Urgency, expected: Urgency) -> None:
    assert current.at_least(floor) is expected


def test_action_escalation_order() -> None:
    assert Action.AUTO_RESPOND.at_least(Action.ESCALATE_HUMAN) is Action.ESCALATE_HUMAN
    assert Action.ESCALATE_HUMAN.at_least(Action.ROUTE_SPECIALIST) is Action.ESCALATE_HUMAN


def _message(at: datetime, content: str = "hi") -> Message:
    return Message(sent_at=at, content=content)


def test_ticket_rejects_out_of_order_messages() -> None:
    start = datetime(2026, 11, 7, 6, tzinfo=UTC)
    with pytest.raises(ValidationError, match="chronological"):
        Ticket(
            ticket_id="T-1",
            customer_id="C-1",
            messages=[_message(start + timedelta(hours=1)), _message(start)],
        )


def test_ticket_requires_at_least_one_message() -> None:
    with pytest.raises(ValidationError):
        Ticket(ticket_id="T-1", customer_id="C-1", messages=[])
