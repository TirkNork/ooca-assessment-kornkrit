"""Hybrid knowledge base search: pgvector similarity + Postgres full-text search, fused with
Reciprocal Rank Fusion (RRF). Semantic search finds paraphrases ("money back" -> refund);
full-text search keeps exact terms (error codes, product names) ranking well."""

from collections import defaultdict

from sqlalchemy import Engine, Text, cast, func, select
from sqlalchemy.orm import Session

from triage.embeddings import Embedder
from triage.models import KBHit
from triage.repositories.postgres.schema import KBArticleRow, KBChunkRow

_CANDIDATES = 20  # chunks taken from each search before fusing
_RRF_K = 60  # standard RRF constant: dampens the advantage of the very top ranks
_MAX_CONTENT_CHARS = 1500  # articles up to this size are returned whole


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = _RRF_K) -> dict[int, float]:
    """Score each item by the sum of 1 / (k + rank) over the rankings it appears in."""
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1 / (k + rank)
    return dict(scores)


class PgVectorKnowledgeBase:
    def __init__(self, engine: Engine, embedder: Embedder, min_similarity: float) -> None:
        self._engine = engine
        self._embedder = embedder
        self._max_distance = 1 - min_similarity

    def search(self, query: str, top_k: int) -> list[KBHit]:
        if not query.strip():
            return []
        embedding = self._embedder.embed_query(query)

        with Session(self._engine) as session:
            semantic = self._semantic_chunk_ids(session, embedding)
            keyword = self._keyword_chunk_ids(session, query)
            chunk_scores = reciprocal_rank_fusion([semantic, keyword])
            if not chunk_scores:
                return []

            chunks = session.scalars(
                select(KBChunkRow).where(KBChunkRow.id.in_(chunk_scores))
            ).all()
            article_scores: dict[str, float] = defaultdict(float)
            matched: dict[str, list[KBChunkRow]] = defaultdict(list)
            for chunk in chunks:
                article_scores[chunk.article_id] = max(
                    article_scores[chunk.article_id], chunk_scores[chunk.id]
                )
                matched[chunk.article_id].append(chunk)

            top = sorted(article_scores, key=article_scores.__getitem__, reverse=True)[:top_k]
            articles = {
                a.article_id: a
                for a in session.scalars(
                    select(KBArticleRow).where(KBArticleRow.article_id.in_(top))
                )
            }
            return [
                KBHit(
                    article_id=article_id,
                    title=articles[article_id].title,
                    content=_content(articles[article_id], matched[article_id]),
                    score=round(article_scores[article_id], 4),
                )
                for article_id in top
            ]

    def _semantic_chunk_ids(self, session: Session, embedding: list[float]) -> list[int]:
        distance = KBChunkRow.embedding.cosine_distance(embedding)
        query = (
            select(KBChunkRow.id)
            .where(distance <= self._max_distance)
            .order_by(distance)
            .limit(_CANDIDATES)
        )
        return list(session.scalars(query))

    def _keyword_chunk_ids(self, session: Session, query: str) -> list[int]:
        # plainto_tsquery ANDs the words; swap to OR so a chunk matching some words still counts
        # and ts_rank_cd ranks chunks matching more of them higher.
        and_query = cast(func.plainto_tsquery("english", query), Text)
        ts_query = func.to_tsquery("english", func.replace(and_query, "&", "|"))
        rank = func.ts_rank_cd(KBChunkRow.search_vector, ts_query)
        statement = (
            select(KBChunkRow.id)
            .where(KBChunkRow.search_vector.op("@@")(ts_query))
            .order_by(rank.desc())
            .limit(_CANDIDATES)
        )
        return list(session.scalars(statement))


def _content(article: KBArticleRow, matched: list[KBChunkRow]) -> str:
    if len(article.body) <= _MAX_CONTENT_CHARS:
        return article.body
    return "\n\n".join(c.content for c in sorted(matched, key=lambda c: c.chunk_index))
