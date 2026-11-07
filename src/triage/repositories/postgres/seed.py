"""Loads the JSON data and KB articles into Postgres and embeds the KB.

Idempotent: every run replaces the data with what is in `data/`. Embeddings are reused for chunks
whose text and embedding model are unchanged, so re-seeding does not pay for them again.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from triage.embeddings import Embedder
from triage.models import (
    BillingAccount,
    CustomerHistory,
    CustomerProfile,
    KBArticle,
    RegionStatus,
)
from triage.repositories.file.json_repositories import load_records
from triage.repositories.kb_markdown import load_articles
from triage.repositories.postgres.schema import (
    Base,
    BillingAccountRow,
    CustomerHistoryRow,
    CustomerRow,
    IncidentRow,
    KBArticleRow,
    KBChunkRow,
    RegionStatusRow,
    TransactionRow,
)


@dataclass(frozen=True)
class SeedReport:
    customers: int
    articles: int
    chunks: int
    newly_embedded: int


def create_schema(engine: Engine, reset: bool = False) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_database(
    engine: Engine, data_dir: Path, embedder: Embedder, embedding_model: str
) -> SeedReport:
    customers = load_records(data_dir / "customers.json", CustomerProfile)
    histories = load_records(data_dir / "customer_history.json", CustomerHistory)
    accounts = load_records(data_dir / "billing.json", BillingAccount)
    regions = load_records(data_dir / "service_status.json", RegionStatus)
    articles = load_articles(data_dir / "kb")

    with Session(engine) as session, session.begin():
        rows = session.execute(select(KBChunkRow.content_hash, KBChunkRow.embedding))
        known_embeddings = {content_hash: list(vector) for content_hash, vector in rows}
        # Children before parents, so foreign keys are never violated.
        for table in (KBChunkRow, KBArticleRow, TransactionRow, BillingAccountRow,
                      CustomerHistoryRow, IncidentRow, RegionStatusRow, CustomerRow):  # fmt: skip
            session.execute(delete(table))
        session.flush()

        session.add_all(_customer_row(c) for c in customers)
        session.flush()
        session.add_all(_history_row(h) for h in histories)
        session.add_all(_billing_row(a) for a in accounts)
        session.add_all(_region_row(r) for r in regions)
        session.add_all(KBArticleRow(**a.model_dump()) for a in articles)
        session.flush()

        chunks = [chunk for a in articles for chunk in _chunks(a, embedding_model)]
        missing = [c for c in chunks if c.content_hash not in known_embeddings]
        if missing:
            vectors = embedder.embed_documents([_embedding_text(c) for c in missing])
            known_embeddings |= {c.content_hash: v for c, v in zip(missing, vectors, strict=True)}
        for chunk in chunks:
            chunk.embedding = known_embeddings[chunk.content_hash]
        session.add_all(chunks)

    return SeedReport(
        customers=len(customers),
        articles=len(articles),
        chunks=len(chunks),
        newly_embedded=len(missing),
    )


def split_paragraphs(body: str) -> list[str]:
    return [" ".join(p.split()) for p in body.split("\n\n") if p.strip()]


def _chunks(article: KBArticle, embedding_model: str) -> list[KBChunkRow]:
    return [
        KBChunkRow(
            article_id=article.article_id,
            chunk_index=i,
            title=article.title,
            content=paragraph,
            content_hash=hashlib.sha256(
                f"{embedding_model}\n{article.title}\n{paragraph}".encode()
            ).hexdigest(),
        )
        for i, paragraph in enumerate(split_paragraphs(article.body))
    ]


def _embedding_text(chunk: KBChunkRow) -> str:
    # The title gives a short paragraph the context it needs to be found.
    return f"{chunk.title}\n\n{chunk.content}"


def _customer_row(c: CustomerProfile) -> CustomerRow:
    return CustomerRow(
        **c.model_dump(exclude={"products"}),
        products=[p.model_dump(mode="json") for p in c.products],
    )


def _history_row(h: CustomerHistory) -> CustomerHistoryRow:
    return CustomerHistoryRow(
        customer_id=h.customer_id,
        activity_summary=h.activity_summary,
        past_tickets=[t.model_dump(mode="json") for t in h.past_tickets],
    )


def _billing_row(a: BillingAccount) -> BillingAccountRow:
    return BillingAccountRow(
        customer_id=a.customer_id,
        subscription_status=a.subscription_status,
        transactions=[TransactionRow(**t.model_dump()) for t in a.transactions],
    )


def _region_row(r: RegionStatus) -> RegionStatusRow:
    return RegionStatusRow(
        region=r.region.lower(),
        status=r.status,
        public_status=r.public_status,
        active_incidents=[IncidentRow(**i.model_dump()) for i in r.active_incidents],
    )
