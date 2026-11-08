"""Run the agent on labelled tickets with the real LLM and report quality metrics.

    python scripts/run_eval.py                       # all labelled tickets, once
    python scripts/run_eval.py --runs 3              # also measures consistency across runs
    python scripts/run_eval.py --save                # also writes JSON, Markdown and HTML
    python scripts/run_eval.py --backend postgres --json > report.json

Exits with 1 when a safety check fails: a ticket that must reach a human was not escalated, or a
ticket was auto-responded that should not be. Unit tests (pytest) need no API key; this does.
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter

from triage.config import configure_logging, get_settings
from triage.evaluation import (
    EvalRun,
    Expected,
    safety_gate_passed,
    score,
    summarize,
    to_html,
    to_json,
    to_markdown,
    to_text,
)
from triage.models import Ticket
from triage.prompts import PROMPT_VERSION
from triage.service import TriageService, build_service

DEFAULT_TICKET_FILES = [
    Path("data/sample_tickets.json"),
    Path("data/test_set.json"),
]
RESULTS_DIR = Path("evals/results")


def main(argv: list[str] | None = None, service: TriageService | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ticket_files", nargs="*", type=Path, default=DEFAULT_TICKET_FILES)
    parser.add_argument("--labels", type=Path, default=Path("data/eval_labels.json"))
    parser.add_argument("--runs", type=int, default=1, help="runs per ticket (default 1)")
    parser.add_argument("--concurrency", type=int, default=4, help="tickets in parallel")
    parser.add_argument("--backend", choices=["file", "postgres"], help="override the backend")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--save", action="store_true", help=f"write the report to {RESULTS_DIR}/")
    args = parser.parse_args(argv)

    ticket_sets: dict[str, str] = {}
    tickets: list[Ticket] = []
    for path in args.ticket_files:
        for ticket in TypeAdapter(list[Ticket]).validate_json(path.read_bytes()):
            tickets.append(ticket)
            ticket_sets[ticket.ticket_id] = path.stem
    labels = TypeAdapter(dict[str, Expected]).validate_json(args.labels.read_bytes())
    unlabelled = {t.ticket_id for t in tickets} - labels.keys()
    if unlabelled:
        parser.error(f"tickets without labels: {', '.join(sorted(unlabelled))}")

    settings = get_settings()
    if args.backend:
        settings = settings.model_copy(update={"repository_backend": args.backend})
    configure_logging(settings.log_level)
    service = service or build_service(settings)

    started_at = datetime.now(UTC)
    jobs = [ticket for _ in range(args.runs) for ticket in tickets]
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        outputs = list(pool.map(service.triage, jobs))
    scores = [score(output, labels[output.ticket_id]) for output in outputs]
    metrics = summarize(scores, outputs)
    run = EvalRun(
        info={
            "started_at": started_at.isoformat(timespec="seconds"),
            "model": settings.openai_model,
            "prompt_version": PROMPT_VERSION,
            "backend": settings.repository_backend,
            "runs_per_ticket": args.runs,
            "tickets": len(tickets),
        },
        tickets=tickets,
        ticket_sets=ticket_sets,
        labels=labels,
        outputs=outputs,
        scores=scores,
        metrics=metrics,
        passed=safety_gate_passed(metrics),
    )

    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
        base = RESULTS_DIR / (
            f"{stamp}_{settings.openai_model}_prompt-v{PROMPT_VERSION}_{settings.repository_backend}"
        )
        for suffix, render in ((".json", to_json), (".md", to_markdown), (".html", to_html)):
            base.with_suffix(suffix).write_text(render(run), encoding="utf-8")
        print(f"Report saved to {base}.{{json,md,html}}", file=sys.stderr)

    print(to_json(run) if args.json else to_text(run))
    return 0 if run.passed else 1


if __name__ == "__main__":
    sys.exit(main())
