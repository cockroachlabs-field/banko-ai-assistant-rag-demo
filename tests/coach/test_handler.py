"""Unit tests for SignalHandler. Uses an injected StubCoach so the handler
contract is tested without touching the LLM."""

import os
import pytest
from sqlalchemy import create_engine, text

from banko_ai.coach.handler import SignalHandler
from banko_ai.coach.signals import Signal, SignalType
from banko_ai.utils.migration import DatabaseMigration


TEST_USER = "00000000-0000-0000-0000-000000000eee"


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    DatabaseMigration(database_url=url).migrate_to_coach_v1()
    return url


@pytest.fixture(autouse=True)
def _cleanup(db_url):
    eng = create_engine(db_url)
    for table in ("coach_nudges", "spending_signals"):
        try:
            with eng.begin() as conn:
                conn.execute(text(f"DELETE FROM {table} WHERE user_id = :u"),
                             {"u": TEST_USER})
        except Exception:
            pass
    eng.dispose()
    yield


class StubCoach:
    """Records calls; returns a canned nudge result."""
    def __init__(self):
        self.calls = []

    def react(self, signal: Signal) -> dict:
        self.calls.append(signal)
        return {
            "message": f"stub nudge for {signal.signal_type.value}",
            "tool_trace": [{"tool": "get_user_budget"}],
            "provider_used": "stub",
        }


class StubEmitter:
    def __init__(self):
        self.events = []

    def emit(self, event: str, payload: dict, room: str | None = None) -> None:
        self.events.append((event, payload, room))


def _make_signal(idem: str, sig_type: SignalType = SignalType.BUDGET_THRESHOLD,
                 user_id: str = TEST_USER) -> Signal:
    eng = create_engine(os.environ["DATABASE_URL"])
    with eng.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO spending_signals
              (user_id, signal_type, severity, payload, idempotency_key)
            VALUES (:u, :t, 'warn',
                    CAST(:payload AS JSONB), :k)
            RETURNING signal_id
        """), {"u": user_id, "t": sig_type.value, "k": idem,
               "payload": '{"category":"dining","pct_used":0.82}'}).fetchone()
    eng.dispose()
    return Signal(
        signal_id=str(row[0]),
        user_id=user_id,
        signal_type=sig_type,
        severity="warn",
        payload={"category": "dining", "pct_used": 0.82},
        idempotency_key=idem,
    )


def test_handler_invokes_coach_and_persists_nudge(db_url):
    coach = StubCoach()
    emitter = StubEmitter()
    handler = SignalHandler(coach=coach, emitter=emitter, database_url=db_url)

    sig = _make_signal("h-1")
    result = handler.handle(sig)

    assert result["status"] == "delivered"
    assert len(coach.calls) == 1
    assert coach.calls[0].idempotency_key == "h-1"

    eng = create_engine(db_url)
    with eng.connect() as conn:
        nudges = conn.execute(text(
            "SELECT message, provider_used FROM coach_nudges WHERE user_id = :u"
        ), {"u": TEST_USER}).fetchall()
        consumed = conn.execute(text(
            "SELECT consumed_at FROM spending_signals WHERE signal_id = :s"
        ), {"s": sig.signal_id}).fetchone()
    eng.dispose()

    assert len(nudges) == 1
    assert nudges[0][1] == "stub"
    assert consumed[0] is not None
    assert len(emitter.events) == 1
    assert emitter.events[0][0] == "coach.nudge"


def test_handler_dedups_on_idempotency_key(db_url):
    coach = StubCoach()
    emitter = StubEmitter()
    handler = SignalHandler(coach=coach, emitter=emitter, database_url=db_url)

    sig = _make_signal("h-dup")
    first = handler.handle(sig)
    second = handler.handle(sig)

    assert first["status"] == "delivered"
    assert second["status"] == "replayed"
    assert len(coach.calls) == 1


def test_handler_skips_suppressed_signal_type(db_url):
    coach = StubCoach()
    emitter = StubEmitter()
    handler = SignalHandler(
        coach=coach, emitter=emitter, database_url=db_url,
        suppressed_types={SignalType.RECURRING_DRIFT},
    )

    sig = _make_signal("h-suppress", sig_type=SignalType.RECURRING_DRIFT)
    result = handler.handle(sig)

    assert result["status"] == "suppressed"
    assert coach.calls == []
    assert emitter.events == []
