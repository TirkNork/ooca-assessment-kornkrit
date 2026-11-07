"""Billing records returned by the billing tool."""

from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field


class TransactionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class Transaction(BaseModel):
    transaction_id: str
    created_at: AwareDatetime
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217 code, e.g. 'USD'.")
    status: TransactionStatus
    failure_reason: str | None = None


class BillingAccount(BaseModel):
    customer_id: str
    subscription_status: str = Field(description="e.g. 'active', 'upgrade_pending', 'past_due'.")
    transactions: list[Transaction] = Field(default_factory=list)
