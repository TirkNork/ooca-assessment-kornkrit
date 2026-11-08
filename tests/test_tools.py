import json
from importlib.resources import files
from typing import Any

import pytest
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from triage.repositories import Repositories
from triage.tools import build_tools


@pytest.fixture(scope="module")
def tools(repositories: Repositories) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in build_tools(repositories)}


def _call(tool: BaseTool, **args: Any) -> Any:
    return json.loads(tool.invoke(args))


def test_registry_exposes_the_four_tools(tools: dict[str, BaseTool]) -> None:
    assert set(tools) == {
        "get_customer_history",
        "search_knowledge_base",
        "check_service_status",
        "get_billing_transactions",
    }


def test_every_tool_has_a_description_and_documented_args(tools: dict[str, BaseTool]) -> None:
    for tool in tools.values():
        assert tool.description
        for name, prop in tool.args.items():
            assert prop.get("description"), f"{tool.name}.{name} has no description"


def test_every_tool_is_listed_in_the_tools_readme(tools: dict[str, BaseTool]) -> None:
    readme = files("triage.tools").joinpath("README.md").read_text(encoding="utf-8")
    assert all(f"`{name}`" in readme for name in tools)


def test_get_customer_history(tools: dict[str, BaseTool]) -> None:
    result = _call(tools["get_customer_history"], customer_id="C-2001")
    assert result["customer_id"] == "C-2001"
    assert {t["product"] for t in result["past_tickets"]} == {"crm", "erp"}


def test_get_billing_transactions_shows_three_pending_charges(tools: dict[str, BaseTool]) -> None:
    result = _call(tools["get_billing_transactions"], customer_id="C-1001")
    assert result["subscription_status"] == "upgrade_pending"
    assert [t["status"] for t in result["transactions"]] == ["pending"] * 3


def test_check_service_status_reveals_unpublished_outage(tools: dict[str, BaseTool]) -> None:
    result = _call(tools["check_service_status"], region="Asia")
    assert result["status"] == "outage"
    assert result["public_status"] == "operational"
    assert result["active_incidents"][0]["incident_id"] == "INC-2291"


def test_search_knowledge_base_returns_hits(tools: dict[str, BaseTool]) -> None:
    hits = _call(tools["search_knowledge_base"], query="duplicate charges", top_k=2)
    assert 1 <= len(hits) <= 2
    assert set(hits[0]) == {"article_id", "title", "content", "score"}


@pytest.mark.parametrize(
    ("tool_name", "args", "message"),
    [
        ("get_customer_history", {"customer_id": "C-9999"}, "No customer found"),
        ("get_billing_transactions", {"customer_id": "C-9999"}, "No billing account"),
        ("check_service_status", {"region": "mars"}, "Known regions: asia, eu, us"),
    ],
)
def test_not_found_returns_readable_error(
    tools: dict[str, BaseTool], tool_name: str, args: dict[str, Any], message: str
) -> None:
    result = _call(tools[tool_name], **args)
    assert message in result["error"]


@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        ("search_knowledge_base", {"query": "x", "top_k": 50}),
        ("search_knowledge_base", {"query": ""}),
        ("get_customer_history", {}),
    ],
)
def test_invalid_arguments_are_rejected_by_schema(
    tools: dict[str, BaseTool], tool_name: str, args: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        tools[tool_name].invoke(args)
