"""Retrieval quality: queries the agent is expected to make must find the right article (hit@3)."""

import pytest

from triage.models import KBArticle
from triage.repositories import Repositories
from triage.repositories.file import Bm25KnowledgeBase


@pytest.mark.parametrize(
    ("query", "expected_article"),
    [
        # Ticket 1: failed upgrade, duplicate charges, needs Pro export
        ("duplicate pending charges after failed upgrade", "KB-012"),
        ("refund duplicate charges", "KB-013"),
        ("Pro export features for presentation", "KB-040"),
        # Ticket 2: whole team gets HTTP 500, status page says operational
        ("HTTP 500 error cannot access multiple users", "KB-031"),
        ("status page says all systems operational but asia region is down", "KB-032"),
        ("enterprise SLA critical issue response time", "KB-050"),
        # Ticket 3: dark mode missing / System Default not following macOS, scheduling
        ("dark mode option missing, only light and system default", "KB-020"),
        ("system default theme not following macOS dark appearance", "KB-020"),
        ("schedule dark mode to switch automatically at a set time", "KB-020"),
    ],
)
def test_expected_article_is_in_top_3(
    repositories: Repositories, query: str, expected_article: str
) -> None:
    hits = repositories.knowledge_base.search(query, top_k=3)
    assert expected_article in [h.article_id for h in hits]


def test_results_are_sorted_and_limited(repositories: Repositories) -> None:
    hits = repositories.knowledge_base.search("charges refund upgrade payment", top_k=2)
    assert len(hits) == 2
    assert hits[0].score >= hits[1].score


@pytest.mark.parametrize("query", ["", "the and of", "xyzzy qwerty"])
def test_queries_without_matches_return_nothing(repositories: Repositories, query: str) -> None:
    assert repositories.knowledge_base.search(query, top_k=3) == []


def test_snippet_is_the_most_relevant_paragraph() -> None:
    kb = Bm25KnowledgeBase(
        [
            KBArticle(article_id="A", title="Billing", body="Intro text.\n\nRefunds take 5 days."),
            KBArticle(article_id="B", title="Other", body="Unrelated content."),
        ]
    )
    [hit] = kb.search("refund", top_k=1)
    assert hit.snippet == "Refunds take 5 days."


def test_empty_knowledge_base_is_rejected() -> None:
    with pytest.raises(ValueError):
        Bm25KnowledgeBase([])
