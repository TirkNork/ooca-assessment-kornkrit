from pathlib import Path

import pytest

from triage.config import get_settings
from triage.repositories import Repositories
from triage.repositories.file import build_file_repositories


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return get_settings().data_dir


@pytest.fixture(scope="session")
def repositories(data_dir: Path) -> Repositories:
    return build_file_repositories(data_dir)
