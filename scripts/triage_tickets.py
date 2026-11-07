"""Triage tickets from a JSON file and print the results.

    python scripts/triage_tickets.py data/sample_tickets.json
    python scripts/triage_tickets.py data/sample_tickets.json --ticket T-1001 --json

The file holds a JSON list of tickets (see data/sample_tickets.json). Results go to stdout,
logs to stderr.
"""

import argparse
import sys
from pathlib import Path

from pydantic import TypeAdapter

from triage.config import configure_logging, get_settings
from triage.models import Ticket, TriageOutput
from triage.service import TriageService, build_service


def main(argv: list[str] | None = None, service: TriageService | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickets_file", type=Path, help="JSON file with a list of tickets")
    parser.add_argument("--ticket", action="append", help="only this ticket id (repeatable)")
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(argv)

    tickets = TypeAdapter(list[Ticket]).validate_json(args.tickets_file.read_bytes())
    if args.ticket:
        unknown = set(args.ticket) - {t.ticket_id for t in tickets}
        if unknown:
            parser.error(f"unknown ticket id(s): {', '.join(sorted(unknown))}")
        tickets = [t for t in tickets if t.ticket_id in args.ticket]

    configure_logging(get_settings().log_level)
    service = service or build_service()
    outputs = [service.triage(ticket) for ticket in tickets]

    if args.json:
        print(TypeAdapter(list[TriageOutput]).dump_json(outputs, indent=2).decode())
    else:
        print("\n\n".join(format_output(output) for output in outputs))
    return 0


def format_output(output: TriageOutput) -> str:
    t, meta = output.triage, output.metadata

    def join(values: list) -> str:
        return ", ".join(str(v) for v in values) or "-"

    team = f" -> {output.assigned_team}" if output.assigned_team else ""
    lines = [
        f"=== {output.ticket_id} " + "=" * 60,
        f"Action:     {t.action}{team}",
        f"Urgency:    {t.urgency}    Sentiment: {t.sentiment}    Language: {t.language}",
        f"Products:   {join(t.products)}    Issues: {join(t.issue_types)}",
        f"Risk flags: {join(t.risk_flags)}",
        f"KB:         {join(t.kb_article_ids)}",
        f"Summary:    {t.summary}",
        f"Reasoning:  {t.reasoning}",
    ]
    if output.policy_overrides:
        lines += ["Policy overrides:", *(f"  - {o}" for o in output.policy_overrides)]
    if output.fallback_reason:
        lines.append(f"FALLBACK:   {output.fallback_reason}")
    if output.handoff_summary:
        lines += ["--- Handoff summary ---", output.handoff_summary]
    if output.suggested_reply:
        lines += ["--- Suggested reply ---", output.suggested_reply]
    lines.append(
        f"(trace {meta.trace_id}, {meta.model}, {meta.latency_ms / 1000:.1f}s, "
        f"{meta.total_tokens:,} tokens, tools: {join(meta.tool_calls)})"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
