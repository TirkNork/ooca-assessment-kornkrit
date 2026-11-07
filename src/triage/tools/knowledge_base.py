from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from triage.repositories import KnowledgeBase
from triage.tools._results import ok


class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(
        min_length=1,
        description=(
            "What to look up, written in English even if the customer wrote in another "
            "language, e.g. 'duplicate pending charges after failed upgrade'."
        ),
    )
    top_k: int = Field(default=3, ge=1, le=5, description="Maximum number of articles to return.")


def make_search_knowledge_base(knowledge_base: KnowledgeBase) -> BaseTool:
    def search_knowledge_base(query: str, top_k: int = 3) -> str:
        return ok(knowledge_base.search(query, top_k))

    return StructuredTool.from_function(
        func=search_knowledge_base,
        name="search_knowledge_base",
        description=(
            "Search the help-center knowledge base (FAQ and docs) for articles that help answer "
            "the customer. Returns article id, title, the most relevant snippet and a relevance "
            "score; an empty list means nothing relevant was found. Search once per distinct issue."
        ),
        args_schema=SearchKnowledgeBaseInput,
    )
