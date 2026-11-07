"""Builds the repositories the app runs with, based on settings."""

from triage.config import Settings
from triage.repositories.base import Repositories
from triage.repositories.file import build_file_repositories


def build_repositories(settings: Settings) -> Repositories:
    # Only the file backend exists for now; a Postgres backend is selected here once it lands.
    return build_file_repositories(settings.data_dir)
