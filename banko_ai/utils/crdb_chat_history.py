"""CockroachDB-backed chat message history using langchain-cockroachdb.

Provides persistent conversation storage per session/thread so chat
history survives server restarts and browser refreshes.
"""

import os
from typing import Optional

from langchain_cockroachdb import CockroachDBChatMessageHistory

from .crdb_engine import normalize_crdb_url


def get_chat_history(
    session_id: str,
    database_url: Optional[str] = None,
    table_name: str = "chat_message_store",
) -> CockroachDBChatMessageHistory:
    """Return a CockroachDBChatMessageHistory for the given session.

    The table is created automatically on first use.

    Args:
        session_id: Unique session / thread identifier.
        database_url: CockroachDB connection string (falls back to env).
        table_name: Table name for messages.
    """
    url = normalize_crdb_url(
        database_url or os.getenv(
            "DATABASE_URL",
            "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable",
        )
    )

    history = CockroachDBChatMessageHistory(
        session_id=session_id,
        connection_string=url,
        table_name=table_name,
    )
    history.create_table_if_not_exists()
    return history
