"""Eval reports: the same run rendered as JSON, terminal text, Markdown (GitHub) and HTML (a
self-contained dashboard that opens in any browser, with no server or network)."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from importlib.resources import files
from typing import Any

from pydantic import TypeAdapter

from triage.evaluation.scoring import CaseScore, Expected
from triage.models import Ticket, TriageOutput

# name -> (section, label, definition); metrics not listed fall back to the "checks" section.
METRIC_INFO: dict[str, tuple[str, str, str]] = {
    "escalation_accuracy": (
        "safety",
        "Escalation recall",
        "Tickets that must reach a person and were escalated",
    ),
    "safe_auto_respond_accuracy": (
        "safety",
        "Safe auto-replies",
        "Automatic replies sent only where one was acceptable",
    ),
    "under_triage_rate": (
        "safety",
        "Under-triage",
        "Urgency below the lowest acceptable level (lower is better)",
    ),
    "fallback_rate": (
        "safety",
        "Fallback to a person",
        "Runs where the agent failed and handed the ticket over",
    ),
    "urgency_accuracy": ("checks", "Urgency", "Urgency within the accepted levels"),
    "action_accuracy": ("checks", "Action", "Next action among the accepted ones"),
    "issue_types_accuracy": ("checks", "Issue types", "Every labelled issue type found"),
    "products_accuracy": ("checks", "Products", "Every labelled product listed"),
    "kb_accuracy": ("checks", "KB articles", "Every labelled article cited"),
    "tools_accuracy": ("checks", "Tools called", "Every required tool called"),
    "language_accuracy": ("checks", "Language", "Customer language detected"),
    "sentiment_accuracy": ("checks", "Sentiment", "Sentiment within the accepted values"),
    "risk_flag_recall": ("checks", "Risk flag recall", "Required risk flags that were set"),
    "risk_flag_precision": (
        "checks",
        "Risk flag precision",
        "Set flags that were required or defensible",
    ),
    "consistency": (
        "stability",
        "Consistency",
        "Tickets with the same urgency and action in every run",
    ),
    "policy_override_rate": (
        "stability",
        "Policy overrides",
        "Runs where a business rule raised the model's decision",
    ),
    "latency_p50_s": ("cost", "Latency, median (s)", "Median time to triage one ticket"),
    "latency_max_s": ("cost", "Latency, slowest (s)", "Slowest single triage"),
    "tokens_per_ticket": ("cost", "Tokens per ticket", "Average tokens over all LLM calls"),
}


@dataclass(frozen=True)
class EvalRun:
    """Everything one eval run produced, in the order the runs were made."""

    info: dict[str, Any]  # started_at, model, prompt_version, backend, runs_per_ticket, tickets
    tickets: list[Ticket]
    ticket_sets: dict[str, str]  # ticket id -> the file it came from, e.g. "sample_tickets"
    labels: dict[str, Expected]
    outputs: list[TriageOutput]
    scores: list[CaseScore]
    metrics: dict[str, float]
    passed: bool

    @cached_property
    def by_ticket(self) -> dict[str, list[tuple[TriageOutput, CaseScore]]]:
        """Each ticket's runs in run order, tickets in file order."""
        runs: dict[str, list[tuple[TriageOutput, CaseScore]]] = {
            t.ticket_id: [] for t in self.tickets
        }
        for output, case in zip(self.outputs, self.scores, strict=True):
            runs[output.ticket_id].append((output, case))
        return runs


def to_json(run: EvalRun) -> str:
    report = {
        "run": run.info,
        "passed": run.passed,
        "metrics": run.metrics,
        "failures": [
            {"ticket_id": ticket_id, "run": n, "failed": case.failed}
            for ticket_id, results in run.by_ticket.items()
            for n, (_, case) in enumerate(results, 1)
            if case.failed
        ],
        "outputs": TypeAdapter(list[TriageOutput]).dump_python(run.outputs, mode="json"),
    }
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def to_text(run: EvalRun) -> str:
    lines = [f"{'ticket':<8} {'urgency':<9} {'action':<17} failed checks", "-" * 60]
    for output, case in zip(run.outputs, run.scores, strict=True):
        t = output.triage
        lines.append(
            f"{output.ticket_id:<8} {t.urgency:<9} {t.action:<17} {', '.join(case.failed)}"
        )
    lines += ["", "Metrics:"]
    lines += [f"  {name:<26} {format_metric(name, v)}" for name, v in run.metrics.items()]
    lines += ["", "Safety gate: " + ("PASSED" if run.passed else "FAILED")]
    return "\n".join(lines)


def to_markdown(run: EvalRun) -> str:
    """Renders on GitHub, so results can be read without running anything."""
    info = run.info
    lines = [
        f"# Eval report: {info['model']}, prompt v{info['prompt_version']}",
        "",
        f"**Safety gate: {'PASSED' if run.passed else 'FAILED'}** · "
        f"{info['tickets']} tickets x {info['runs_per_ticket']} runs · "
        f"{info['backend']} backend · started {info['started_at']}",
        "",
        "## Metrics",
        "",
        _row("Metric", "Value", "Meaning"),
        _row("---", "---", "---"),
        *(
            _row(_metric_label(name), format_metric(name, v), _metric_definition(name))
            for name, v in run.metrics.items()
        ),
        "",
        "## Decisions",
        "",
        "Accepted values come from the labels; the model's value is shown once when every run",
        "agreed, otherwise one line per run.",
        "",
        _row(
            "Ticket", "Urgency accepted", "Urgency got", "Action accepted", "Action got", "Failed"
        ),
        _row(*["---"] * 6),
    ]
    for ticket_id, results in run.by_ticket.items():
        e, got = run.labels[ticket_id], [o.triage for o, _ in results]
        lines.append(
            _row(
                ticket_id,
                _join(e.urgency),
                _per_run(t.urgency for t in got),
                _join(e.action),
                _per_run(t.action for t in got),
                "<br>".join(_failures(results)) or "-",
            )
        )
    lines += [
        "",
        "## Extraction",
        "",
        "Labelled values must all appear (extra ones are not penalised); `-` means not scored.",
        "Optional risk flags are defensible either way and shown in brackets.",
        "",
        _row(
            "Ticket",
            "Issue types labelled",
            "Issue types got",
            "Products labelled",
            "Products got",
            "Risk flags labelled",
            "Risk flags got",
            "KB labelled",
            "KB got",
            "Language labelled / got",
        ),
        _row(*["---"] * 10),
    ]
    for ticket_id, results in run.by_ticket.items():
        e, got = run.labels[ticket_id], [o.triage for o, _ in results]
        optional = f" ({_join(e.optional_risk_flags)})" if e.optional_risk_flags else ""
        lines.append(
            _row(
                ticket_id,
                _join(e.issue_types),
                _per_run(_join(sorted(t.issue_types)) for t in got),
                _join(e.products),
                _per_run(_join(sorted(t.products)) for t in got),
                _join(e.risk_flags) + optional,
                _per_run(_join(sorted(t.risk_flags)) for t in got),
                _join(e.kb_article_ids),
                _per_run(_join(sorted(t.kb_article_ids)) for t in got),
                f"{e.language or '-'} / {_per_run(t.language for t in got)}",
            )
        )
    return "\n".join(lines) + "\n"


def to_html(run: EvalRun) -> str:
    """A single-file dashboard: the template plus this run's data embedded as JSON."""
    tickets = {t.ticket_id: t for t in run.tickets}
    data = {
        "info": run.info,
        "passed": run.passed,
        "metrics": [
            {
                "name": name,
                "section": METRIC_INFO.get(name, ("checks",))[0],
                "label": _metric_label(name),
                "definition": _metric_definition(name),
                "value": value,
                "display": format_metric(name, value),
            }
            for name, value in run.metrics.items()
        ],
        "tickets": [
            {
                "id": ticket_id,
                "set": run.ticket_sets.get(ticket_id, ""),
                "customer_id": tickets[ticket_id].customer_id,
                "message": tickets[ticket_id].messages[0].content,
                "expected": run.labels[ticket_id].model_dump(mode="json"),
                "runs": [
                    {
                        **o.triage.model_dump(
                            mode="json", exclude={"summary", "reasoning", "kb_article_ids"}
                        ),
                        "summary": o.triage.summary,
                        "kb_article_ids": sorted(o.triage.kb_article_ids),
                        "failed": case.failed,
                        "policy_overrides": o.policy_overrides,
                        "fallback_reason": o.fallback_reason,
                        "latency_s": round(o.metadata.latency_ms / 1000, 1),
                    }
                    for o, case in results
                ],
            }
            for ticket_id, results in run.by_ticket.items()
        ],
    }
    # "</" would let a value close the <script> tag that holds the data.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    template = files(__package__).joinpath("report.html").read_text(encoding="utf-8")
    return template.replace("__REPORT_DATA__", payload)


def format_metric(name: str, value: float) -> str:
    return f"{value:,.1f}" if name.startswith(("latency", "tokens")) else f"{value:.0%}"


def _failures(results: list[tuple[TriageOutput, CaseScore]]) -> list[str]:
    return [f"run {n}: {', '.join(c.failed)}" for n, (_, c) in enumerate(results, 1) if c.failed]


def _metric_label(name: str) -> str:
    return METRIC_INFO[name][1] if name in METRIC_INFO else name


def _metric_definition(name: str) -> str:
    return METRIC_INFO[name][2] if name in METRIC_INFO else ""


def _row(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |"


def _join(values: Iterable[object]) -> str:
    return ", ".join(str(v) for v in values) or "-"


def _per_run(values: Iterable[object]) -> str:
    """One value when every run agreed, otherwise each run's value in order."""
    texts = [str(v) for v in values]
    if len(set(texts)) == 1:
        return texts[0]
    return "<br>".join(f"{n}: {text}" for n, text in enumerate(texts, 1))
