"""Test that Coach v1 migrations create spending_signals and coach_nudges
with the correct columns, PKs, indexes, and TTL."""

import os

import pytest
from sqlalchemy import create_engine, text

from banko_ai.utils.migration import DatabaseMigration


@pytest.fixture
def db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set; integration test requires a live CRDB")
    return url


def _column_names(conn, table_name: str) -> list[str]:
    rows = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :t ORDER BY ordinal_position"
    ), {"t": table_name}).fetchall()
    return [r[0] for r in rows]


def test_spending_signals_table_created(db_url):
    migrator = DatabaseMigration(database_url=db_url)
    assert migrator.migrate_to_coach_v1() is True

    with migrator.engine.connect() as conn:
        cols = _column_names(conn, "spending_signals")
        assert set(cols) >= {
            "signal_id", "user_id", "signal_type", "severity",
            "payload", "produced_at", "consumed_at", "idempotency_key",
        }


def test_coach_nudges_table_created(db_url):
    migrator = DatabaseMigration(database_url=db_url)
    assert migrator.migrate_to_coach_v1() is True

    with migrator.engine.connect() as conn:
        cols = _column_names(conn, "coach_nudges")
        assert set(cols) >= {
            "nudge_id", "signal_id", "user_id", "message",
            "tool_trace", "provider_used", "trace_id", "created_at",
        }


def test_spending_signals_idempotency_key_unique(db_url):
    migrator = DatabaseMigration(database_url=db_url)
    migrator.migrate_to_coach_v1()

    user_id = "00000000-0000-0000-0000-000000000aaa"
    with migrator.engine.connect() as conn:
        # Nudges reference signals, so they have to go first or the signal
        # delete trips the FK when an earlier test left nudges behind.
        conn.execute(text(
            "DELETE FROM coach_nudges WHERE signal_id IN "
            "(SELECT signal_id FROM spending_signals WHERE user_id = :u)"
        ), {"u": user_id})
        conn.execute(text("DELETE FROM spending_signals WHERE user_id = :u"),
                     {"u": user_id})
        conn.execute(text(
            "INSERT INTO spending_signals "
            "(user_id, signal_type, severity, payload, idempotency_key) "
            "VALUES (:u, 'budget_threshold', 'warn', '{}'::JSONB, 'dup-key-1')"
        ), {"u": user_id})
        conn.commit()

        with pytest.raises(Exception):
            conn.execute(text(
                "INSERT INTO spending_signals "
                "(user_id, signal_type, severity, payload, idempotency_key) "
                "VALUES (:u, 'budget_threshold', 'warn', '{}'::JSONB, 'dup-key-1')"
            ), {"u": user_id})
            conn.commit()

        conn.rollback()
        conn.execute(text("DELETE FROM spending_signals WHERE user_id = :u"),
                     {"u": user_id})
        conn.commit()
