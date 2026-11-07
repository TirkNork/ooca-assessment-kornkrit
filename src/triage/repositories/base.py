"""Data-access interfaces.

Tools depend only on these protocols, so the storage backend
can be swapped without touching tools, the graph, or prompts.
"""

from dataclasses import dataclass
from typing import Protocol

from triage.models import BillingAccount, CustomerHistory, CustomerProfile, KBHit, RegionStatus


class CustomerRepository(Protocol):
    def get_profile(self, customer_id: str) -> CustomerProfile | None: ...

    def get_history(self, customer_id: str) -> CustomerHistory | None: ...


class BillingRepository(Protocol):
    def get_account(self, customer_id: str) -> BillingAccount | None: ...


class ServiceStatusRepository(Protocol):
    def get_region(self, region: str) -> RegionStatus | None:
        """Look up a region by name, case-insensitively."""
        ...

    def regions(self) -> list[str]: ...


class KnowledgeBase(Protocol):
    def search(self, query: str, top_k: int) -> list[KBHit]:
        """Return up to `top_k` relevant articles, best first. Empty if nothing matches."""
        ...


@dataclass(frozen=True)
class Repositories:
    customers: CustomerRepository
    billing: BillingRepository
    service_status: ServiceStatusRepository
    knowledge_base: KnowledgeBase
