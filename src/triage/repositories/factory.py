"""Builds the repositories the app runs with, based on settings."""

from triage.config import Settings
from triage.repositories.base import Repositories
from triage.repositories.file import build_file_repositories


def build_repositories(settings: Settings) -> Repositories:
    if settings.repository_backend == "postgres":
        # Imported lazily so the file backend works without the database libraries loaded.
        from triage.repositories.postgres import build_postgres_repositories

        return build_postgres_repositories(settings)
    return build_file_repositories(settings.data_dir)
