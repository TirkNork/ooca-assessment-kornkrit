"""Parse knowledge base articles stored as Markdown with a small front-matter block.

---
id: KB-012
title: Pending or duplicate charges after a failed upgrade
---
Body text...
"""

from pathlib import Path

from triage.models import KBArticle

_DELIMITER = "---"


def parse_article(text: str) -> KBArticle:
    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != _DELIMITER:
        raise ValueError("article must start with a '---' front-matter block")
    try:
        end = lines.index(_DELIMITER, 1)
    except ValueError as exc:
        raise ValueError("front-matter block is not closed with '---'") from exc

    meta = dict(line.split(":", 1) for line in lines[1:end] if ":" in line)
    meta = {key.strip(): value.strip() for key, value in meta.items()}
    return KBArticle(
        article_id=meta["id"],
        title=meta["title"],
        body="\n".join(lines[end + 1 :]).strip(),
    )


def load_articles(kb_dir: Path) -> list[KBArticle]:
    return [parse_article(p.read_text(encoding="utf-8")) for p in sorted(kb_dir.glob("*.md"))]
