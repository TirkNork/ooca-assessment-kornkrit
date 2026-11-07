from pathlib import Path

import pytest

from triage.config import get_settings


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return get_settings().data_dir
