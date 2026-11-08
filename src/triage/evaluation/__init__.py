"""Offline evaluation: score triage runs against labels and report the results."""

from triage.evaluation.report import EvalRun, to_html, to_json, to_markdown, to_text
from triage.evaluation.scoring import (
    SAFETY_CHECKS,
    CaseScore,
    Expected,
    consistency,
    safety_gate_passed,
    score,
    summarize,
)

__all__ = [
    "SAFETY_CHECKS",
    "CaseScore",
    "EvalRun",
    "Expected",
    "consistency",
    "safety_gate_passed",
    "score",
    "summarize",
    "to_html",
    "to_json",
    "to_markdown",
    "to_text",
]
