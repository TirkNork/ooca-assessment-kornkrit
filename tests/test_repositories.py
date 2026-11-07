import pytest

from triage.models import Plan, Product
from triage.repositories import Repositories
from triage.repositories.kb_markdown import parse_article


def test_customer_profile_and_history(repositories: Repositories) -> None:
    profile = repositories.customers.get_profile("C-2001")
    history = repositories.customers.get_history("C-2001")

    assert profile is not None and history is not None
    assert profile.plan is Plan.ENTERPRISE
    assert {s.product for s in profile.products} == {Product.CRM, Product.ERP}
    assert len(history.past_tickets) == 2


def test_unknown_ids_return_none(repositories: Repositories) -> None:
    assert repositories.customers.get_profile("C-9999") is None
    assert repositories.customers.get_history("C-9999") is None
    assert repositories.billing.get_account("C-9999") is None
    assert repositories.service_status.get_region("mars") is None


@pytest.mark.parametrize("region", ["asia", "Asia", " ASIA "])
def test_region_lookup_is_case_insensitive(repositories: Repositories, region: str) -> None:
    status = repositories.service_status.get_region(region)
    assert status is not None and status.region == "asia"


def test_lists_known_regions(repositories: Repositories) -> None:
    assert repositories.service_status.regions() == ["asia", "eu", "us"]


def test_parse_article_reads_front_matter_and_body() -> None:
    article = parse_article("---\nid: KB-1\ntitle: Hello: world\n---\nFirst line.\n\nSecond.\n")
    assert article.article_id == "KB-1"
    assert article.title == "Hello: world"
    assert article.body == "First line.\n\nSecond."


@pytest.mark.parametrize("text", ["no front matter", "---\nid: KB-1\ntitle: never closed\nbody"])
def test_parse_article_rejects_malformed_front_matter(text: str) -> None:
    with pytest.raises(ValueError):
        parse_article(text)
