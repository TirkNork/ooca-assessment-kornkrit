"""Postgres + pgvector backend. Seed it with scripts/seed_db.py before use."""

from sqlalchemy import inspect

from triage.config import Settings
from triage.embeddings import build_embedder
from triage.repositories.base import Repositories
from triage.repositories.postgres.db import DatabaseNotReadyError, create_db_engine
from triage.repositories.postgres.knowledge_base import PgVectorKnowledgeBase
from triage.repositories.postgres.repositories import (
    SqlBillingRepository,
    SqlCustomerRepository,
    SqlServiceStatusRepository,
)


def build_postgres_repositories(settings: Settings) -> Repositories:
    engine = create_db_engine(settings.database_url)
    if not inspect(engine).has_table("kb_chunks"):
        raise DatabaseNotReadyError("Database is not seeded: run `python scripts/seed_db.py`.")
    return Repositories(
        customers=SqlCustomerRepository(engine),
        billing=SqlBillingRepository(engine),
        service_status=SqlServiceStatusRepository(engine),
        knowledge_base=PgVectorKnowledgeBase(
            engine, build_embedder(settings), settings.kb_min_similarity
        ),
    )


__all__ = ["DatabaseNotReadyError", "build_postgres_repositories"]
