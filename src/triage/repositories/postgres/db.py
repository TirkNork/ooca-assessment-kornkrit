"""Database engine shared by the repositories and the seed script."""

from sqlalchemy import Engine, create_engine


class DatabaseNotReadyError(RuntimeError):
    pass


def create_db_engine(database_url: str | None) -> Engine:
    if not database_url:
        raise DatabaseNotReadyError("DATABASE_URL is not set.")
    # Pre-ping replaces pooled connections the server closed (e.g. after a database restart).
    return create_engine(database_url, pool_pre_ping=True)
