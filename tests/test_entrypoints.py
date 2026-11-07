"""The script and the API are thin: they parse input, call TriageService and render the output."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from triage.api import create_app
from triage.models import (
    Action,
    IssueType,
    RunMetadata,
    Sentiment,
    Team,
    Ticket,
    TriageOutput,
    TriageResult,
    Urgency,
)


class FakeService:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def triage(self, ticket: Ticket) -> TriageOutput:
        self.seen.append(ticket.ticket_id)
        return TriageOutput(
            ticket_id=ticket.ticket_id,
            triage=TriageResult(
                summary="Duplicate charges",
                urgency=Urgency.CRITICAL,
                products=[],
                issue_types=[IssueType.BILLING],
                sentiment=Sentiment.NEGATIVE,
                language="en",
                risk_flags=[],
                kb_article_ids=["KB-012"],
                action=Action.ESCALATE_HUMAN,
                reasoning="r",
            ),
            assigned_team=Team.BILLING,
            handoff_summary="- refund 2 charges",
            policy_overrides=["chargeback_threat: action route_specialist -> escalate_human (x)"],
            metadata=RunMetadata(trace_id="t1", model="fake", prompt_version="1", latency_ms=1500),
        )


def _load_script(name: str) -> ModuleType:
    path = Path("scripts") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script("triage_tickets")


@pytest.fixture
def tickets_file(data_dir: Path) -> str:
    return str(data_dir / "sample_tickets.json")


# --- scripts/triage_tickets.py ---------------------------------------------------------------


def test_script_prints_a_readable_report(
    script: ModuleType, tickets_file: str, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService()

    assert script.main([tickets_file, "--ticket", "T-1001"], service=service) == 0

    out = capsys.readouterr().out
    assert service.seen == ["T-1001"]
    assert "=== T-1001" in out
    assert "Action:     escalate_human -> billing" in out
    assert "chargeback_threat" in out and "refund 2 charges" in out
    assert "1.5s" in out


def test_script_json_output_round_trips(
    script: ModuleType, tickets_file: str, capsys: pytest.CaptureFixture[str]
) -> None:
    script.main([tickets_file, "--json"], service=FakeService())

    outputs = [TriageOutput.model_validate(o) for o in json.loads(capsys.readouterr().out)]
    assert [o.ticket_id for o in outputs] == ["T-1001", "T-1002", "T-1003"]


def test_script_rejects_unknown_ticket_ids(script: ModuleType, tickets_file: str) -> None:
    with pytest.raises(SystemExit) as exc:
        script.main([tickets_file, "--ticket", "T-404"], service=FakeService())
    assert exc.value.code == 2


# --- API -------------------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(service_factory=FakeService)) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_triage_endpoint_returns_the_service_output(client: TestClient, data_dir: Path) -> None:
    ticket = json.loads((data_dir / "sample_tickets.json").read_text())[0]

    response = client.post("/triage", json=ticket)

    assert response.status_code == 200
    body = TriageOutput.model_validate(response.json())
    assert (body.ticket_id, body.assigned_team) == ("T-1001", Team.BILLING)


def test_triage_endpoint_validates_the_ticket(client: TestClient) -> None:
    response = client.post(
        "/triage", json={"ticket_id": "T-1", "customer_id": "C-1", "messages": []}
    )
    assert response.status_code == 422
