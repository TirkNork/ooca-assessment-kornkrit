"""Postgres backend: the same data must come back as from the file backend, and hybrid search must
find the same articles. Runs against a separate `<db>_test` database; skipped without a database."""

import os
from collections.abc import Iterator

import pytest
from fakes import HashingEmbedder
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from test_kb_retrieval import RETRIEVAL_CASES

from triage.repositories import Repositories
from triage.repositories.postgres import (
    DatabaseNotReadyError,
    build_postgres_repositories,
)
from triage.repositories.postgres.knowledge_base import (
    PgVectorKnowledgeBase,
    reciprocal_rank_fusion,
)
from triage.repositories.postgres.repositories import (
    SqlBillingRepository,
    SqlCustomerRepository,
    SqlServiceStatusRepository,
)
from triage.repositories.postgres.seed import create_schema, seed_database, split_paragraphs
from triage.tools import build_tools

EMBEDDING_MODEL = "hashing-test"

# --- pure helpers (no database) -------------------------------------------------------------


def test_reciprocal_rank_fusion_rewards_items_found_by_both_searches() -> None:
    scores = reciprocal_rank_fusion([[1, 2, 3], [3, 4]], k=60)
    assert max(scores, key=scores.__getitem__) == 3
    assert scores[1] > scores[2] == scores[4]  # both 2nd in their ranking


def test_split_paragraphs_normalizes_whitespace() -> None:
    assert split_paragraphs("One\nline.\n\n\n  Two  words. \n\n") == ["One line.", "Two words."]


def test_postgres_backend_needs_a_database_url(data_dir) -> None:
    from triage.config import Settings

    with pytest.raises(DatabaseNotReadyError, match="DATABASE_URL"):
        build_postgres_repositories(Settings(_env_file=None, database_url=None))


# --- integration ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set")
    test_url = make_url(url).set(database=f"{make_url(url).database}_test")
    try:
        admin = create_engine(url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_url.database},
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
        admin.dispose()
    except OperationalError:
        pytest.skip("database is not reachable")

    test_engine = create_engine(test_url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="module")
def embedder() -> HashingEmbedder:
    return HashingEmbedder()


@pytest.fixture(scope="module")
def seeded(engine: Engine, data_dir, embedder: HashingEmbedder):
    create_schema(engine, reset=True)
    return seed_database(engine, data_dir, embedder, EMBEDDING_MODEL)


@pytest.fixture(scope="module")
def sql(engine: Engine, seeded, embedder: HashingEmbedder) -> Repositories:
    return Repositories(
        customers=SqlCustomerRepository(engine),
        billing=SqlBillingRepository(engine),
        service_status=SqlServiceStatusRepository(engine),
        knowledge_base=PgVectorKnowledgeBase(engine, embedder, min_similarity=0.3),
    )


@pytest.mark.integration
def test_seed_loads_everything(seeded, data_dir) -> None:
    assert (seeded.customers, seeded.articles) == (3, 10)
    assert seeded.chunks == seeded.newly_embedded > seeded.articles


@pytest.mark.integration
def test_reseeding_reuses_unchanged_embeddings(engine: Engine, seeded, data_dir) -> None:
    counting = HashingEmbedder()
    report = seed_database(engine, data_dir, counting, EMBEDDING_MODEL)
    assert report.chunks == seeded.chunks
    assert report.newly_embedded == counting.embedded_texts == 0


@pytest.mark.integration
@pytest.mark.parametrize("customer_id", ["C-1001", "C-2001", "C-3001", "C-9999"])
def test_customer_and_billing_data_match_the_file_backend(
    sql: Repositories, repositories: Repositories, customer_id: str
) -> None:
    assert sql.customers.get_profile(customer_id) == repositories.customers.get_profile(customer_id)
    assert sql.customers.get_history(customer_id) == repositories.customers.get_history(customer_id)
    assert sql.billing.get_account(customer_id) == repositories.billing.get_account(customer_id)


@pytest.mark.integration
@pytest.mark.parametrize("region", ["asia", " Asia ", "us", "eu", "mars"])
def test_service_status_matches_the_file_backend(
    sql: Repositories, repositories: Repositories, region: str
) -> None:
    assert sql.service_status.get_region(region) == repositories.service_status.get_region(region)
    assert sql.service_status.regions() == repositories.service_status.regions()


@pytest.mark.integration
@pytest.mark.parametrize(("query", "expected_article"), RETRIEVAL_CASES)
def test_hybrid_search_finds_the_expected_article(
    sql: Repositories, query: str, expected_article: str
) -> None:
    hits = sql.knowledge_base.search(query, top_k=3)
    assert expected_article in [h.article_id for h in hits]


@pytest.mark.integration
def test_hybrid_search_returns_whole_short_articles_and_nothing_for_noise(
    sql: Repositories,
) -> None:
    [hit, *_] = sql.knowledge_base.search("dark mode system default macOS", top_k=3)
    assert hit.article_id == "KB-020" and "4.1.3" in hit.content
    assert sql.knowledge_base.search("xyzzy qwerty", top_k=3) == []
    assert sql.knowledge_base.search("   ", top_k=3) == []


@pytest.mark.integration
def test_tools_work_unchanged_on_the_postgres_backend(sql: Repositories) -> None:
    tools = {tool.name: tool for tool in build_tools(sql)}
    result = tools["check_service_status"].invoke({"region": "Asia"})
    assert '"status":"outage"' in result and "INC-2291" in result
