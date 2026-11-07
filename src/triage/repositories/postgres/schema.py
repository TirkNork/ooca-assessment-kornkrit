"""Database tables. Small nested lists (products, past tickets) are stored as JSONB; transactions,
incidents and KB chunks are their own tables because they are queried or indexed on their own."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from triage.embeddings import EMBEDDING_DIMENSIONS


class Base(DeclarativeBase):
    pass


class CustomerRow(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    plan: Mapped[str]
    region: Mapped[str]
    seats: Mapped[int]
    customer_since: Mapped[date]
    products: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)


class CustomerHistoryRow(Base):
    __tablename__ = "customer_history"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    activity_summary: Mapped[str] = mapped_column(Text)
    past_tickets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)


class BillingAccountRow(Base):
    __tablename__ = "billing_accounts"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    subscription_status: Mapped[str]
    transactions: Mapped[list["TransactionRow"]] = relationship(
        order_by="TransactionRow.created_at", cascade="all, delete-orphan"
    )


class TransactionRow(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.customer_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str]
    failure_reason: Mapped[str | None]


class RegionStatusRow(Base):
    __tablename__ = "region_status"

    region: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str]
    public_status: Mapped[str]
    active_incidents: Mapped[list["IncidentRow"]] = relationship(
        order_by="IncidentRow.started_at", cascade="all, delete-orphan"
    )


class IncidentRow(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String, primary_key=True)
    region: Mapped[str] = mapped_column(ForeignKey("region_status.region"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str]


class KBArticleRow(Base):
    __tablename__ = "kb_articles"

    article_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str]
    body: Mapped[str] = mapped_column(Text)


class KBChunkRow(Base):
    """One paragraph of an article, with its embedding and a weighted full-text vector."""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("kb_articles.article_id"), index=True)
    chunk_index: Mapped[int]
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', title), 'A') || "
            "setweight(to_tsvector('english', content), 'B')",
            persisted=True,
        ),
    )

    __table_args__ = (
        Index(
            "kb_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("kb_chunks_search_vector_gin", "search_vector", postgresql_using="gin"),
    )
