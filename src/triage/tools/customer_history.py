from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from triage.repositories import CustomerRepository
from triage.tools._results import error, ok


class GetCustomerHistoryInput(BaseModel):
    customer_id: str = Field(description="Customer ID from the ticket, e.g. 'C-1001'.")


def make_get_customer_history(customers: CustomerRepository) -> BaseTool:
    def get_customer_history(customer_id: str) -> str:
        history = customers.get_history(customer_id)
        if history is None:
            return error(f"No customer found with id {customer_id!r}.")
        return ok(history)

    return StructuredTool.from_function(
        func=get_customer_history,
        name="get_customer_history",
        description=(
            "Get a customer's activity summary and past support tickets (with product, urgency "
            "and whether each was resolved). Use it to tell a first contact from a repeat or "
            "unresolved issue."
        ),
        args_schema=GetCustomerHistoryInput,
    )
