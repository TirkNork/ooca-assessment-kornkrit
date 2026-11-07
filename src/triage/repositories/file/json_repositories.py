"""Repositories backed by JSON files, loaded into memory once."""

from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from triage.models import BillingAccount, CustomerHistory, CustomerProfile, RegionStatus


def load_records[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    """Load a JSON file holding a list of `model` records."""
    return TypeAdapter(list[model]).validate_json(path.read_bytes())


class JsonCustomerRepository:
    def __init__(self, data_dir: Path) -> None:
        profiles = load_records(data_dir / "customers.json", CustomerProfile)
        histories = load_records(data_dir / "customer_history.json", CustomerHistory)
        self._profiles = {p.customer_id: p for p in profiles}
        self._histories = {h.customer_id: h for h in histories}

    def get_profile(self, customer_id: str) -> CustomerProfile | None:
        return self._profiles.get(customer_id)

    def get_history(self, customer_id: str) -> CustomerHistory | None:
        return self._histories.get(customer_id)


class JsonBillingRepository:
    def __init__(self, data_dir: Path) -> None:
        accounts = load_records(data_dir / "billing.json", BillingAccount)
        self._accounts = {a.customer_id: a for a in accounts}

    def get_account(self, customer_id: str) -> BillingAccount | None:
        return self._accounts.get(customer_id)


class JsonServiceStatusRepository:
    def __init__(self, data_dir: Path) -> None:
        regions = load_records(data_dir / "service_status.json", RegionStatus)
        self._regions = {r.region.lower(): r for r in regions}

    def get_region(self, region: str) -> RegionStatus | None:
        return self._regions.get(region.strip().lower())

    def regions(self) -> list[str]:
        return sorted(self._regions)
