"""Tools the triage agent can call. Each is built from a repository, so data access is injected."""

from langchain_core.tools import BaseTool

from triage.repositories import Repositories
from triage.tools.billing import make_get_billing_transactions
from triage.tools.customer_history import make_get_customer_history
from triage.tools.knowledge_base import make_search_knowledge_base
from triage.tools.service_status import make_check_service_status


def build_tools(repositories: Repositories) -> list[BaseTool]:
    return [
        make_get_customer_history(repositories.customers),
        make_search_knowledge_base(repositories.knowledge_base),
        make_check_service_status(repositories.service_status),
        make_get_billing_transactions(repositories.billing),
    ]


__all__ = ["build_tools"]
