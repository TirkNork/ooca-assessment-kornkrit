"""Enumerations shared across the triage domain.

`Urgency` and `Action` are ordered by severity so policy rules can *raise* a value
(e.g. "at least high") without hard-coding comparisons everywhere.
"""

from enum import StrEnum
from typing import Self


class _Ranked(StrEnum):
    """StrEnum whose members are ordered by declaration (first = least severe)."""

    @property
    def rank(self) -> int:
        return list(type(self)).index(self)

    def at_least(self, other: Self) -> Self:
        """Return the more severe of `self` and `other`."""
        return self if self.rank >= other.rank else other


class Urgency(_Ranked):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Action(_Ranked):
    AUTO_RESPOND = "auto_respond"
    ROUTE_SPECIALIST = "route_specialist"
    ESCALATE_HUMAN = "escalate_human"


class Product(StrEnum):
    CRM = "crm"
    ERP = "erp"
    ANALYTICS = "analytics"


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class IssueType(StrEnum):
    BILLING = "billing"
    OUTAGE = "outage"
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    USAGE_QUESTION = "usage_question"
    ACCOUNT_ACCESS = "account_access"
    OTHER = "other"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class RiskFlag(StrEnum):
    CHARGEBACK_THREAT = "chargeback_threat"
    DUPLICATE_CHARGES = "duplicate_charges"
    TIME_SENSITIVE = "time_sensitive"
    REVENUE_IMPACT = "revenue_impact"
    WIDESPREAD_OUTAGE = "widespread_outage"


class Team(StrEnum):
    BILLING = "billing"
    TECHNICAL_SUPPORT = "technical_support"
    ENGINEERING_ONCALL = "engineering_oncall"
    PRODUCT = "product"
