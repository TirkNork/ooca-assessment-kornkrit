from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from triage.repositories import BillingRepository
from triage.tools._results import error, ok


class GetBillingTransactionsInput(BaseModel):
    customer_id: str = Field(description="Customer ID from the ticket, e.g. 'C-1001'.")


def make_get_billing_transactions(billing: BillingRepository) -> BaseTool:
    def get_billing_transactions(customer_id: str) -> str:
        account = billing.get_account(customer_id)
        if account is None:
            return error(f"No billing account found for customer {customer_id!r}.")
        return ok(account)

    return StructuredTool.from_function(
        func=get_billing_transactions,
        name="get_billing_transactions",
        description=(
            "Get a customer's subscription status and payment transactions (amount, currency, "
            "status, failure reason). Use it for payment, charge, refund or upgrade issues."
        ),
        args_schema=GetBillingTransactionsInput,
    )
