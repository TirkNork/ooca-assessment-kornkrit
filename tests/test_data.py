"""Mock data files must match the domain models and reference each other consistently."""

from pathlib import Path

import pytest
from pydantic import TypeAdapter

from triage.models import BillingAccount, CustomerHistory, CustomerProfile, RegionStatus, Ticket


def _load[T](path: Path, model: type[T]) -> list[T]:
    return TypeAdapter(list[model]).validate_json(path.read_bytes())


@pytest.fixture(scope="module")
def tickets(data_dir: Path) -> list[Ticket]:
    return _load(data_dir / "sample_tickets.json", Ticket)


@pytest.fixture(scope="module")
def customer_ids(data_dir: Path) -> set[str]:
    return {c.customer_id for c in _load(data_dir / "customers.json", CustomerProfile)}


def test_sample_tickets_load(tickets: list[Ticket]) -> None:
    assert [t.ticket_id for t in tickets] == ["T-1001", "T-1002", "T-1003"]


def test_every_ticket_references_a_known_customer(
    tickets: list[Ticket], customer_ids: set[str]
) -> None:
    assert {t.customer_id for t in tickets} <= customer_ids


@pytest.mark.parametrize(
    ("file_name", "model"),
    [("customer_history.json", CustomerHistory), ("billing.json", BillingAccount)],
)
def test_every_customer_has_a_record(
    data_dir: Path, customer_ids: set[str], file_name: str, model: type
) -> None:
    records = _load(data_dir / file_name, model)
    assert {r.customer_id for r in records} == customer_ids


def test_every_customer_region_has_a_status(data_dir: Path) -> None:
    customers = _load(data_dir / "customers.json", CustomerProfile)
    regions = _load(data_dir / "service_status.json", RegionStatus)
    assert {c.region for c in customers} <= {r.region for r in regions}


def test_kb_articles_have_front_matter_matching_file_name(data_dir: Path) -> None:
    articles = sorted((data_dir / "kb").glob("*.md"))
    assert len(articles) >= 8
    for path in articles:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "---", path.name
        article_id = next(line.split(":", 1)[1].strip() for line in lines if line.startswith("id:"))
        assert path.name.startswith(f"{article_id}-"), path.name


def test_past_tickets_only_reference_products_the_customer_uses(data_dir: Path) -> None:
    customers = {
        c.customer_id: {s.product for s in c.products}
        for c in _load(data_dir / "customers.json", CustomerProfile)
    }
    for history in _load(data_dir / "customer_history.json", CustomerHistory):
        for ticket in history.past_tickets:
            assert ticket.product in customers[history.customer_id]
