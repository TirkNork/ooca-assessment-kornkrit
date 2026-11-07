from dataclasses import dataclass

from triage.models import TriageResult
from triage.policy.rules import DEFAULT_RULES, PolicyContext, Rule


@dataclass(frozen=True)
class PolicyResult:
    triage: TriageResult
    overrides: list[str]


class PolicyEngine:
    def __init__(self, rules: tuple[Rule, ...] = DEFAULT_RULES) -> None:
        self._rules = rules

    def apply(self, ctx: PolicyContext) -> PolicyResult:
        """Evaluate every rule against the LLM's triage and raise urgency/action to the highest
        floor any rule requires. Each change is described in `overrides` for auditing."""
        triage = ctx.triage
        overrides: list[str] = []
        for requirement in filter(None, (rule(ctx) for rule in self._rules)):
            changes = {}
            if requirement.min_urgency:
                changes["urgency"] = triage.urgency.at_least(requirement.min_urgency)
            if requirement.min_action:
                changes["action"] = triage.action.at_least(requirement.min_action)
            changed = {k: v for k, v in changes.items() if v != getattr(triage, k)}
            if not changed:
                continue
            diff = ", ".join(f"{k} {getattr(triage, k)} -> {v}" for k, v in changed.items())
            overrides.append(f"{requirement.rule}: {diff} ({requirement.reason})")
            triage = triage.model_copy(update=changed)
        return PolicyResult(triage=triage, overrides=overrides)
