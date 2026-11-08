from pathlib import Path

import pytest

from triage.config import get_settings
from triage.repositories import Repositories
from triage.repositories.file import build_file_repositories

SAMPLE_TICKETS = Path("data/sample_tickets.json")


@pytest.fixture(scope="session")
def sample_tickets_path() -> Path:
    return SAMPLE_TICKETS


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """The mock data the tools read (customers, billing, status, KB)."""
    return get_settings().data_dir


@pytest.fixture(scope="session")
def repositories(data_dir: Path) -> Repositories:
    return build_file_repositories(data_dir)
