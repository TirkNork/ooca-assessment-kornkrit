"""In-memory keyword search over KB articles using BM25."""

import math
import re
from collections import Counter

from triage.models import KBArticle, KBHit

_TOKEN = re.compile(r"[a-z0-9]+")
# fmt: off
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "for", "from",
    "has", "have", "how", "i", "if", "in", "is", "it", "its", "my", "of", "on", "or", "so",
    "that", "the", "their", "this", "to", "was", "we", "what", "when", "with", "you", "your",
})
# fmt: on
# Articles up to this size are returned whole; longer ones are cut to their most relevant parts.
_MAX_CONTENT_CHARS = 1500


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens without stopwords; trailing plural 's' is stripped."""
    tokens = []
    for token in _TOKEN.findall(text.lower()):
        if token in _STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


class Bm25Index:
    """Okapi BM25 with Lucene's IDF, which stays positive even for terms found in most documents
    (plain Okapi IDF drops to zero or below, which breaks ranking on a small corpus)."""

    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self._k1, self._b = k1, b
        self._term_freqs = [Counter(doc) for doc in documents]
        self._lengths = [len(doc) for doc in documents]
        self._avg_length = sum(self._lengths) / len(documents)
        doc_freq = Counter(term for doc in documents for term in set(doc))
        n = len(documents)
        self._idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}

    def scores(self, query: list[str]) -> list[float]:
        return [self._score(query, i) for i in range(len(self._term_freqs))]

    def _score(self, query: list[str], i: int) -> float:
        tf, length = self._term_freqs[i], self._lengths[i]
        norm = self._k1 * (1 - self._b + self._b * length / self._avg_length)
        return sum(self._idf[t] * tf[t] * (self._k1 + 1) / (tf[t] + norm) for t in query if tf[t])


class Bm25KnowledgeBase:
    def __init__(self, articles: list[KBArticle]) -> None:
        if not articles:
            raise ValueError("knowledge base is empty")
        self._articles = articles
        # The title is repeated so that a title match outweighs a passing mention in the body.
        corpus = [tokenize(f"{a.title} {a.title} {a.body}") for a in articles]
        self._index = Bm25Index(corpus)

    def search(self, query: str, top_k: int) -> list[KBHit]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = self._index.scores(query_tokens)
        ranked = sorted(zip(scores, self._articles, strict=True), key=lambda pair: -pair[0])
        return [
            KBHit(
                article_id=article.article_id,
                title=article.title,
                content=_relevant_content(article.body, set(query_tokens)),
                score=round(score, 3),
            )
            for score, article in ranked[:top_k]
            if score > 0
        ]


def _relevant_content(body: str, query_tokens: set[str]) -> str:
    """The whole body if it fits, otherwise the paragraphs that share tokens with the query, most
    relevant first, up to the size limit (returned in their original order)."""
    if len(body) <= _MAX_CONTENT_CHARS:
        return body
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    overlap = [len(query_tokens & set(tokenize(p))) for p in paragraphs]
    by_relevance = sorted(range(len(paragraphs)), key=lambda i: overlap[i], reverse=True)
    candidates = [i for i in by_relevance if overlap[i] > 0] or by_relevance
    chosen: list[int] = []
    used = 0
    for i in candidates:
        if chosen and used + len(paragraphs[i]) > _MAX_CONTENT_CHARS:
            break
        chosen.append(i)
        used += len(paragraphs[i])
    return "\n\n".join(paragraphs[i] for i in sorted(chosen))
