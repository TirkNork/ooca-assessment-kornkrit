"""Customer data.

The profile is small and needed for every ticket, so it is loaded up-front. History can be large
in a real system, so the agent fetches it on demand through a tool.
"""

from datetime import date

from pydantic import AwareDatetime, BaseModel, Field

from triage.models.enums import Plan, Product, Urgency


class ProductSubscription(BaseModel):
    product: Product
    since: date


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    plan: Plan
    region: str = Field(description="Service region the account is hosted in, e.g. 'asia'.")
    seats: int = Field(ge=1)
    customer_since: date
    products: list[ProductSubscription] = Field(min_length=1)


class PastTicket(BaseModel):
    opened_at: AwareDatetime
    product: Product
    summary: str
    urgency: Urgency
    resolved: bool


class CustomerHistory(BaseModel):
    customer_id: str
    activity_summary: str
    past_tickets: list[PastTicket] = Field(default_factory=list)
