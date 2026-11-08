"""Eval scoring (no LLM) and the consistency of the eval dataset itself."""

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from triage.evaluation import Expected, consistency, safety_gate_passed, score, summarize
from triage.models import (
    Action,
    IssueType,
    Product,
    RiskFlag,
    RunMetadata,
    Sentiment,
    Ticket,
    TriageOutput,
    TriageResult,
    Urgency,
)
from triage.repositories.kb_markdown import load_articles
from triage.tools import build_tools

ESCALATE = Expected(
    urgency=[Urgency.CRITICAL],
    action=[Action.ESCALATE_HUMAN],
    issue_types=[IssueType.BILLING],
    risk_flags=[RiskFlag.CHARGEBACK_THREAT, RiskFlag.DUPLICATE_CHARGES],
    optional_risk_flags=[RiskFlag.TIME_SENSITIVE],
    kb_article_ids=["KB-012"],
    tools=["get_billing_transactions"],
    language="en",
)


def make_output(
    ticket_id: str = "T-1",
    urgency: Urgency = Urgency.CRITICAL,
    action: Action = Action.ESCALATE_HUMAN,
    risk_flags: tuple[RiskFlag, ...] = (RiskFlag.CHARGEBACK_THREAT, RiskFlag.DUPLICATE_CHARGES),
    overrides: tuple[str, ...] = (),
) -> TriageOutput:
    return TriageOutput(
        ticket_id=ticket_id,
        triage=TriageResult(
            summary="s",
            urgency=urgency,
            products=[],
            issue_types=[IssueType.BILLING],
            sentiment=Sentiment.NEGATIVE,
            language="en",
            risk_flags=list(risk_flags),
            kb_article_ids=["KB-012"],
            action=action,
            reasoning="r",
        ),
        policy_overrides=list(overrides),
        metadata=RunMetadata(
            trace_id="t",
            model="fake",
            prompt_version="1",
            latency_ms=2000,
            total_tokens=100,
            tool_calls=["get_customer_history", "get_billing_transactions"],
        ),
    )


# --- scoring --------------------------------------------------------------------------------


def test_a_correct_output_passes_every_check() -> None:
    result = score(make_output(), ESCALATE)
    assert result.failed == []
    assert set(result.checks) >= {"urgency", "action", "escalation", "safe_auto_respond"}
    assert not result.under_triaged


def test_missing_an_escalation_fails_the_safety_gate() -> None:
    result = score(make_output(urgency=Urgency.MEDIUM, action=Action.ROUTE_SPECIALIST), ESCALATE)
    assert {"urgency", "action", "escalation"} <= set(result.failed)
    assert result.under_triaged
    assert not safety_gate_passed(summarize([result], [make_output()]))


def test_auto_responding_when_not_acceptable_is_unsafe() -> None:
    expected = Expected(urgency=[Urgency.LOW], action=[Action.ROUTE_SPECIALIST])
    result = score(make_output(urgency=Urgency.LOW, action=Action.AUTO_RESPOND), expected)
    assert result.failed == ["action", "safe_auto_respond"]
    assert "escalation" not in result.checks  # only scored when escalation is required


def test_missing_a_labelled_product_fails_but_extra_products_do_not() -> None:
    expected = ESCALATE.model_copy(update={"products": [Product.ANALYTICS]})
    output = make_output()
    assert score(output, expected).failed == ["products"]
    output.triage.products = [Product.ANALYTICS, Product.CRM]
    assert score(output, expected).failed == []


def test_over_triage_is_wrong_but_not_under_triage() -> None:
    expected = Expected(urgency=[Urgency.LOW], action=[Action.AUTO_RESPOND])
    result = score(make_output(urgency=Urgency.HIGH, action=Action.AUTO_RESPOND), expected)
    assert "urgency" in result.failed and not result.under_triaged


def test_optional_flags_are_not_false_positives() -> None:
    flags = (RiskFlag.CHARGEBACK_THREAT, RiskFlag.TIME_SENSITIVE, RiskFlag.REVENUE_IMPACT)
    result = score(make_output(risk_flags=flags), ESCALATE)
    assert (result.flags_found, result.flags_expected) == (1, 2)
    assert (result.flags_wrong, result.flags_predicted) == (1, 3)  # only revenue_impact


def test_summary_aggregates_runs() -> None:
    outputs = [
        make_output("T-1"),
        make_output("T-1", overrides=("rule: ...",)),
        make_output("T-2", urgency=Urgency.HIGH),
    ]
    metrics = summarize([score(o, ESCALATE) for o in outputs], outputs)
    assert metrics["urgency_accuracy"] == pytest.approx(2 / 3)
    assert metrics["under_triage_rate"] == pytest.approx(1 / 3)
    assert metrics["risk_flag_recall"] == metrics["risk_flag_precision"] == 1.0
    assert metrics["policy_override_rate"] == pytest.approx(1 / 3)
    assert metrics["latency_p50_s"] == 2.0 and metrics["tokens_per_ticket"] == 100
    assert safety_gate_passed(metrics)


def test_consistency_counts_tickets_with_identical_decisions() -> None:
    runs = [make_output("T-1"), make_output("T-1"), make_output("T-2"), make_output("T-2")]
    assert consistency(runs) == 1.0
    runs[3] = make_output("T-2", action=Action.ROUTE_SPECIALIST)
    assert consistency(runs) == 0.5


# --- the dataset ----------------------------------------------------------------------------

TICKET_FILES = ["sample_tickets.json", "test_set.json"]


@pytest.fixture(scope="module")
def labels(data_dir: Path) -> dict[str, Expected]:
    return TypeAdapter(dict[str, Expected]).validate_json(
        (data_dir / "eval_labels.json").read_text()
    )


def test_every_ticket_has_labels_and_every_label_a_ticket(data_dir: Path, labels) -> None:
    ids = [
        t.ticket_id
        for name in TICKET_FILES
        for t in TypeAdapter(list[Ticket]).validate_json((data_dir / name).read_text())
    ]
    assert len(ids) == len(set(ids))
    assert set(ids) == labels.keys()


def test_labels_only_reference_existing_articles_and_tools(data_dir: Path, labels, repositories):
    article_ids = {a.article_id for a in load_articles(data_dir / "kb")}
    tool_names = {tool.name for tool in build_tools(repositories)}
    for expected in labels.values():
        assert set(expected.kb_article_ids) <= article_ids
        assert set(expected.tools) <= tool_names
        assert not set(expected.risk_flags) & set(expected.optional_risk_flags)


# --- the script -----------------------------------------------------------------------------


class LabelledFakeService:
    """Returns the first acceptable decision for each ticket, or an under-triage for one id."""

    def __init__(self, labels: dict[str, Expected], miss: str | None = None) -> None:
        self.labels, self.miss = labels, miss

    def triage(self, ticket: Ticket) -> TriageOutput:
        expected = self.labels[ticket.ticket_id]
        output = make_output(ticket.ticket_id, expected.urgency[0], expected.action[0])
        if ticket.ticket_id == self.miss:
            output.triage.action = Action.AUTO_RESPOND
        return output


def _run_eval_script():
    spec = importlib.util.spec_from_file_location("run_eval", Path("scripts/run_eval.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_script_reports_metrics_and_passes_the_gate(labels, capsys) -> None:
    code = _run_eval_script().main(["--runs", "2"], service=LabelledFakeService(labels))
    out = capsys.readouterr().out
    assert code == 0
    assert "Safety gate: PASSED" in out and "consistency" in out and "T-3004" in out


def test_eval_script_fails_when_an_escalation_is_missed(labels, capsys) -> None:
    code = _run_eval_script().main(["--json"], service=LabelledFakeService(labels, miss="T-1001"))
    report = json.loads(capsys.readouterr().out)
    assert code == 1 and report["passed"] is False
    [t1001] = [f["failed"] for f in report["failures"] if f["ticket_id"] == "T-1001"]
    assert all(f["run"] == 1 for f in report["failures"])
    assert {"escalation", "safe_auto_respond"} <= set(t1001)
    assert report["metrics"]["escalation_accuracy"] < 1


def test_eval_script_saves_the_report(labels, tmp_path, monkeypatch, capsys) -> None:
    script = _run_eval_script()
    monkeypatch.setattr(script, "RESULTS_DIR", tmp_path)
    assert script.main(["--save"], service=LabelledFakeService(labels)) == 0
    [saved] = tmp_path.glob("*.json")
    report = json.loads(saved.read_text())
    assert report["run"]["tickets"] == len(labels) and report["passed"] is True
    markdown = saved.with_suffix(".md").read_text()
    assert "**Safety gate: PASSED**" in markdown and "| T-3022 |" in markdown
    html = saved.with_suffix(".html").read_text()
    assert "__REPORT_DATA__" not in html and '"id": "T-3022"' in html
