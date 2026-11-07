"""Which team owns a ticket, derived deterministically from its issue types."""

from triage.models import IssueType, Team

# Checked in order: the first matching issue type decides the team. Billing comes first because
# only the billing team can move money (refunds, voided charges); a platform incident behind a
# billing problem is already owned by the incident process.
_TEAM_BY_ISSUE: tuple[tuple[IssueType, Team], ...] = (
    (IssueType.BILLING, Team.BILLING),
    (IssueType.OUTAGE, Team.ENGINEERING_ONCALL),
    (IssueType.BUG, Team.TECHNICAL_SUPPORT),
    (IssueType.ACCOUNT_ACCESS, Team.TECHNICAL_SUPPORT),
    (IssueType.FEATURE_REQUEST, Team.PRODUCT),
)


def assign_team(issue_types: list[IssueType]) -> Team:
    for issue_type, team in _TEAM_BY_ISSUE:
        if issue_type in issue_types:
            return team
    return Team.TECHNICAL_SUPPORT
