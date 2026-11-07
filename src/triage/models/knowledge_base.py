"""Knowledge base articles and search hits."""

from pydantic import BaseModel


class KBArticle(BaseModel):
    article_id: str
    title: str
    body: str


class KBHit(BaseModel):
    article_id: str
    title: str
    snippet: str
    score: float
