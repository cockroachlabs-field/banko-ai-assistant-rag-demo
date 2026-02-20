"""Singleton CockroachDBEngine for the entire application.

Provides a single async connection pool backed by langchain-cockroachdb
that all components (vectorstore, chat history, checkpointer) share.
"""

import os
from typing import Optional

from langchain_cockroachdb import CockroachDBEngine


def normalize_crdb_url(url: str) -> str:
    """Convert any CockroachDB URL to use the async psycopg driver.

    langchain-cockroachdb only converts ``cockroachdb://`` automatically.
    This handles ``postgresql://`` and ``postgres://`` as well.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "cockroachdb+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "cockroachdb+psycopg://", 1)
    return url

_engine: Optional[CockroachDBEngine] = None


def get_crdb_engine(database_url: Optional[str] = None) -> CockroachDBEngine:
    """Get or create the singleton CockroachDBEngine.

    Args:
        database_url: CockroachDB connection string.  Falls back to
            DATABASE_URL env var, then localhost default.

    Returns:
        Shared CockroachDBEngine instance.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = database_url or os.getenv(
        "DATABASE_URL",
        "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable",
    )

    url = normalize_crdb_url(url)

    _engine = CockroachDBEngine.from_connection_string(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return _engine


def close_crdb_engine() -> None:
    """Dispose the singleton engine (call on app shutdown)."""
    global _engine
    if _engine is not None:
        _engine.close()
        _engine = None
