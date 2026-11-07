"""Create the Postgres schema and load data/ into it, embedding the knowledge base.

    python scripts/seed_db.py            # (re)load data, reusing unchanged embeddings
    python scripts/seed_db.py --reset    # drop and recreate all tables first

Needs DATABASE_URL (set by compose) and OPENAI_API_KEY (for embeddings).
"""

import argparse
import sys

from triage.config import get_settings
from triage.embeddings import Embedder, build_embedder
from triage.repositories.postgres.db import DatabaseNotReadyError, create_db_engine
from triage.repositories.postgres.seed import create_schema, seed_database


def main(argv: list[str] | None = None, embedder: Embedder | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        engine = create_db_engine(settings.database_url)
    except DatabaseNotReadyError as exc:
        parser.error(str(exc))

    create_schema(engine, reset=args.reset)
    report = seed_database(
        engine,
        settings.data_dir,
        embedder or build_embedder(settings),
        settings.openai_embedding_model,
    )
    print(
        f"Seeded {report.customers} customers, {report.articles} KB articles and "
        f"{report.chunks} chunks ({report.newly_embedded} newly embedded)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
