"""Tool results are JSON strings so the LLM always receives a predictable shape.

A "not found" or invalid-input case returns `{"error": ...}` instead of raising, so the model can
read the problem and adjust (e.g. retry with a valid region). Unexpected exceptions are left to
the graph's ToolNode, which reports them to the model as tool errors.
"""

import json

from pydantic import BaseModel


def ok(result: BaseModel | list[BaseModel]) -> str:
    if isinstance(result, BaseModel):
        return result.model_dump_json()
    return json.dumps([item.model_dump(mode="json") for item in result], ensure_ascii=False)


def error(message: str) -> str:
    return json.dumps({"error": message})
