"""File-based backend: JSON data + BM25 over Markdown KB articles."""

from pathlib import Path

from triage.repositories.base import Repositories
from triage.repositories.file.bm25_knowledge_base import Bm25KnowledgeBase
from triage.repositories.file.json_repositories import (
    JsonBillingRepository,
    JsonCustomerRepository,
    JsonServiceStatusRepository,
)
from triage.repositories.kb_markdown import load_articles


def build_file_repositories(data_dir: Path) -> Repositories:
    return Repositories(
        customers=JsonCustomerRepository(data_dir),
        billing=JsonBillingRepository(data_dir),
        service_status=JsonServiceStatusRepository(data_dir),
        knowledge_base=Bm25KnowledgeBase(load_articles(data_dir / "kb")),
    )


__all__ = [
    "Bm25KnowledgeBase",
    "JsonBillingRepository",
    "JsonCustomerRepository",
    "JsonServiceStatusRepository",
    "build_file_repositories",
]
