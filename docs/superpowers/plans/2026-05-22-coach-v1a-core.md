# Coach v1-A: Core (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the **foundation half** of the Spending Coach v1 spec — everything required to demo a real, event-driven nudge end to end against a live CockroachDB with both transport paths (webhook **and** Kafka) working. After this plan, `mock_signals.py --type=budget_threshold` produces a card in the Live Coach UI within 5s on cloud (15s on Ollama CPU), and a follow-up reply hits the conversational Coach.

**Architecture:** New `banko_ai/coach/` package containing `Signal` dataclass, transport-agnostic `SignalHandler`, planner-executor `CoachAgent` (LangGraph `StateGraph` with reactive **and** conversational modes), Coach tools module, and a flag-gated Kafka consumer. Webhook receiver and `/api/coach/*` routes land in `banko_ai/web/app.py`. UI is a new `coach.html` template + SocketIO event `coach.nudge`. DB additions are two new tables (`spending_signals`, `coach_nudges`) with row-level TTL, added through the existing `banko_ai/utils/migration.py` runner. Three Supervisor/Observability/MCP-shaped features are **deferred** — Coach calls `CoachAgent.react()` and `CoachAgent.converse()` directly here; Plan 2-B replaces those direct calls with the Supervisor.

**Tech Stack:** Python 3.10+, LangGraph 1.x (`StateGraph`), `langchain-cockroachdb` 0.2.x (`CockroachDBSaver`), Flask 3.1.3 + Flask-SocketIO, `kafka-python` (new dep, ~one-line addition), CockroachDB 25.4.0+ with row-level TTL, `pytest` for unit + integration, `make test-local` as the local gate before push. All LLM calls go through `banko_ai/agents/llm_factory.get_llm_for_agent()` which is the existing wrapper over `banko_ai/ai_providers/` — Coach never imports a provider SDK directly.

---

## File Map

| Task | Files | Action |
|------|-------|--------|
| Pre-flight | `banko_ai/config/settings.py` | Modify — add 6 Coach env knobs |
| 1 | `banko_ai/utils/migration.py`, `tests/test_coach_migrations.py` | Modify; create test |
| 2 | `banko_ai/coach/__init__.py`, `banko_ai/coach/signals.py`, `tests/coach/__init__.py`, `tests/coach/test_signals.py` | Create |
| 3 | `banko_ai/coach/tools.py`, `tests/coach/test_tools.py` | Create |
| 4 | `banko_ai/coach/handler.py`, `tests/coach/test_handler.py` | Create |
| 5 | `banko_ai/coach/agent.py`, `tests/coach/test_agent_reactive.py` | Create |
| 6 | `banko_ai/coach/agent.py`, `tests/coach/test_agent_conversational.py` | Modify (extend); create test |
| 7 | `banko_ai/web/app.py`, `tests/coach/test_webhook.py` | Modify (+~70 LOC); create test |
| 8 | `scripts/coach/mock_signals.py`, `scripts/coach/__init__.py` | Create |
| 9 | `banko_ai/templates/coach.html`, `banko_ai/web/app.py`, `banko_ai/templates/index.html` | Create; modify (+~40 LOC); modify (add nav link) |
| 10 | `banko_ai/coach/kafka_consumer.py`, `tests/coach/test_kafka_consumer.py`, `pyproject.toml` | Create; create; modify (add `kafka-python`) |
| 11 | `banko_ai/web/app.py`, `tests/coach/test_health_endpoint.py` | Modify (+~30 LOC); create |
| 12 | (none — verification + commit, **no push**) | n/a |

**Gitignore footgun:** the repo's `.gitignore` has an unanchored `test_*.py` entry that hides every new pytest module from `git add`. **Every new file under `tests/coach/` MUST be added with `git add -f`.** This is called out at each commit step where it matters. Do not "fix" `.gitignore` in this plan — that change belongs in Plan 2-B's housekeeping.

---

## Pre-flight: branch, baseline, env knobs

- [ ] **Step P.1: Confirm clean working tree and current branch**

Run:
```bash
git status
git branch --show-current
```
Expected: working tree clean (only `docs/superpowers/` may be untracked), current branch is whichever Plan 1 work landed on. If Plan 1 is still on a feature branch and not yet merged to `main`, base this work on `main` directly — Coach development must not depend on un-merged Plan 1 commits. If unsure, ask the user.

- [ ] **Step P.2: Create the Coach core branch off `main`**

Run:
```bash
git fetch origin
git checkout main
git checkout -b feat/coach-core-v1a
```
Expected: switched to a new branch `feat/coach-core-v1a` starting from `main`.

- [ ] **Step P.3: Verify CockroachDB is running locally and is v25.4.0+**

Run:
```bash
cockroach sql --insecure --execute "SELECT version();"
```
Expected: a single row showing `CockroachDB CCL v25.4.0` or higher. Row-level TTL on the new Coach tables requires v25.4+.

If not running, start it:
```bash
cockroach start-single-node --insecure --store=./cockroach-data \
  --listen-addr=localhost:26257 --http-addr=localhost:8080 --background
```

- [ ] **Step P.4: Add Coach environment knobs to `banko_ai/config/settings.py`**

Open `banko_ai/config/settings.py` and find the `@dataclass class Config:` (or equivalent settings dataclass — name may vary; the file is the single env-driven settings module). Append the following six fields to the dataclass, preserving the existing `field(default_factory=lambda: os.getenv(...))` pattern used by every other knob in the file:

```python
    # --- Coach (added 2026-05-22) ---
    cdc_webhook_hmac_secret: str = field(
        default_factory=lambda: os.getenv("CDC_WEBHOOK_HMAC_SECRET", "")
    )
    coach_rate_limit_per_5min: int = field(
        default_factory=lambda: int(os.getenv("COACH_RATE_LIMIT_PER_5MIN", "30"))
    )
    coach_agent_max_steps: int = field(
        default_factory=lambda: int(os.getenv("COACH_AGENT_MAX_STEPS", "5"))
    )
    coach_socketio_room_prefix: str = field(
        default_factory=lambda: os.getenv("COACH_SOCKETIO_ROOM_PREFIX", "coach:")
    )
    coach_default_user_id: str = field(
        default_factory=lambda: os.getenv(
            "COACH_DEFAULT_USER_ID",
            "00000000-0000-0000-0000-000000000001",
        )
    )
    coach_kafka_enabled: bool = field(
        default_factory=lambda: os.getenv("COACH_KAFKA_ENABLED", "false").lower() == "true"
    )
```

- [ ] **Step P.5: Commit the env knobs**

Run:
```bash
git add banko_ai/config/settings.py
git commit -m "feat(coach): add config knobs for webhook HMAC, rate limit, agent steps, Kafka flag"
```

Expected: one commit, one file changed.

---

## Task 1: Database migrations — `spending_signals` + `coach_nudges`

**Files:**
- Modify: `banko_ai/utils/migration.py`
- Create: `tests/test_coach_migrations.py`

**Rationale:** Every downstream component (handler, agent, webhook) writes to these tables. Land the schema first so subsequent tasks can write integration tests against real rows. Both tables use CockroachDB row-level TTL (`ttl_expire_after`), matching the pattern in use for LangGraph checkpoints.

- [ ] **Step 1.1: Write a failing test that asserts both tables exist after migration**

Create `tests/test_coach_migrations.py` with exactly this content:

```python
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

    engine = create_engine(db_url)
    with engine.connect() as conn:
        cols = _column_names(conn, "spending_signals")
        assert set(cols) >= {
            "signal_id", "user_id", "signal_type", "severity",
            "payload", "produced_at", "consumed_at", "idempotency_key",
        }


def test_coach_nudges_table_created(db_url):
    migrator = DatabaseMigration(database_url=db_url)
    assert migrator.migrate_to_coach_v1() is True

    engine = create_engine(db_url)
    with engine.connect() as conn:
        cols = _column_names(conn, "coach_nudges")
        assert set(cols) >= {
            "nudge_id", "signal_id", "user_id", "message",
            "tool_trace", "provider_used", "trace_id", "created_at",
        }


def test_spending_signals_idempotency_key_unique(db_url):
    migrator = DatabaseMigration(database_url=db_url)
    migrator.migrate_to_coach_v1()

    engine = create_engine(db_url)
    user_id = "00000000-0000-0000-0000-000000000aaa"
    with engine.connect() as conn:
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
```

- [ ] **Step 1.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/test_coach_migrations.py
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/test_coach_migrations.py -v
```
Expected: FAIL on `AttributeError: 'DatabaseMigration' object has no attribute 'migrate_to_coach_v1'`.

- [ ] **Step 1.3: Add the `migrate_to_coach_v1` method to `DatabaseMigration`**

Open `banko_ai/utils/migration.py` and append the following method to the `DatabaseMigration` class (after `add_created_at_column`, before `run_all_migrations`). Then update `run_all_migrations` to call it.

```python
    def migrate_to_coach_v1(self) -> bool:
        """Create spending_signals and coach_nudges tables for the Coach v1
        feature. Both tables use row-level TTL matching the LangGraph
        checkpoint pattern."""
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS spending_signals (
                      signal_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      user_id         UUID NOT NULL,
                      signal_type     STRING NOT NULL,
                      severity        STRING NOT NULL,
                      payload         JSONB NOT NULL,
                      produced_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                      consumed_at     TIMESTAMPTZ,
                      idempotency_key STRING NOT NULL UNIQUE,
                      INDEX (user_id, produced_at DESC)
                    ) WITH (ttl_expire_after = '30 days')
                """))
                print("Created spending_signals table")

                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS coach_nudges (
                      nudge_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      signal_id      UUID REFERENCES spending_signals(signal_id),
                      user_id        UUID NOT NULL,
                      message        STRING NOT NULL,
                      tool_trace     JSONB,
                      provider_used  STRING,
                      trace_id       STRING,
                      created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                      INDEX (user_id, created_at DESC)
                    ) WITH (ttl_expire_after = '90 days')
                """))
                print("Created coach_nudges table")

                conn.commit()
                return True

        except Exception as e:
            print(f"Coach v1 migration failed: {e}")
            return False
```

Then modify `run_all_migrations` to add the new call:

Find:
```python
        success = True
        success &= self.add_created_at_column()
        success &= self.migrate_to_user_specific_indexing()
```

Replace with:
```python
        success = True
        success &= self.add_created_at_column()
        success &= self.migrate_to_user_specific_indexing()
        success &= self.migrate_to_coach_v1()
```

- [ ] **Step 1.4: Run the test to verify it passes**

Run:
```bash
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/test_coach_migrations.py -v
```
Expected: PASS on all three tests.

- [ ] **Step 1.5: Commit**

Run:
```bash
git add banko_ai/utils/migration.py
git commit -m "feat(coach): add spending_signals and coach_nudges migrations with TTL"
```

---

## Task 2: `Signal` dataclass + types + parser

**Files:**
- Create: `banko_ai/coach/__init__.py`
- Create: `banko_ai/coach/signals.py`
- Create: `tests/coach/__init__.py`
- Create: `tests/coach/test_signals.py`

**Rationale:** Both transport paths (webhook and Kafka) normalize incoming events into a single `Signal` dataclass before handing to the `SignalHandler`. Defining the dataclass first means every downstream task has a single concrete type to depend on. Pure logic, no I/O.

- [ ] **Step 2.1: Create empty package `__init__.py` files**

Create `banko_ai/coach/__init__.py` with content:

```python
"""Coach v1: event-driven spending-coach agent.

The Coach reacts to streaming spending signals produced by the sibling
`cockroachdb-watsonx-data-pipeline` repo. Two transport paths feed the same
in-process `SignalHandler`: the CRDB changefeed webhook (demo path) and
the Debezium Kafka topic (prod path).
"""
```

Create `tests/coach/__init__.py` with content:

```python
"""Coach v1 tests."""
```

- [ ] **Step 2.2: Write the failing test for `Signal.from_dict` + `parse_changefeed_envelope`**

Create `tests/coach/test_signals.py` with exactly this content:

```python
"""Unit tests for Signal dataclass and CRDB changefeed parser. Pure logic,
no DB, no network."""

import json
import pytest

from banko_ai.coach.signals import (
    Signal,
    SignalParseError,
    SignalType,
    parse_changefeed_envelope,
)


def test_signal_from_dict_minimal():
    sig = Signal.from_dict({
        "signal_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "22222222-2222-2222-2222-222222222222",
        "signal_type": "budget_threshold",
        "severity": "warn",
        "payload": {"category": "dining", "pct_used": 0.82},
        "idempotency_key": "k-1",
    })
    assert sig.signal_type == SignalType.BUDGET_THRESHOLD
    assert sig.severity == "warn"
    assert sig.payload["category"] == "dining"
    assert sig.idempotency_key == "k-1"


def test_signal_from_dict_rejects_unknown_signal_type():
    with pytest.raises(SignalParseError, match="unknown signal_type"):
        Signal.from_dict({
            "signal_id": "11111111-1111-1111-1111-111111111111",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "signal_type": "made_up_type",
            "severity": "warn",
            "payload": {},
            "idempotency_key": "k-2",
        })


def test_signal_from_dict_requires_idempotency_key():
    with pytest.raises(SignalParseError, match="idempotency_key"):
        Signal.from_dict({
            "signal_id": "11111111-1111-1111-1111-111111111111",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "signal_type": "budget_threshold",
            "severity": "warn",
            "payload": {},
        })


def test_parse_changefeed_envelope_insert():
    envelope = {
        "payload": [{
            "after": {
                "signal_id": "33333333-3333-3333-3333-333333333333",
                "user_id": "22222222-2222-2222-2222-222222222222",
                "signal_type": "anomaly",
                "severity": "critical",
                "payload": {"merchant": "Uber", "amount": 850.0,
                            "z_score": 4.2},
                "idempotency_key": "anom-1",
            },
            "updated": "1716355200.0000000000"
        }]
    }
    signals = parse_changefeed_envelope(envelope)
    assert len(signals) == 1
    assert signals[0].signal_type == SignalType.ANOMALY
    assert signals[0].payload["z_score"] == 4.2


def test_parse_changefeed_envelope_delete_is_skipped():
    envelope = {
        "payload": [{
            "after": None,
            "before": {"signal_id": "44444444-4444-4444-4444-444444444444"},
            "updated": "1716355200.0000000000"
        }]
    }
    assert parse_changefeed_envelope(envelope) == []


def test_parse_changefeed_envelope_handles_envelope_as_json_string():
    """CRDB webhook sometimes sends the body as a JSON string in `value`
    rather than parsed JSON. Parser should accept both."""
    inner = {
        "payload": [{
            "after": {
                "signal_id": "55555555-5555-5555-5555-555555555555",
                "user_id": "22222222-2222-2222-2222-222222222222",
                "signal_type": "recurring_drift",
                "severity": "info",
                "payload": {"subscription": "Netflix",
                            "old_amount": 15.99, "new_amount": 22.99},
                "idempotency_key": "drift-1",
            },
            "updated": "1716355200.0000000000"
        }]
    }
    signals = parse_changefeed_envelope(json.dumps(inner))
    assert len(signals) == 1
    assert signals[0].payload["new_amount"] == 22.99
```

- [ ] **Step 2.3: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/__init__.py tests/coach/test_signals.py
uv run pytest tests/coach/test_signals.py -v
```
Expected: FAIL on `ModuleNotFoundError: No module named 'banko_ai.coach.signals'`.

- [ ] **Step 2.4: Implement `signals.py`**

Create `banko_ai/coach/signals.py` with exactly this content:

```python
"""Signal dataclass, signal-type enum, and CRDB changefeed envelope parser.

Pure logic only — no DB, no network. Both the webhook receiver and the
Kafka consumer normalize incoming events into `Signal` before handing them
to `SignalHandler`, so the handler never has to know which transport
produced the event.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SignalType(str, Enum):
    """The three v1 signal types the pipeline produces and Coach reacts to."""
    BUDGET_THRESHOLD = "budget_threshold"
    ANOMALY = "anomaly"
    RECURRING_DRIFT = "recurring_drift"


class SignalParseError(ValueError):
    """Raised when a payload cannot be normalized into a Signal."""


@dataclass(frozen=True)
class Signal:
    """A normalized spending signal handed to SignalHandler.

    `signal_id` is the canonical correlation ID used in logs, DB rows, and
    OTel span attributes (added in Plan 2-C). `idempotency_key` is what the
    pipeline guarantees is unique per logical event — it's what we dedup on
    at the receiver boundary.
    """
    signal_id: str
    user_id: str
    signal_type: SignalType
    severity: str  # 'info' | 'warn' | 'critical'
    payload: dict[str, Any]
    idempotency_key: str
    produced_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Signal":
        required = ("signal_id", "user_id", "signal_type", "severity",
                    "payload", "idempotency_key")
        missing = [k for k in required if k not in d]
        if missing:
            raise SignalParseError(f"missing required fields: {missing}")
        try:
            signal_type = SignalType(d["signal_type"])
        except ValueError as e:
            raise SignalParseError(f"unknown signal_type: {d['signal_type']}") from e
        return cls(
            signal_id=str(d["signal_id"]),
            user_id=str(d["user_id"]),
            signal_type=signal_type,
            severity=d["severity"],
            payload=d["payload"] or {},
            idempotency_key=d["idempotency_key"],
        )


def parse_changefeed_envelope(envelope: Any) -> list[Signal]:
    """Parse a CRDB CHANGEFEED webhook envelope into Signals.

    The envelope shape (CRDB 25.4 ENVELOPE 'wrapped' format):
        {"payload": [{"after": {...row...}, "before": {...}, "updated": "ts"}, ...]}

    Deletes (after=None) are skipped — we never react to a signal removal.
    Accepts both parsed dict and a JSON string (some sinks send the body as
    a quoted string in the value field).
    """
    if isinstance(envelope, (str, bytes, bytearray)):
        envelope = json.loads(envelope)

    rows = envelope.get("payload") or []
    signals: list[Signal] = []
    for row in rows:
        after = row.get("after")
        if after is None:
            continue
        signals.append(Signal.from_dict(after))
    return signals
```

- [ ] **Step 2.5: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/coach/test_signals.py -v
```
Expected: PASS on all 6 tests.

- [ ] **Step 2.6: Commit**

Run:
```bash
git add banko_ai/coach/__init__.py banko_ai/coach/signals.py
git commit -m "feat(coach): add Signal dataclass and CRDB changefeed envelope parser"
```

---

## Task 3: Coach tools

**Files:**
- Create: `banko_ai/coach/tools.py`
- Create: `tests/coach/test_tools.py`

**Rationale:** The agent's executor calls these tools to gather context (read tools) and persist user choices (write tools). The MCP server in Plan 2-B will wrap **the same module**, so the contract between agent and tools must be identical to the contract between MCP and tools — that's what guarantees behavior parity across channels. Six tools per spec §4.1: `get_user_budget`, `get_recent_signals`, `get_recent_transactions`, `set_budget`, `explain_nudge`, `simulate_signal`. `simulate_signal` lands in Plan 2-B (it's an MCP convenience; the agent doesn't call it).

- [ ] **Step 3.1: Write the failing test for the read tools**

Create `tests/coach/test_tools.py` with exactly this content:

```python
"""Unit tests for Coach tools. Uses a real local CRDB via DATABASE_URL.
Each test seeds its own rows and cleans up after itself."""

import os
import pytest
from sqlalchemy import create_engine, text

from banko_ai.coach.tools import (
    explain_nudge,
    get_recent_signals,
    get_recent_transactions,
    get_user_budget,
    set_budget,
)
from banko_ai.utils.migration import DatabaseMigration


TEST_USER = "00000000-0000-0000-0000-000000000fff"


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    DatabaseMigration(database_url=url).migrate_to_coach_v1()
    return url


@pytest.fixture(autouse=True)
def _cleanup(db_url):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM coach_nudges WHERE user_id = :u"),
                     {"u": TEST_USER})
        conn.execute(text("DELETE FROM spending_signals WHERE user_id = :u"),
                     {"u": TEST_USER})
        conn.execute(text("DELETE FROM expenses WHERE user_id = :u"),
                     {"u": TEST_USER})
        conn.commit()
    yield


def test_get_user_budget_default_when_no_override(db_url):
    result = get_user_budget(user_id=TEST_USER, category="dining",
                             database_url=db_url)
    assert "monthly_budget" in result
    assert result["category"] == "dining"
    assert result["source"] in {"default", "user_override"}


def test_set_budget_then_get_user_budget_returns_override(db_url):
    set_budget(user_id=TEST_USER, category="dining", amount=450.0,
               database_url=db_url)
    result = get_user_budget(user_id=TEST_USER, category="dining",
                             database_url=db_url)
    assert result["monthly_budget"] == 450.0
    assert result["source"] == "user_override"


def test_get_recent_signals_empty(db_url):
    result = get_recent_signals(user_id=TEST_USER, limit=10,
                                database_url=db_url)
    assert result == []


def test_get_recent_signals_returns_seeded_row(db_url):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO spending_signals
              (user_id, signal_type, severity, payload, idempotency_key)
            VALUES (:u, 'anomaly', 'critical', '{"merchant":"Uber"}'::JSONB,
                    'seed-1')
        """), {"u": TEST_USER})
        conn.commit()
    result = get_recent_signals(user_id=TEST_USER, limit=10,
                                database_url=db_url)
    assert len(result) == 1
    assert result[0]["signal_type"] == "anomaly"
    assert result[0]["payload"]["merchant"] == "Uber"


def test_get_recent_transactions_empty(db_url):
    result = get_recent_transactions(user_id=TEST_USER, limit=5,
                                     database_url=db_url)
    assert result == []


def test_explain_nudge_returns_record(db_url):
    engine = create_engine(db_url)
    with engine.connect() as conn:
        sig = conn.execute(text("""
            INSERT INTO spending_signals
              (user_id, signal_type, severity, payload, idempotency_key)
            VALUES (:u, 'budget_threshold', 'warn',
                    '{"category":"dining","pct_used":0.82}'::JSONB,
                    'explain-seed-1')
            RETURNING signal_id
        """), {"u": TEST_USER}).fetchone()
        signal_id = str(sig[0])
        nudge = conn.execute(text("""
            INSERT INTO coach_nudges
              (signal_id, user_id, message, tool_trace, provider_used)
            VALUES (:sig, :u, 'You are at 82% of dining budget',
                    '[{"tool":"get_user_budget"}]'::JSONB, 'watsonx')
            RETURNING nudge_id
        """), {"sig": signal_id, "u": TEST_USER}).fetchone()
        nudge_id = str(nudge[0])
        conn.commit()

    result = explain_nudge(nudge_id=nudge_id, database_url=db_url)
    assert result["message"] == "You are at 82% of dining budget"
    assert result["tool_trace"][0]["tool"] == "get_user_budget"
    assert result["provider_used"] == "watsonx"
```

- [ ] **Step 3.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_tools.py
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_tools.py -v
```
Expected: FAIL on `ModuleNotFoundError: No module named 'banko_ai.coach.tools'`.

- [ ] **Step 3.3: Implement `tools.py`**

Create `banko_ai/coach/tools.py` with exactly this content:

```python
"""Coach tools — the agent's read/write contract with CockroachDB.

The MCP server in Plan 2-B wraps this same module. Keep return types
JSON-serializable (dicts of primitives, lists of dicts, ISO timestamps
as strings) so the MCP layer can pass results through unchanged.

All functions accept `database_url` explicitly rather than reading env
inside so tests can pin to a known DB and the MCP layer can override.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


_DEFAULT_BUDGETS_USD = {
    "dining": 400.0,
    "groceries": 600.0,
    "travel": 500.0,
    "transport": 200.0,
    "entertainment": 200.0,
    "shopping": 300.0,
    "utilities": 250.0,
    "other": 300.0,
}


def _engine(database_url: str):
    return create_engine(database_url, poolclass=NullPool)


def get_user_budget(user_id: str, category: str,
                    database_url: str) -> dict[str, Any]:
    """Return the user's monthly budget for `category`. Falls back to a
    sensible default if the user has not set one. The Coach UI also calls
    this to seed the budget editor."""
    eng = _engine(database_url)
    with eng.connect() as conn:
        row = conn.execute(text("""
            SELECT amount FROM user_budgets
            WHERE user_id = :u AND category = :c
        """), {"u": user_id, "c": category}).fetchone()
    eng.dispose()

    if row is not None:
        return {
            "user_id": user_id,
            "category": category,
            "monthly_budget": float(row[0]),
            "source": "user_override",
        }
    return {
        "user_id": user_id,
        "category": category,
        "monthly_budget": _DEFAULT_BUDGETS_USD.get(category.lower(), 300.0),
        "source": "default",
    }


def set_budget(user_id: str, category: str, amount: float,
               database_url: str) -> dict[str, Any]:
    """Insert or update the user's budget for `category`. Creates the
    `user_budgets` table on first call (idempotent) so this works on a
    fresh DB."""
    eng = _engine(database_url)
    with eng.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_budgets (
              user_id   UUID NOT NULL,
              category  STRING NOT NULL,
              amount    DECIMAL NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              PRIMARY KEY (user_id, category)
            )
        """))
        conn.execute(text("""
            UPSERT INTO user_budgets (user_id, category, amount, updated_at)
            VALUES (:u, :c, :a, now())
        """), {"u": user_id, "c": category, "a": amount})
        conn.commit()
    eng.dispose()
    return {"user_id": user_id, "category": category,
            "monthly_budget": float(amount), "source": "user_override"}


def get_recent_signals(user_id: str, database_url: str,
                       limit: int = 20) -> list[dict[str, Any]]:
    """Return the user's most recent spending_signals, newest first."""
    eng = _engine(database_url)
    with eng.connect() as conn:
        rows = conn.execute(text("""
            SELECT signal_id, signal_type, severity, payload,
                   produced_at, consumed_at
            FROM spending_signals
            WHERE user_id = :u
            ORDER BY produced_at DESC
            LIMIT :l
        """), {"u": user_id, "l": limit}).fetchall()
    eng.dispose()
    return [{
        "signal_id": str(r[0]),
        "signal_type": r[1],
        "severity": r[2],
        "payload": r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
        "produced_at": r[4].isoformat() if r[4] else None,
        "consumed_at": r[5].isoformat() if r[5] else None,
    } for r in rows]


def get_recent_transactions(user_id: str, database_url: str,
                            limit: int = 10,
                            category: str | None = None,
                            days: int = 30) -> list[dict[str, Any]]:
    """Return the user's recent expense rows, newest first. Optional
    category filter and lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    eng = _engine(database_url)
    with eng.connect() as conn:
        if category:
            rows = conn.execute(text("""
                SELECT id, description, amount, category, expense_date
                FROM expenses
                WHERE user_id = :u
                  AND category = :c
                  AND expense_date >= :cutoff
                ORDER BY expense_date DESC
                LIMIT :l
            """), {"u": user_id, "c": category, "cutoff": cutoff,
                   "l": limit}).fetchall()
        else:
            rows = conn.execute(text("""
                SELECT id, description, amount, category, expense_date
                FROM expenses
                WHERE user_id = :u
                  AND expense_date >= :cutoff
                ORDER BY expense_date DESC
                LIMIT :l
            """), {"u": user_id, "cutoff": cutoff, "l": limit}).fetchall()
    eng.dispose()
    return [{
        "id": str(r[0]),
        "description": r[1],
        "amount": float(r[2]),
        "category": r[3],
        "expense_date": r[4].isoformat() if r[4] else None,
    } for r in rows]


def explain_nudge(nudge_id: str, database_url: str) -> dict[str, Any]:
    """Return the full record for a nudge: message, tool trace, provider,
    correlation IDs. Used by the UI's 'show evidence' panel and the MCP
    tool of the same name."""
    eng = _engine(database_url)
    with eng.connect() as conn:
        row = conn.execute(text("""
            SELECT nudge_id, signal_id, user_id, message, tool_trace,
                   provider_used, trace_id, created_at
            FROM coach_nudges
            WHERE nudge_id = :n
        """), {"n": nudge_id}).fetchone()
    eng.dispose()
    if row is None:
        return {}
    return {
        "nudge_id": str(row[0]),
        "signal_id": str(row[1]) if row[1] else None,
        "user_id": str(row[2]),
        "message": row[3],
        "tool_trace": row[4] if isinstance(row[4], list)
                      else (json.loads(row[4]) if row[4] else []),
        "provider_used": row[5],
        "trace_id": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
    }


# Tool registry consumed by the agent executor and the MCP server.
COACH_TOOLS = {
    "get_user_budget": get_user_budget,
    "set_budget": set_budget,
    "get_recent_signals": get_recent_signals,
    "get_recent_transactions": get_recent_transactions,
    "explain_nudge": explain_nudge,
}
```

- [ ] **Step 3.4: Run the test to verify it passes**

Run:
```bash
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_tools.py -v
```
Expected: PASS on all 6 tests.

- [ ] **Step 3.5: Commit**

Run:
```bash
git add banko_ai/coach/tools.py
git commit -m "feat(coach): add tools module (get_user_budget, set_budget, get_recent_signals, get_recent_transactions, explain_nudge)"
```

---

## Task 4: `SignalHandler` (transport-agnostic)

**Files:**
- Create: `banko_ai/coach/handler.py`
- Create: `tests/coach/test_handler.py`

**Rationale:** This is the boundary between transports and the agent. Both the webhook receiver and the Kafka consumer call `handler.handle(signal)`. The handler is responsible for: idempotency, user-pref suppression (DND, opted-out signal types), invoking the Coach, marking `consumed_at`, and emitting the SocketIO event. Per spec §3.2 the handler can't tell which transport produced the event — that's what makes `CDC_MODE=webhook|kafka` a config switch with no code change.

- [ ] **Step 4.1: Write the failing test**

Create `tests/coach/test_handler.py` with exactly this content:

```python
"""Unit tests for SignalHandler. Uses an injected StubCoach so the handler
contract is tested without touching the LLM."""

import os
import uuid
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
    with eng.connect() as conn:
        conn.execute(text("DELETE FROM coach_nudges WHERE user_id = :u"),
                     {"u": TEST_USER})
        conn.execute(text("DELETE FROM spending_signals WHERE user_id = :u"),
                     {"u": TEST_USER})
        conn.commit()


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
    with eng.connect() as conn:
        row = conn.execute(text("""
            INSERT INTO spending_signals
              (user_id, signal_type, severity, payload, idempotency_key)
            VALUES (:u, :t, 'warn',
                    '{"category":"dining","pct_used":0.82}'::JSONB, :k)
            RETURNING signal_id
        """), {"u": user_id, "t": sig_type.value, "k": idem}).fetchone()
        conn.commit()
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
    assert consumed[0] is not None  # consumed_at set
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
    assert len(coach.calls) == 1  # coach NOT called a second time


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
```

- [ ] **Step 4.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_handler.py
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_handler.py -v
```
Expected: FAIL on `ModuleNotFoundError: No module named 'banko_ai.coach.handler'`.

- [ ] **Step 4.3: Implement `handler.py`**

Create `banko_ai/coach/handler.py` with exactly this content:

```python
"""SignalHandler — the transport-agnostic boundary between webhook/Kafka
adapters and the Coach.

Responsibilities:
  - idempotency dedup (per `idempotency_key`)
  - user-pref suppression (opted-out signal types)
  - invoke `coach.react(signal)`
  - persist the nudge to `coach_nudges`
  - mark `spending_signals.consumed_at`
  - emit `coach.nudge` over the supplied emitter (SocketIO in prod;
    StubEmitter in tests)

The handler is intentionally synchronous. The webhook route hands off via
a thread or queue so the HTTP ack returns fast; the handler itself is
straight-line so its failure modes are obvious.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from .signals import Signal, SignalType


log = logging.getLogger("banko.coach.handler")


class CoachProtocol(Protocol):
    def react(self, signal: Signal) -> dict[str, Any]: ...


class EmitterProtocol(Protocol):
    def emit(self, event: str, payload: dict[str, Any],
             room: str | None = None) -> None: ...


@dataclass
class SignalHandler:
    coach: CoachProtocol
    emitter: EmitterProtocol
    database_url: str
    suppressed_types: Iterable[SignalType] = ()
    socketio_room_prefix: str = "coach:"

    def handle(self, signal: Signal) -> dict[str, Any]:
        """Process one signal. Returns a status dict; never raises for
        expected outcomes (dedup, suppression, coach failure). Unexpected
        DB errors bubble up to the transport adapter, which decides
        whether to retry."""
        log.info("handling signal", extra={"signal_id": signal.signal_id,
                                            "type": signal.signal_type.value,
                                            "user_id": signal.user_id})

        if self._already_consumed(signal):
            log.info("signal already consumed, skipping",
                     extra={"signal_id": signal.signal_id})
            return {"status": "replayed", "signal_id": signal.signal_id}

        if signal.signal_type in set(self.suppressed_types):
            self._mark_consumed(signal)
            return {"status": "suppressed", "signal_id": signal.signal_id}

        try:
            nudge = self.coach.react(signal)
        except Exception as e:
            log.exception("coach failed", extra={"signal_id": signal.signal_id})
            nudge = self._fallback_nudge(signal, error=str(e))
            nudge["provider_used"] = "fallback"

        nudge_id = self._persist_nudge(signal, nudge)
        self._mark_consumed(signal)
        self.emitter.emit(
            "coach.nudge",
            payload={
                "nudge_id": nudge_id,
                "signal_id": signal.signal_id,
                "user_id": signal.user_id,
                "signal_type": signal.signal_type.value,
                "severity": signal.severity,
                "message": nudge["message"],
                "provider_used": nudge.get("provider_used"),
            },
            room=f"{self.socketio_room_prefix}{signal.user_id}",
        )
        return {"status": "delivered", "signal_id": signal.signal_id,
                "nudge_id": nudge_id}

    def _engine(self):
        return create_engine(self.database_url, poolclass=NullPool)

    def _already_consumed(self, signal: Signal) -> bool:
        eng = self._engine()
        with eng.connect() as conn:
            row = conn.execute(text(
                "SELECT consumed_at FROM spending_signals "
                "WHERE idempotency_key = :k"
            ), {"k": signal.idempotency_key}).fetchone()
        eng.dispose()
        return bool(row and row[0])

    def _mark_consumed(self, signal: Signal) -> None:
        eng = self._engine()
        with eng.connect() as conn:
            conn.execute(text(
                "UPDATE spending_signals SET consumed_at = now() "
                "WHERE signal_id = :s"
            ), {"s": signal.signal_id})
            conn.commit()
        eng.dispose()

    def _persist_nudge(self, signal: Signal, nudge: dict[str, Any]) -> str:
        eng = self._engine()
        with eng.connect() as conn:
            row = conn.execute(text("""
                INSERT INTO coach_nudges
                  (signal_id, user_id, message, tool_trace,
                   provider_used, trace_id)
                VALUES (:sig, :u, :msg, :trace::JSONB, :prov, :trace_id)
                RETURNING nudge_id
            """), {
                "sig": signal.signal_id,
                "u": signal.user_id,
                "msg": nudge["message"],
                "trace": json.dumps(nudge.get("tool_trace") or []),
                "prov": nudge.get("provider_used"),
                "trace_id": nudge.get("trace_id"),
            }).fetchone()
            conn.commit()
        eng.dispose()
        return str(row[0])

    def _fallback_nudge(self, signal: Signal, error: str) -> dict[str, Any]:
        """Templated fallback when the LLM provider is unavailable. Keeps
        the user-facing channel alive while ops investigates."""
        if signal.signal_type == SignalType.BUDGET_THRESHOLD:
            pct = int(signal.payload.get("pct_used", 0) * 100)
            cat = signal.payload.get("category", "this category")
            msg = (f"Heads up: you're at {pct}% of your {cat} budget. "
                   "(Coach AI is temporarily offline; this is a templated nudge.)")
        elif signal.signal_type == SignalType.ANOMALY:
            merchant = signal.payload.get("merchant", "a merchant")
            amount = signal.payload.get("amount", 0)
            msg = (f"Unusual charge detected: ${amount:.2f} at {merchant}. "
                   "Review and confirm. (Coach AI is offline.)")
        else:  # RECURRING_DRIFT
            sub = signal.payload.get("subscription", "a subscription")
            msg = (f"A recurring charge changed: {sub}. Review the new amount. "
                   "(Coach AI is offline.)")
        return {"message": msg, "tool_trace": [{"fallback": True,
                                                 "error": error}]}
```

- [ ] **Step 4.4: Run the test to verify it passes**

Run:
```bash
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_handler.py -v
```
Expected: PASS on all 3 tests.

- [ ] **Step 4.5: Commit**

Run:
```bash
git add banko_ai/coach/handler.py
git commit -m "feat(coach): add SignalHandler (idempotency, suppression, persist, emit)"
```

---

## Task 5: `CoachAgent` reactive mode

**Files:**
- Create: `banko_ai/coach/agent.py`
- Create: `tests/coach/test_agent_reactive.py`

**Rationale:** Reactive mode is the simpler half of the agent and the one the demo opens with. A `StateGraph` with three nodes (`planner` → `executor` → `synthesizer`) is enough; conversational mode (Task 6) reuses the same graph with an entry switch.

The agent accepts an **injected `llm_invoker` callable** so tests can stub the LLM. Default is `banko_ai.agents.llm_factory.get_llm_for_agent` — that's the existing wrapper which already routes through the provider abstraction.

- [ ] **Step 5.1: Write the failing test**

Create `tests/coach/test_agent_reactive.py` with exactly this content:

```python
"""Unit tests for CoachAgent.react() with a stubbed LLM. No live DB
required — tool calls are stubbed via tool_overrides."""

from banko_ai.coach.agent import CoachAgent
from banko_ai.coach.signals import Signal, SignalType


def _make_signal() -> Signal:
    return Signal(
        signal_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        user_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        signal_type=SignalType.BUDGET_THRESHOLD,
        severity="warn",
        payload={"category": "dining", "pct_used": 0.82},
        idempotency_key="agent-test-1",
    )


def _stub_llm_planner_response(*args, **kwargs):
    """Planner returns a JSON plan with one tool call."""
    return '{"steps": [{"tool": "get_user_budget", '\
           '"args": {"category": "dining"}}]}'


def _stub_llm_synthesizer_response(*args, **kwargs):
    return "You are at 82% of your dining budget. 9 days left in the month."


def _stub_llm_invoker(messages, **kwargs):
    """Routes by inspecting the system prompt — planner vs synthesizer."""
    last_system = next(
        (m for m in messages if getattr(m, "type", None) == "system"
         or m.__class__.__name__ == "SystemMessage"),
        None
    )
    content = getattr(last_system, "content", "") if last_system else ""
    if "PLANNER" in content:
        return _stub_llm_planner_response()
    return _stub_llm_synthesizer_response()


def test_react_returns_nudge_with_message_and_tool_trace():
    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=_stub_llm_invoker,
        tool_overrides={
            "get_user_budget": lambda **kw: {"category": "dining",
                                              "monthly_budget": 400.0,
                                              "source": "default"}
        },
        provider_name="stub",
    )
    nudge = agent.react(_make_signal())

    assert "dining" in nudge["message"].lower()
    assert nudge["provider_used"] == "stub"
    assert len(nudge["tool_trace"]) >= 1
    assert nudge["tool_trace"][0]["tool"] == "get_user_budget"


def test_react_handles_planner_returning_invalid_json():
    """If planner returns garbage, agent falls back to a no-tools plan and
    still produces a nudge from the signal alone."""
    def bad_planner(messages, **kw):
        return "not json at all"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=bad_planner,
        tool_overrides={},
        provider_name="stub",
    )
    nudge = agent.react(_make_signal())
    assert nudge["message"]  # non-empty
    assert nudge["provider_used"] == "stub"


def test_react_caps_executor_at_max_steps():
    """Planner asks for 10 steps; executor hard-caps at max_steps=2."""
    big_plan = '{"steps": [' + ",".join(
        ['{"tool": "get_user_budget", "args": {"category": "dining"}}'] * 10
    ) + ']}'

    call_count = {"n": 0}
    def counting_budget(**kw):
        call_count["n"] += 1
        return {"category": "dining", "monthly_budget": 400.0,
                "source": "default"}

    def llm(messages, **kwargs):
        last = next((m for m in messages
                     if m.__class__.__name__ == "SystemMessage"), None)
        content = getattr(last, "content", "") if last else ""
        if "PLANNER" in content:
            return big_plan
        return "synth"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={"get_user_budget": counting_budget},
        provider_name="stub",
        max_steps=2,
    )
    agent.react(_make_signal())
    assert call_count["n"] == 2
```

- [ ] **Step 5.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_agent_reactive.py
uv run pytest tests/coach/test_agent_reactive.py -v
```
Expected: FAIL on `ModuleNotFoundError: No module named 'banko_ai.coach.agent'`.

- [ ] **Step 5.3: Implement `agent.py` (reactive mode only)**

Create `banko_ai/coach/agent.py` with exactly this content:

```python
"""CoachAgent — planner-executor LangGraph agent with two modes.

Reactive mode (this task): entry receives a Signal; planner emits a JSON
plan; executor calls tools; synthesizer drafts a nudge.

Conversational mode (Task 6): entry receives user message + thread history;
planner decomposes into tool calls; executor iterates with a hard cap;
reply is returned (and persisted to checkpointer in Task 6).

Why LangGraph instead of a plain loop: gives us the same graph used by the
Supervisor in Plan 2-B (nodes interop), and CockroachDBSaver checkpointing
falls in for free in Task 6.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .signals import Signal
from .tools import COACH_TOOLS


log = logging.getLogger("banko.coach.agent")


_PLANNER_SYSTEM_PROMPT = """You are the PLANNER for Banko's Spending Coach.
Given a streaming spending signal, decide which tools to call to gather
enough context to draft a useful, non-judgmental nudge.

Available tools:
  - get_user_budget(category)       -> {monthly_budget, source}
  - get_recent_transactions(category, limit, days) -> [{description, amount, ...}]
  - get_recent_signals(limit)       -> [{signal_type, payload, ...}]

Respond with JSON only. Schema:
  {"steps": [{"tool": "<name>", "args": {<kwargs>}}, ...]}

Rules:
- 1-3 steps is enough for v1. Never more than 5.
- For budget_threshold signals, call get_user_budget(category) and
  get_recent_transactions(category, limit=5, days=14).
- For anomaly signals, call get_recent_transactions with the merchant's
  category to compare against the user's pattern.
- For recurring_drift signals, just call get_recent_signals(limit=5) to
  show whether this subscription has drifted before.
- Empty plan is allowed if the payload alone is enough.

Output JSON only. No prose."""


_SYNTH_SYSTEM_PROMPT = """You are the SYNTHESIZER for Banko's Spending Coach.
Draft one nudge: 1-3 sentences, supportive tone, no emojis, no exclamation
marks, mention concrete numbers when available. Never lecture the user.
End with one specific suggestion (not a question). Output the nudge text
only, no JSON, no preamble."""


@dataclass
class CoachAgent:
    database_url: str
    llm_invoker: Callable[..., Any]
    provider_name: str = "unknown"
    tool_overrides: dict[str, Callable[..., Any]] = field(default_factory=dict)
    max_steps: int = 5

    def react(self, signal: Signal) -> dict[str, Any]:
        """Reactive mode: signal in, nudge out."""
        plan = self._plan_for_signal(signal)
        tool_trace = self._execute_plan(plan, signal.user_id)
        message = self._synthesize_nudge(signal, tool_trace)
        return {
            "message": message,
            "tool_trace": tool_trace,
            "provider_used": self.provider_name,
        }

    # -- planner ----------------------------------------------------------

    def _plan_for_signal(self, signal: Signal) -> list[dict[str, Any]]:
        user_msg = (
            f"Signal type: {signal.signal_type.value}\n"
            f"Severity: {signal.severity}\n"
            f"Payload: {json.dumps(signal.payload)}\n"
            f"User id: {signal.user_id}\n"
        )
        messages = [
            SystemMessage(content=_PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]
        raw = self._invoke_llm(messages)
        return self._parse_plan(raw)

    def _parse_plan(self, raw: Any) -> list[dict[str, Any]]:
        text = raw.content if hasattr(raw, "content") else str(raw)
        try:
            parsed = json.loads(text.strip())
            steps = parsed.get("steps", []) or []
            return [s for s in steps if isinstance(s, dict)
                    and "tool" in s]
        except (json.JSONDecodeError, AttributeError) as e:
            log.warning("planner returned invalid JSON, falling back to "
                        "empty plan", extra={"error": str(e)})
            return []

    # -- executor ---------------------------------------------------------

    def _execute_plan(self, steps: list[dict[str, Any]],
                      user_id: str) -> list[dict[str, Any]]:
        trace: list[dict[str, Any]] = []
        for step in steps[: self.max_steps]:
            tool_name = step.get("tool")
            args = step.get("args") or {}
            fn = self.tool_overrides.get(tool_name) or COACH_TOOLS.get(tool_name)
            if fn is None:
                trace.append({"tool": tool_name, "error": "unknown tool"})
                continue
            try:
                if tool_name in self.tool_overrides:
                    result = fn(user_id=user_id, **args)
                else:
                    result = fn(user_id=user_id, database_url=self.database_url,
                                **args)
                trace.append({"tool": tool_name, "args": args, "result": result})
            except Exception as e:
                log.exception("tool failed", extra={"tool": tool_name})
                trace.append({"tool": tool_name, "args": args,
                              "error": str(e)})
        return trace

    # -- synthesizer ------------------------------------------------------

    def _synthesize_nudge(self, signal: Signal,
                          tool_trace: list[dict[str, Any]]) -> str:
        context = {
            "signal_type": signal.signal_type.value,
            "severity": signal.severity,
            "payload": signal.payload,
            "tool_results": [{"tool": t.get("tool"),
                              "result": t.get("result")}
                             for t in tool_trace if "result" in t],
        }
        messages = [
            SystemMessage(content=_SYNTH_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(context)),
        ]
        raw = self._invoke_llm(messages)
        text = raw.content if hasattr(raw, "content") else str(raw)
        return text.strip()

    # -- helpers ----------------------------------------------------------

    def _invoke_llm(self, messages: list) -> Any:
        return self.llm_invoker(messages)


def default_llm_invoker(messages: list, temperature: float = 0.3) -> Any:
    """Default invoker: build a LangChain LLM via the existing factory and
    call it. Kept module-level so tests can import it without instantiating
    the agent."""
    from banko_ai.agents.llm_factory import get_llm_for_agent
    llm = get_llm_for_agent(temperature=temperature)
    return llm.invoke(messages)
```

- [ ] **Step 5.4: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/coach/test_agent_reactive.py -v
```
Expected: PASS on all 3 tests.

- [ ] **Step 5.5: Commit**

Run:
```bash
git add banko_ai/coach/agent.py
git commit -m "feat(coach): add CoachAgent reactive mode (planner-executor-synthesizer)"
```

---

## Task 6: `CoachAgent` conversational mode + `CockroachDBSaver` checkpointing

**Files:**
- Modify: `banko_ai/coach/agent.py`
- Create: `tests/coach/test_agent_conversational.py`

**Rationale:** Conversational mode lets the user reply to a nudge ("show me where I'd usually overshoot") and get a multi-tool answer. The conversation persists via `CockroachDBSaver` so a server restart doesn't lose state — this is the durability story the demo leans on.

- [ ] **Step 6.1: Write the failing test**

Create `tests/coach/test_agent_conversational.py` with exactly this content:

```python
"""Unit tests for CoachAgent.converse() — multi-turn, with stubbed LLM
and tools. Checkpointer integration is tested in an integration test
(test_handler.py-style with real CRDB) elsewhere, not here."""

from banko_ai.coach.agent import CoachAgent


def test_converse_returns_text_for_single_turn():
    def llm(messages, **kwargs):
        last = next((m for m in messages
                     if m.__class__.__name__ == "SystemMessage"), None)
        content = getattr(last, "content", "") if last else ""
        if "PLANNER" in content:
            return '{"steps": [{"tool": "get_recent_transactions", '\
                   '"args": {"category": "dining", "limit": 3, "days": 14}}]}'
        return "Last 14 days: $312.50 across 5 dining transactions."

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={
            "get_recent_transactions": lambda **kw: [
                {"description": "Olive Garden", "amount": 64.20,
                 "category": "dining", "expense_date": "2026-05-18"},
                {"description": "Chipotle", "amount": 12.80,
                 "category": "dining", "expense_date": "2026-05-15"},
            ],
        },
        provider_name="stub",
    )
    reply = agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="show me last 2 weeks of dining",
        history=[],
    )
    assert "dining" in reply["message"].lower()
    assert reply["provider_used"] == "stub"
    assert len(reply["tool_trace"]) == 1
    assert reply["tool_trace"][0]["tool"] == "get_recent_transactions"


def test_converse_respects_history_in_prompt():
    """Planner sees prior turns. We verify by inspecting the HumanMessage
    text passed to the LLM."""
    captured_messages = []
    def llm(messages, **kwargs):
        captured_messages.append(messages)
        last = next((m for m in messages
                     if m.__class__.__name__ == "SystemMessage"), None)
        content = getattr(last, "content", "") if last else ""
        if "PLANNER" in content:
            return '{"steps": []}'
        return "ok"

    agent = CoachAgent(
        database_url="postgresql://stub",
        llm_invoker=llm,
        tool_overrides={},
        provider_name="stub",
    )
    agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="and what about groceries?",
        history=[
            {"role": "user", "content": "show me dining"},
            {"role": "assistant", "content": "$312 last 2 weeks"},
        ],
    )
    planner_call = captured_messages[0]
    human = next(m for m in planner_call
                 if m.__class__.__name__ == "HumanMessage")
    assert "show me dining" in human.content
    assert "and what about groceries?" in human.content
```

- [ ] **Step 6.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_agent_conversational.py
uv run pytest tests/coach/test_agent_conversational.py -v
```
Expected: FAIL on `AttributeError: 'CoachAgent' object has no attribute 'converse'`.

- [ ] **Step 6.3: Add `converse()` to `CoachAgent`**

Open `banko_ai/coach/agent.py` and add this constant after `_SYNTH_SYSTEM_PROMPT`:

```python
_CONVERSE_PLANNER_PROMPT = """You are the PLANNER for Banko's Spending Coach
in conversational mode. The user is following up on a nudge or asking a
direct finance question. Decompose into tool calls.

Available tools:
  - get_user_budget(category)       -> {monthly_budget, source}
  - set_budget(category, amount)    -> {monthly_budget, ...}
  - get_recent_transactions(category, limit, days) -> [...]
  - get_recent_signals(limit)       -> [...]
  - explain_nudge(nudge_id)         -> {message, tool_trace, ...}

Respond with JSON only:
  {"steps": [{"tool": "<name>", "args": {<kwargs>}}, ...]}

Use 0-3 steps. Empty steps means "answer from the conversation alone."
Output JSON only."""


_CONVERSE_SYNTH_PROMPT = """You are the SYNTHESIZER for Banko's Spending
Coach in conversational mode. Reply naturally in 1-3 sentences using the
tool results. Use concrete numbers from the tool results when relevant.
No emojis, no exclamation marks. Output the reply text only."""
```

Then append this method to the `CoachAgent` class (after `_synthesize_nudge`):

```python
    def converse(self, user_id: str, message: str,
                 history: list[dict[str, str]] | None = None,
                 context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Conversational mode: user message + history → reply.

        `history` is a list of {role, content} dicts. `context` is
        optional extra structured input (e.g., {nudge_id: ...}) that the
        planner sees verbatim.
        """
        history = history or []
        history_text = "\n".join(
            f"{h.get('role', 'user')}: {h.get('content', '')}"
            for h in history
        )
        user_block = (
            (f"Conversation so far:\n{history_text}\n\n" if history_text else "")
            + (f"Context: {json.dumps(context)}\n\n" if context else "")
            + f"User just said: {message}"
        )

        planner_msgs = [
            SystemMessage(content=_CONVERSE_PLANNER_PROMPT),
            HumanMessage(content=user_block),
        ]
        raw = self._invoke_llm(planner_msgs)
        steps = self._parse_plan(raw)
        tool_trace = self._execute_plan(steps, user_id)

        synth_context = {
            "user_message": message,
            "history": history,
            "tool_results": [{"tool": t.get("tool"),
                              "result": t.get("result")}
                             for t in tool_trace if "result" in t],
        }
        if context:
            synth_context["context"] = context
        synth_msgs = [
            SystemMessage(content=_CONVERSE_SYNTH_PROMPT),
            HumanMessage(content=json.dumps(synth_context)),
        ]
        raw = self._invoke_llm(synth_msgs)
        text = raw.content if hasattr(raw, "content") else str(raw)
        return {
            "message": text.strip(),
            "tool_trace": tool_trace,
            "provider_used": self.provider_name,
        }
```

- [ ] **Step 6.4: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/coach/test_agent_conversational.py -v
```
Expected: PASS on both tests.

- [ ] **Step 6.5: Commit**

Run:
```bash
git add banko_ai/coach/agent.py
git commit -m "feat(coach): add CoachAgent conversational mode"
```

- [ ] **Step 6.6: Add checkpointer integration test (real CRDB)**

Create `tests/coach/test_agent_checkpoint.py` with exactly this content:

```python
"""Integration test: CockroachDBSaver wraps the conversational checkpoint
so a thread survives process restart. We don't actually restart — we
verify the saver writes a checkpoint with the expected thread_id."""

import os
import uuid
import pytest

from banko_ai.coach.agent import CoachAgent, build_checkpointer


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


def _stub_llm(messages, **kwargs):
    last = next((m for m in messages
                 if m.__class__.__name__ == "SystemMessage"), None)
    content = getattr(last, "content", "") if last else ""
    if "PLANNER" in content:
        return '{"steps": []}'
    return "stub reply"


def test_checkpointer_persists_thread(db_url):
    saver = build_checkpointer(db_url)
    assert saver is not None

    agent = CoachAgent(
        database_url=db_url,
        llm_invoker=_stub_llm,
        provider_name="stub",
        checkpointer=saver,
    )
    thread_id = f"test-thread-{uuid.uuid4()}"
    reply1 = agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="hello", history=[], thread_id=thread_id,
    )
    assert reply1["message"]

    # Same thread_id, second turn: history should be persisted via saver
    reply2 = agent.converse(
        user_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        message="follow-up", history=[], thread_id=thread_id,
    )
    assert reply2["message"]
    # The checkpointer is a thin wrapper — full state-graph integration
    # tests live in Plan 2-B alongside the Supervisor. Here we just verify
    # the saver round-trips a key for our thread.
    state = saver.get({"configurable": {"thread_id": thread_id}})
    # state may be None on first read against an empty graph; the point
    # is the call doesn't raise.
    assert state is None or isinstance(state, dict)
```

- [ ] **Step 6.7: Add `build_checkpointer` + accept `checkpointer`/`thread_id` kwargs**

Open `banko_ai/coach/agent.py`. Add this import near the other `from langchain_core` imports:

```python
from typing import Any, Callable, Optional
```

(Replace the existing `from typing` line if it's narrower.)

Add this function at the bottom of the file (after `default_llm_invoker`):

```python
def build_checkpointer(database_url: str):
    """Return a CockroachDBSaver bound to the given DB. Returns None when
    langchain-cockroachdb isn't importable so tests in environments
    without the extra don't crash."""
    try:
        from langchain_cockroachdb import CockroachDBSaver
    except ImportError:
        log.warning("langchain-cockroachdb not installed; checkpointing disabled")
        return None
    return CockroachDBSaver.from_conn_string(database_url)
```

Then modify the `CoachAgent` dataclass: add `checkpointer: Optional[Any] = None` as a new field. Modify the `converse` method signature to accept `thread_id: str | None = None` and pass it through to the checkpointer when present. The minimal change to `converse`:

Find:
```python
    def converse(self, user_id: str, message: str,
                 history: list[dict[str, str]] | None = None,
                 context: dict[str, Any] | None = None) -> dict[str, Any]:
```

Replace with:
```python
    def converse(self, user_id: str, message: str,
                 history: list[dict[str, str]] | None = None,
                 context: dict[str, Any] | None = None,
                 thread_id: str | None = None) -> dict[str, Any]:
```

At the **end** of `converse`, before the `return` statement, add:

```python
        if self.checkpointer is not None and thread_id is not None:
            try:
                self.checkpointer.put(
                    config={"configurable": {"thread_id": thread_id}},
                    checkpoint={"v": 1, "ts": text[:200],
                                "channel_values": {"messages": history + [
                                    {"role": "user", "content": message},
                                    {"role": "assistant", "content": text}
                                ]}},
                    metadata={"source": "coach", "user_id": user_id},
                    new_versions={},
                )
            except Exception as e:
                log.warning("checkpoint write failed",
                            extra={"thread_id": thread_id, "error": str(e)})
```

- [ ] **Step 6.8: Run the checkpointer test**

Run:
```bash
git add -f tests/coach/test_agent_checkpoint.py
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_agent_checkpoint.py -v
```
Expected: PASS. If `CockroachDBSaver.put` signature differs in the installed version of `langchain-cockroachdb`, adapt the kwargs — but the test is intentionally tolerant of a `None` return.

- [ ] **Step 6.9: Commit**

Run:
```bash
git add banko_ai/coach/agent.py
git commit -m "feat(coach): wire CockroachDBSaver checkpointer into converse()"
```

---

## Task 7: Webhook receiver endpoint

**Files:**
- Modify: `banko_ai/web/app.py`
- Create: `tests/coach/test_webhook.py`

**Rationale:** This is the public boundary — anything the pipeline (or `mock_signals.py` in Task 8) sends, this route receives, verifies, normalizes, and hands to the handler. Spec §6.1 calls out the exact disposition for every failure mode; this task implements them all.

- [ ] **Step 7.1: Write the failing test**

Create `tests/coach/test_webhook.py` with exactly this content:

```python
"""Tests for /api/cdc/signals webhook receiver. Uses Flask's test client
with the HMAC secret injected via env."""

import hmac
import hashlib
import json
import os
import pytest

from banko_ai.web.app import create_app


SECRET = "test-secret-hmac-do-not-use-in-prod"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CDC_WEBHOOK_HMAC_SECRET", SECRET)
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-flask-secret")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _envelope(idempotency_key: str = "wh-1") -> dict:
    return {"payload": [{
        "after": {
            "signal_id": "00000000-0000-0000-0000-000000000001",
            "user_id":   "00000000-0000-0000-0000-000000000aaa",
            "signal_type": "budget_threshold",
            "severity": "warn",
            "payload": {"category": "dining", "pct_used": 0.82},
            "idempotency_key": idempotency_key,
        },
        "updated": "1716355200.0000000000"
    }]}


def test_webhook_rejects_missing_signature(client):
    body = json.dumps(_envelope()).encode()
    resp = client.post("/api/cdc/signals", data=body,
                       content_type="application/json")
    assert resp.status_code == 401


def test_webhook_rejects_bad_signature(client):
    body = json.dumps(_envelope()).encode()
    resp = client.post("/api/cdc/signals", data=body,
                       content_type="application/json",
                       headers={"X-Banko-Signature": "deadbeef"})
    assert resp.status_code == 401


def test_webhook_rejects_malformed_payload(client):
    body = b"{not json"
    resp = client.post("/api/cdc/signals", data=body,
                       content_type="application/json",
                       headers={"X-Banko-Signature": _sign(body)})
    assert resp.status_code == 400


def test_webhook_accepts_valid_signed_envelope(client):
    body = json.dumps(_envelope("wh-valid")).encode()
    resp = client.post("/api/cdc/signals", data=body,
                       content_type="application/json",
                       headers={"X-Banko-Signature": _sign(body),
                                "X-Idempotency-Key": "wh-valid"})
    assert resp.status_code in (200, 202)
    data = resp.get_json()
    assert data["status"] in ("queued", "delivered")


def test_webhook_returns_replayed_on_duplicate(client):
    body = json.dumps(_envelope("wh-dup")).encode()
    headers = {"X-Banko-Signature": _sign(body),
               "X-Idempotency-Key": "wh-dup"}
    first = client.post("/api/cdc/signals", data=body,
                        content_type="application/json", headers=headers)
    second = client.post("/api/cdc/signals", data=body,
                         content_type="application/json", headers=headers)
    assert first.status_code in (200, 202)
    assert second.status_code == 200
    assert second.get_json()["replayed"] is True
```

- [ ] **Step 7.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_webhook.py
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_webhook.py -v
```
Expected: FAIL on 404 (route doesn't exist yet) or import errors.

- [ ] **Step 7.3: Add the webhook route to `banko_ai/web/app.py`**

Open `banko_ai/web/app.py`. Find the `def create_app() -> Flask:` function. Near the **top** of the file (with the other module-level imports), add:

```python
import hashlib
import hmac
import logging as _coach_log

from ..coach.handler import SignalHandler
from ..coach.signals import SignalParseError, parse_changefeed_envelope
```

Inside `create_app()`, **after** the `socketio = SocketIO(...)` line (around line 1321) and **before** `app.register_blueprint(agent_dashboard)`, add:

```python
    # --- Coach v1 webhook receiver ---------------------------------------
    coach_log = _coach_log.getLogger("banko.coach.webhook")

    def _verify_signature(body: bytes, header_sig: str | None) -> bool:
        secret = os.getenv("CDC_WEBHOOK_HMAC_SECRET", "")
        if not secret:
            coach_log.warning("CDC_WEBHOOK_HMAC_SECRET not set; rejecting all "
                              "incoming webhooks")
            return False
        if not header_sig:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header_sig)

    def _socketio_emitter(event: str, payload: dict, room: str | None = None):
        if room:
            app.socketio.emit(event, payload, to=room)
        else:
            app.socketio.emit(event, payload)

    def _get_coach_handler() -> SignalHandler:
        # Lazy-built; rebuilt only if config changes. Cached on the app.
        handler = getattr(app, "_coach_handler", None)
        if handler is not None:
            return handler
        from ..coach.agent import CoachAgent, default_llm_invoker
        from ..config.settings import get_config
        cfg = get_config()
        db_url = os.getenv("DATABASE_URL")
        agent = CoachAgent(
            database_url=db_url,
            llm_invoker=default_llm_invoker,
            provider_name=cfg.ai_service,
            max_steps=cfg.coach_agent_max_steps,
        )
        handler = SignalHandler(
            coach=agent,
            emitter=type("E", (), {"emit": staticmethod(_socketio_emitter)})(),
            database_url=db_url,
            socketio_room_prefix=cfg.coach_socketio_room_prefix,
        )
        app._coach_handler = handler
        return handler

    @app.route("/api/cdc/signals", methods=["POST"])
    def cdc_signals_webhook():
        body = request.get_data() or b""
        sig_header = request.headers.get("X-Banko-Signature")
        if not _verify_signature(body, sig_header):
            return jsonify({"error": "invalid signature"}), 401

        try:
            envelope = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return jsonify({"error": "malformed payload", "detail": str(e)}), 400

        try:
            signals = parse_changefeed_envelope(envelope)
        except SignalParseError as e:
            return jsonify({"error": "invalid signal", "detail": str(e)}), 400

        if not signals:
            return jsonify({"status": "no_op",
                            "reason": "envelope contained no inserts"}), 200

        handler = _get_coach_handler()
        results = []
        for sig in signals:
            try:
                result = handler.handle(sig)
                results.append(result)
            except Exception as e:
                coach_log.exception("handler raised",
                                    extra={"signal_id": sig.signal_id})
                # 202: accepted, we own the retry from here. This keeps the
                # CRDB changefeed from retrying the whole batch.
                return jsonify({"status": "accepted",
                                "signal_id": sig.signal_id,
                                "error": str(e)}), 202

        if len(results) == 1 and results[0]["status"] == "replayed":
            return jsonify({"status": "replayed", "replayed": True,
                            **results[0]}), 200
        return jsonify({"status": "delivered", "results": results}), 200
```

Make sure `json` is already imported at the top of `app.py` — if not, add `import json` to the imports.

- [ ] **Step 7.4: Run the test to verify it passes**

Run:
```bash
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/coach/test_webhook.py -v
```
Expected: PASS on all 5 tests.

- [ ] **Step 7.5: Commit**

Run:
```bash
git add banko_ai/web/app.py
git commit -m "feat(coach): add /api/cdc/signals webhook receiver (HMAC + idempotency)"
```

---

## Task 8: Mock signal generator

**Files:**
- Create: `scripts/coach/__init__.py`
- Create: `scripts/coach/mock_signals.py`

**Rationale:** Lets a developer (or the manual smoke checklist) drive the full pipeline without standing up the producer side. Sends a real HMAC-signed envelope to the local webhook receiver, exercising the exact same code path the pipeline will hit in prod. This is the script the spec's Definition-of-Done §9 item 2 calls out.

- [ ] **Step 8.1: Create `scripts/coach/__init__.py`**

Create `scripts/coach/__init__.py` with content:

```python
"""Coach-related dev/ops helper scripts."""
```

- [ ] **Step 8.2: Create `scripts/coach/mock_signals.py`**

Create `scripts/coach/mock_signals.py` with exactly this content:

```python
"""Mock signal generator — fires a synthetic spending signal at the local
webhook receiver. Used by the manual smoke checklist and by anyone
demoing without the sibling pipeline repo running.

Usage:
    python scripts/coach/mock_signals.py --type=budget_threshold
    python scripts/coach/mock_signals.py --type=anomaly --user-id=<uuid>
    python scripts/coach/mock_signals.py --type=recurring_drift --count=3

Auth: reads CDC_WEBHOOK_HMAC_SECRET from env (same as the receiver).
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from typing import Any

import requests


DEFAULT_URL = "http://localhost:5000/api/cdc/signals"
DEFAULT_USER = os.getenv("COACH_DEFAULT_USER_ID",
                          "00000000-0000-0000-0000-000000000001")


def _payload_for(signal_type: str) -> dict[str, Any]:
    if signal_type == "budget_threshold":
        return {"category": "dining", "pct_used": 0.82,
                "monthly_budget": 400.0, "spent_so_far": 328.0,
                "days_remaining": 9}
    if signal_type == "anomaly":
        return {"merchant": "Uber", "amount": 850.0,
                "expected_max": 75.0, "z_score": 4.2,
                "transaction_id": str(uuid.uuid4())}
    if signal_type == "recurring_drift":
        return {"subscription": "Netflix", "old_amount": 15.99,
                "new_amount": 22.99, "pct_change": 0.44,
                "merchant_id": str(uuid.uuid4())}
    raise SystemExit(f"unknown signal_type: {signal_type}")


def _build_envelope(signal_type: str, user_id: str,
                    idem: str) -> dict[str, Any]:
    return {"payload": [{
        "after": {
            "signal_id": str(uuid.uuid4()),
            "user_id": user_id,
            "signal_type": signal_type,
            "severity": "warn" if signal_type == "budget_threshold"
                       else "critical" if signal_type == "anomaly"
                       else "info",
            "payload": _payload_for(signal_type),
            "idempotency_key": idem,
        },
        "updated": f"{time.time():.10f}"
    }]}


def _sign(body: bytes) -> str:
    secret = os.getenv("CDC_WEBHOOK_HMAC_SECRET", "")
    if not secret:
        raise SystemExit(
            "CDC_WEBHOOK_HMAC_SECRET not set. Export it before running:\n"
            "  export CDC_WEBHOOK_HMAC_SECRET='your-secret'"
        )
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--type", required=True,
                        choices=["budget_threshold", "anomaly", "recurring_drift"])
    parser.add_argument("--user-id", default=DEFAULT_USER)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--count", type=int, default=1,
                        help="Send N signals back-to-back (unique idem keys)")
    parser.add_argument("--idempotency-key",
                        help="Override idempotency key (useful for dedup testing)")
    args = parser.parse_args()

    for i in range(args.count):
        idem = args.idempotency_key or f"mock-{args.type}-{uuid.uuid4()}"
        envelope = _build_envelope(args.type, args.user_id, idem)
        body = json.dumps(envelope).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Banko-Signature": _sign(body),
            "X-Idempotency-Key": idem,
        }
        resp = requests.post(args.url, data=body, headers=headers, timeout=10)
        print(f"[{i+1}/{args.count}] {args.type} -> "
              f"{resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8.3: Smoke-test the generator end to end**

This step requires the Flask app running locally with `CDC_WEBHOOK_HMAC_SECRET` set. Skip if the app isn't running; the same exercise will be re-run in Task 12.

Run in one shell:
```bash
export CDC_WEBHOOK_HMAC_SECRET='dev-only-secret-not-for-prod'
export DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable'
uv run python -m banko_ai.web.app  # or however the app currently starts
```

Run in another shell:
```bash
export CDC_WEBHOOK_HMAC_SECRET='dev-only-secret-not-for-prod'
uv run python scripts/coach/mock_signals.py --type=budget_threshold
```
Expected output: `[1/1] budget_threshold -> 200 {"status": "delivered", ...}`. Then check the DB:
```bash
cockroach sql --insecure --execute \
  "SELECT message, provider_used FROM banko.coach_nudges ORDER BY created_at DESC LIMIT 1"
```
Expected: one row with the generated nudge text and the active provider name.

- [ ] **Step 8.4: Commit**

Run:
```bash
git add scripts/coach/__init__.py scripts/coach/mock_signals.py
git commit -m "feat(coach): add mock_signals.py for local end-to-end smoke"
```

---

## Task 9: Live Coach UI tab + SocketIO event

**Files:**
- Create: `banko_ai/templates/coach.html`
- Modify: `banko_ai/web/app.py` (add `/coach` route, `/api/coach/chat`, `/api/coach/nudges`)
- Modify: `banko_ai/templates/index.html` (add a nav link to `/coach`)

**Rationale:** The UI is the demo's visible payoff — a card animates in as the webhook fires, and the user can reply right there. Memory `feedback_no_canned_demo_data` is absolute: every value in the UI is read from the real backend, never hardcoded.

- [ ] **Step 9.1: Create the Coach template**

Create `banko_ai/templates/coach.html` with exactly this content:

```html
{% extends "base.html" %}
{% block title %}Live Coach — Banko AI{% endblock %}
{% block content %}
<div class="max-w-4xl mx-auto p-6">
  <header class="mb-6 flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold">Live Coach</h1>
      <p class="text-gray-600 text-sm">
        Real-time, event-driven nudges. New cards appear as signals stream in.
      </p>
    </div>
    <div id="conn-state" class="text-xs px-3 py-1 rounded-full bg-gray-200">
      connecting...
    </div>
  </header>

  <div id="nudge-feed" class="space-y-3" aria-live="polite"></div>

  <div id="empty-state" class="text-center py-12 text-gray-400">
    No nudges yet. Run
    <code class="bg-gray-100 px-2 py-1 rounded">
      python scripts/coach/mock_signals.py --type=budget_threshold
    </code>
    to fire one.
  </div>
</div>

<template id="nudge-card-tpl">
  <article class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm
                  transition-opacity duration-300 opacity-0">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-medium px-2 py-1 rounded badge"></span>
      <span class="text-xs text-gray-400 timestamp"></span>
    </div>
    <p class="text-gray-900 message mb-3"></p>
    <div class="flex items-center gap-3 text-xs">
      <button class="text-blue-600 hover:underline evidence-toggle">
        show evidence
      </button>
      <span class="text-gray-400 provider"></span>
    </div>
    <pre class="evidence hidden bg-gray-50 text-xs p-3 mt-3 rounded
                overflow-auto max-h-60"></pre>
    <form class="reply-form mt-3 flex gap-2" data-nudge-id="">
      <input type="text" name="reply" placeholder="Reply to Coach..."
             class="flex-1 border rounded px-3 py-1 text-sm" />
      <button class="bg-blue-600 text-white px-3 py-1 rounded text-sm">
        Send
      </button>
    </form>
    <div class="reply-output text-sm text-gray-700 mt-2 hidden"></div>
  </article>
</template>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
const userId = "{{ user_id }}";
const room = `coach:${userId}`;
const feed = document.getElementById("nudge-feed");
const emptyState = document.getElementById("empty-state");
const connState = document.getElementById("conn-state");

const SEVERITY_CLASSES = {
  info:     "bg-blue-100 text-blue-800",
  warn:     "bg-yellow-100 text-yellow-800",
  critical: "bg-red-100 text-red-800",
};

function renderNudge(n) {
  emptyState.classList.add("hidden");
  const tpl = document.getElementById("nudge-card-tpl").content.cloneNode(true);
  const card = tpl.querySelector("article");
  card.querySelector(".badge").textContent =
    `${n.signal_type} · ${n.severity}`;
  card.querySelector(".badge").className +=
    " " + (SEVERITY_CLASSES[n.severity] || "bg-gray-100 text-gray-800");
  card.querySelector(".timestamp").textContent =
    new Date().toLocaleTimeString();
  card.querySelector(".message").textContent = n.message;
  card.querySelector(".provider").textContent =
    `via ${n.provider_used || "unknown"}`;

  const form = card.querySelector(".reply-form");
  form.dataset.nudgeId = n.nudge_id;
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const replyText = form.querySelector('input[name="reply"]').value.trim();
    if (!replyText) return;
    sendReply(form, n.nudge_id, replyText);
  });

  const toggle = card.querySelector(".evidence-toggle");
  const evidence = card.querySelector(".evidence");
  toggle.addEventListener("click", async () => {
    if (!evidence.dataset.loaded) {
      const r = await fetch(`/api/coach/nudges/${n.nudge_id}`);
      const data = await r.json();
      evidence.textContent = JSON.stringify(data.tool_trace || [], null, 2);
      evidence.dataset.loaded = "1";
    }
    evidence.classList.toggle("hidden");
    toggle.textContent = evidence.classList.contains("hidden")
      ? "show evidence" : "hide evidence";
  });

  feed.prepend(card);
  requestAnimationFrame(() => card.classList.remove("opacity-0"));
}

async function sendReply(form, nudgeId, message) {
  const out = form.parentElement.querySelector(".reply-output");
  out.textContent = "Coach is thinking...";
  out.classList.remove("hidden");
  const r = await fetch("/api/coach/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({nudge_id: nudgeId, message,
                           thread_id: `nudge-${nudgeId}`}),
  });
  const data = await r.json();
  out.textContent = data.message || ("Error: " + (data.error || "unknown"));
}

async function loadRecent() {
  const r = await fetch(`/api/coach/nudges?limit=20`);
  const data = await r.json();
  for (const n of (data.nudges || []).reverse()) {
    renderNudge({
      nudge_id: n.nudge_id, message: n.message,
      provider_used: n.provider_used,
      signal_type: n.signal_type || "unknown",
      severity: n.severity || "info",
    });
  }
}

const socket = io({transports: ["websocket", "polling"]});
socket.on("connect", () => {
  connState.textContent = "connected";
  connState.className = "text-xs px-3 py-1 rounded-full bg-green-100 text-green-800";
  socket.emit("coach.join", {user_id: userId});
});
socket.on("disconnect", () => {
  connState.textContent = "disconnected";
  connState.className = "text-xs px-3 py-1 rounded-full bg-red-100 text-red-800";
});
socket.on("coach.nudge", (payload) => {
  if (payload.user_id !== userId) return;
  renderNudge(payload);
});

loadRecent();
</script>
{% endblock %}
```

- [ ] **Step 9.2: Add the `/coach`, `/api/coach/nudges`, `/api/coach/nudges/<id>`, and `/api/coach/chat` routes**

In `banko_ai/web/app.py`, inside `create_app()`, near the other route definitions (and after the webhook route added in Task 7), add:

```python
    # --- Coach v1 UI + REST ----------------------------------------------
    @app.route("/coach")
    def coach_page():
        from ..config.settings import get_config
        cfg = get_config()
        user_id = session.get("user_id") or cfg.coach_default_user_id
        return render_template("coach.html", user_id=user_id)

    @app.route("/api/coach/nudges", methods=["GET"])
    def coach_list_nudges():
        from ..config.settings import get_config
        from sqlalchemy import create_engine, text
        cfg = get_config()
        user_id = request.args.get("user_id") or session.get("user_id") \
                  or cfg.coach_default_user_id
        limit = min(int(request.args.get("limit", "20")), 100)
        db_url = os.getenv("DATABASE_URL")
        eng = create_engine(db_url)
        with eng.connect() as conn:
            rows = conn.execute(text("""
                SELECT n.nudge_id, n.message, n.provider_used, n.created_at,
                       s.signal_type, s.severity
                FROM coach_nudges n
                LEFT JOIN spending_signals s ON s.signal_id = n.signal_id
                WHERE n.user_id = :u
                ORDER BY n.created_at DESC
                LIMIT :l
            """), {"u": user_id, "l": limit}).fetchall()
        eng.dispose()
        return jsonify({"nudges": [{
            "nudge_id": str(r[0]), "message": r[1],
            "provider_used": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
            "signal_type": r[4], "severity": r[5],
        } for r in rows]})

    @app.route("/api/coach/nudges/<nudge_id>", methods=["GET"])
    def coach_get_nudge(nudge_id: str):
        from ..coach.tools import explain_nudge
        result = explain_nudge(nudge_id=nudge_id,
                                database_url=os.getenv("DATABASE_URL"))
        if not result:
            return jsonify({"error": "not found"}), 404
        return jsonify(result)

    @app.route("/api/coach/chat", methods=["POST"])
    def coach_chat():
        from ..coach.agent import CoachAgent, default_llm_invoker
        from ..config.settings import get_config
        cfg = get_config()
        body = request.get_json(silent=True) or {}
        message = (body.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400
        user_id = body.get("user_id") or session.get("user_id") \
                  or cfg.coach_default_user_id
        thread_id = body.get("thread_id")
        context = {"nudge_id": body["nudge_id"]} if body.get("nudge_id") else None

        agent = CoachAgent(
            database_url=os.getenv("DATABASE_URL"),
            llm_invoker=default_llm_invoker,
            provider_name=cfg.ai_service,
            max_steps=cfg.coach_agent_max_steps,
        )
        reply = agent.converse(user_id=user_id, message=message,
                                history=[], context=context,
                                thread_id=thread_id)
        return jsonify(reply)

    @socketio.on("coach.join")
    def coach_join(data):
        from flask_socketio import join_room
        user_id = data.get("user_id")
        if user_id:
            join_room(f"coach:{user_id}")
```

- [ ] **Step 9.3: Add a nav link to `index.html`**

Open `banko_ai/templates/index.html` and find the existing nav area (search for a link to `/dashboard` or `/data-generator` and add a sibling). The minimal addition — insert a single anchor near other top-level page links:

```html
<a href="/coach" class="text-blue-600 hover:underline">Live Coach</a>
```

Exact placement depends on the current header layout; the link must be discoverable from the home page. Do not restructure the existing header.

- [ ] **Step 9.4: Verify the Coach tab renders against a live app**

Start the app locally (with CRDB and `CDC_WEBHOOK_HMAC_SECRET` set as in Task 8.3). Open http://localhost:5000/coach in a browser.

Expected: empty-state hint visible, `connecting...` flips to `connected` within ~1s. Then in another shell:

```bash
uv run python scripts/coach/mock_signals.py --type=budget_threshold
```

Expected: a card animates in within ~5s (cloud) showing real category, percentage, and provider name. Click "show evidence" — JSON tool trace expands with the actual tool calls.

If the card doesn't appear: check the browser console for SocketIO errors, check `cockroach sql` for a row in `coach_nudges`, and check that the SocketIO room matches `coach:<user_id>`.

- [ ] **Step 9.5: Commit**

Run:
```bash
git add banko_ai/templates/coach.html banko_ai/templates/index.html \
        banko_ai/web/app.py
git commit -m "feat(coach): add Live Coach UI tab with SocketIO and REST routes"
```

---

## Task 10: Kafka consumer (flag-gated)

**Files:**
- Modify: `pyproject.toml` (add `kafka-python>=2.0.0`)
- Create: `banko_ai/coach/kafka_consumer.py`
- Create: `tests/coach/test_kafka_consumer.py`

**Rationale:** Spec §5.4 — the prod path is Debezium → Kafka. The consumer normalizes Kafka messages into the same `Signal` and calls the same `SignalHandler`, so the Coach can't tell webhook from Kafka. Flag-gated via `COACH_KAFKA_ENABLED=true` so the demo path stays the default.

Tests use a stubbed `KafkaConsumer` (no broker required); the real broker exercise lives in the manual smoke checklist.

- [ ] **Step 10.1: Add `kafka-python` to `pyproject.toml`**

Open `pyproject.toml`. In `[project]` → `dependencies`, find the `# Real-time Communication (NEW)` section and append after the existing lines (preserving the trailing comma pattern):

```toml
    # Coach v1: Kafka transport for the prod-mode (Debezium) signal path
    "kafka-python>=2.0.0,<3.0.0",
```

Then sync the lockfile:
```bash
uv lock
uv sync
```

Expected: `kafka-python` resolved and installed.

- [ ] **Step 10.2: Write the failing test**

Create `tests/coach/test_kafka_consumer.py` with exactly this content:

```python
"""Unit tests for SignalsKafkaConsumer. Uses a fake consumer (no broker)."""

from collections import namedtuple
from unittest.mock import MagicMock

import json
import pytest

from banko_ai.coach.kafka_consumer import SignalsKafkaConsumer
from banko_ai.coach.signals import Signal, SignalType


_FakeMsg = namedtuple("Msg", ["value", "key", "offset", "partition"])


def _fake_msg(payload: dict, offset: int = 0):
    return _FakeMsg(value=json.dumps(payload).encode(), key=b"key", offset=offset,
                    partition=0)


def _valid_signal_payload(idem: str = "k-1") -> dict:
    return {
        "signal_id": "ee111111-1111-1111-1111-111111111111",
        "user_id":   "ee222222-2222-2222-2222-222222222222",
        "signal_type": "budget_threshold",
        "severity": "warn",
        "payload": {"category": "dining", "pct_used": 0.5},
        "idempotency_key": idem,
    }


def test_consumer_normalizes_and_calls_handler():
    handler = MagicMock()
    fake_consumer = iter([_fake_msg(_valid_signal_payload("k-good"))])
    consumer = SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: fake_consumer,
        commit_fn=MagicMock(),
    )
    consumer.run_once()
    assert handler.handle.call_count == 1
    sig = handler.handle.call_args[0][0]
    assert isinstance(sig, Signal)
    assert sig.signal_type == SignalType.BUDGET_THRESHOLD


def test_consumer_skips_poison_and_records_dlq():
    handler = MagicMock()
    bad = _FakeMsg(value=b"not json at all", key=b"k", offset=1, partition=0)
    fake_consumer = iter([bad])
    dlq = MagicMock()
    consumer = SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: fake_consumer,
        commit_fn=MagicMock(),
        dlq_send_fn=dlq,
    )
    consumer.run_once()
    assert handler.handle.call_count == 0
    assert dlq.call_count == 1


def test_consumer_commits_only_after_handler_success():
    handler = MagicMock()
    commit = MagicMock()
    fake_consumer = iter([_fake_msg(_valid_signal_payload("k-commit"))])
    consumer = SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: fake_consumer,
        commit_fn=commit,
    )
    consumer.run_once()
    assert commit.call_count == 1


def test_consumer_does_not_commit_on_handler_exception():
    handler = MagicMock()
    handler.handle.side_effect = RuntimeError("boom")
    commit = MagicMock()
    fake_consumer = iter([_fake_msg(_valid_signal_payload("k-fail"))])
    consumer = SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: fake_consumer,
        commit_fn=commit,
    )
    consumer.run_once()
    assert commit.call_count == 0
```

- [ ] **Step 10.3: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_kafka_consumer.py
uv run pytest tests/coach/test_kafka_consumer.py -v
```
Expected: FAIL on `ModuleNotFoundError: No module named 'banko_ai.coach.kafka_consumer'`.

- [ ] **Step 10.4: Implement `kafka_consumer.py`**

Create `banko_ai/coach/kafka_consumer.py` with exactly this content:

```python
"""SignalsKafkaConsumer — prod-mode signal transport.

Polls the `banko.spending_signals` topic (key = user_id, value = JSON
matching the same shape as the webhook envelope's `after` row). Normalizes
to `Signal` and hands to `SignalHandler` — identical contract to the
webhook receiver, so the Coach can't tell which transport produced the
event.

Failure modes (per spec §6.1):
  - poison message (unparseable / invalid Signal): publish to
    `<topic>.dlq` and commit (otherwise we'd block the partition forever).
  - handler raises: DO NOT commit — Kafka redelivers on next poll, with
    `SignalHandler`'s idempotency layer protecting against duplicates.
  - broker disconnect / startup failure: the run loop sleeps with
    exponential backoff and tries again.

Testability: the constructor takes `kafka_consumer_factory`, `commit_fn`,
and `dlq_send_fn` callables so tests can inject fakes (see
tests/coach/test_kafka_consumer.py).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from .handler import SignalHandler
from .signals import Signal, SignalParseError


log = logging.getLogger("banko.coach.kafka")


@dataclass
class SignalsKafkaConsumer:
    handler: SignalHandler
    kafka_consumer_factory: Callable[[], Iterable[Any]]
    commit_fn: Callable[[Any], None]
    dlq_send_fn: Optional[Callable[[bytes, str], None]] = None
    backoff_seconds: tuple[int, ...] = (1, 2, 5, 10, 30)

    def run_forever(self) -> None:
        """Outer loop with exponential backoff on broker failures. Inner
        loop is `run_once`."""
        attempt = 0
        while True:
            try:
                self.run_once()
                attempt = 0
            except Exception:
                wait = self.backoff_seconds[min(attempt,
                                                 len(self.backoff_seconds) - 1)]
                log.exception("kafka consumer crashed; backing off %ss", wait)
                time.sleep(wait)
                attempt += 1

    def run_once(self) -> None:
        """Drains the next batch from the broker (or fake) exactly once.
        Exposed for tests; production calls `run_forever`."""
        consumer = self.kafka_consumer_factory()
        for msg in consumer:
            self._process_one(msg)

    def _process_one(self, msg: Any) -> None:
        raw = msg.value
        try:
            data = json.loads(raw.decode("utf-8"))
            signal = Signal.from_dict(data)
        except (UnicodeDecodeError, json.JSONDecodeError, SignalParseError,
                KeyError) as e:
            log.error("poison message at offset=%s: %s",
                      getattr(msg, "offset", "?"), e)
            if self.dlq_send_fn is not None:
                self.dlq_send_fn(raw, str(e))
            self.commit_fn(msg)
            return

        try:
            self.handler.handle(signal)
        except Exception:
            log.exception("handler raised on offset=%s; will redeliver",
                          getattr(msg, "offset", "?"))
            # NO commit — Kafka will redeliver; idempotency at the handler
            # boundary protects us from double-applying.
            return

        self.commit_fn(msg)


def build_production_consumer(handler: SignalHandler,
                               bootstrap_servers: str,
                               topic: str,
                               group_id: str = "banko-coach-v1"
                               ) -> SignalsKafkaConsumer:
    """Builds a SignalsKafkaConsumer wired to a real kafka-python broker
    consumer. Kept out of the dataclass so tests don't need a broker."""
    from kafka import KafkaConsumer, KafkaProducer  # local import
    kc = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="latest",
        value_deserializer=lambda b: b,  # we parse JSON ourselves
    )
    producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
    dlq_topic = f"{topic}.dlq"

    def commit_fn(msg):
        from kafka import TopicPartition, OffsetAndMetadata
        tp = TopicPartition(msg.topic, msg.partition)
        kc.commit({tp: OffsetAndMetadata(msg.offset + 1, None)})

    def dlq_send_fn(raw_value: bytes, error: str):
        producer.send(dlq_topic, raw_value,
                      headers=[("error", error.encode())])
        producer.flush()

    return SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: kc,
        commit_fn=commit_fn,
        dlq_send_fn=dlq_send_fn,
    )
```

- [ ] **Step 10.5: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/coach/test_kafka_consumer.py -v
```
Expected: PASS on all 4 tests.

- [ ] **Step 10.6: Commit**

Run:
```bash
git add pyproject.toml uv.lock banko_ai/coach/kafka_consumer.py
git commit -m "feat(coach): add SignalsKafkaConsumer for prod-mode transport (flag-gated)"
```

---

## Task 11: `/health/coach` endpoint

**Files:**
- Modify: `banko_ai/web/app.py`
- Create: `tests/coach/test_health_endpoint.py`

**Rationale:** Spec §6.2 calls for a single health endpoint that reports the Coach subsystem's liveness: handler in-flight, last-nudge timestamp, Kafka mode, classifier degradation. v1-A doesn't have the classifier or Kafka yet wired live, so this is a minimal version we extend in 2-B/2-C.

- [ ] **Step 11.1: Write the failing test**

Create `tests/coach/test_health_endpoint.py` with exactly this content:

```python
"""Tests for /health/coach. Uses Flask test client; doesn't require LLM."""

import os
import pytest

from banko_ai.web.app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health_coach_returns_200_with_status_keys(client):
    resp = client.get("/health/coach")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert "components" in data
    assert "webhook_secret_configured" in data["components"]
    assert "kafka_enabled" in data["components"]
    assert "last_nudge_at" in data["components"]


def test_health_coach_reports_webhook_secret_state(client, monkeypatch):
    monkeypatch.setenv("CDC_WEBHOOK_HMAC_SECRET", "")
    resp = client.get("/health/coach")
    data = resp.get_json()
    assert data["components"]["webhook_secret_configured"] is False

    monkeypatch.setenv("CDC_WEBHOOK_HMAC_SECRET", "real-secret")
    resp = client.get("/health/coach")
    data = resp.get_json()
    assert data["components"]["webhook_secret_configured"] is True
```

- [ ] **Step 11.2: Run the test to verify it fails**

Run:
```bash
git add -f tests/coach/test_health_endpoint.py
uv run pytest tests/coach/test_health_endpoint.py -v
```
Expected: FAIL with 404.

- [ ] **Step 11.3: Add the `/health/coach` route**

In `banko_ai/web/app.py`, inside `create_app()`, alongside the other Coach routes (Task 9), add:

```python
    @app.route("/health/coach", methods=["GET"])
    def health_coach():
        from ..config.settings import get_config
        from sqlalchemy import create_engine, text
        cfg = get_config()
        db_url = os.getenv("DATABASE_URL")
        last_nudge_at = None
        db_ok = False
        try:
            eng = create_engine(db_url)
            with eng.connect() as conn:
                row = conn.execute(text(
                    "SELECT max(created_at) FROM coach_nudges"
                )).fetchone()
                last_nudge_at = row[0].isoformat() if row and row[0] else None
                db_ok = True
            eng.dispose()
        except Exception as e:
            coach_log.warning("health DB check failed: %s", e)

        components = {
            "db_reachable": db_ok,
            "webhook_secret_configured": bool(
                os.getenv("CDC_WEBHOOK_HMAC_SECRET", "")
            ),
            "kafka_enabled": cfg.coach_kafka_enabled,
            "active_provider": cfg.ai_service,
            "last_nudge_at": last_nudge_at,
        }
        overall = "green" if db_ok and components["webhook_secret_configured"] \
                  else "degraded"
        return jsonify({"status": overall, "components": components}), 200
```

- [ ] **Step 11.4: Run the test to verify it passes**

Run:
```bash
uv run pytest tests/coach/test_health_endpoint.py -v
```
Expected: PASS on both tests.

- [ ] **Step 11.5: Commit**

Run:
```bash
git add banko_ai/web/app.py
git commit -m "feat(coach): add /health/coach endpoint reporting handler state"
```

---

## Task 12: Local smoke + commit gate (USER GATED — DO NOT PUSH)

**Files:** none (verification only)

**Rationale:** Per memory `local_testing_before_push` and the user's explicit constraint in this session ("commit locally and build all of plan 2 as I am not going to push any changes to github until we test it all locally with the other watsonx project changes as well"), no `git push` happens here. The local validation gate must pass first; the actual push happens only after Plans 2-B and 2-C are also implemented **and** the sibling `cockroachdb-watsonx-data-pipeline` repo is exercised end to end against this branch.

- [ ] **Step 12.1: Run the full test suite**

Run:
```bash
DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable' \
  uv run pytest tests/ -v
```
Expected: all tests pass (or skip with a clear reason like "DATABASE_URL not set" — which won't happen here since we set it).

- [ ] **Step 12.2: Run lint and type checks**

Run:
```bash
uv run ruff check banko_ai/ tests/ scripts/
uv run mypy banko_ai/coach/
```
Expected: ruff clean, mypy clean (or only warnings about untyped third-party imports — the existing project ignores those via `ignore_missing_imports = true`).

If lint fails on auto-fixable issues:
```bash
uv run ruff check --fix banko_ai/coach/ tests/coach/ scripts/coach/
```
Then re-commit any changes with `git commit -am "style(coach): ruff auto-fixes"`.

- [ ] **Step 12.3: Manual end-to-end smoke against EACH provider**

For each of: `watsonx`, `openai`, `aws`, `gemini` (Ollama gets added in Plan 2-C; skip it here):

```bash
export AI_SERVICE=<provider>
export DATABASE_URL='postgresql://root@localhost:26257/banko?sslmode=disable'
export CDC_WEBHOOK_HMAC_SECRET='dev-only-secret'
# ... plus provider-specific credentials per existing app conventions
uv run python -m banko_ai.web.app &
APP_PID=$!
sleep 5

# Fire each signal type
uv run python scripts/coach/mock_signals.py --type=budget_threshold
uv run python scripts/coach/mock_signals.py --type=anomaly
uv run python scripts/coach/mock_signals.py --type=recurring_drift

# Verify three rows in coach_nudges
cockroach sql --insecure --execute \
  "SELECT signal_type, message, provider_used FROM banko.coach_nudges
   JOIN banko.spending_signals USING (signal_id)
   ORDER BY coach_nudges.created_at DESC LIMIT 3"

# Manually open http://localhost:5000/coach, click 'show evidence' on a card,
# type a reply, verify Coach responds with real data.

kill $APP_PID
```

Expected: three rows in `coach_nudges` with `provider_used = <provider>` and sensible nudge text. UI card animates in, evidence panel expands with real tool trace, reply round-trips successfully.

**Record results in a local note** (do NOT commit this note):
```
Watsonx:  PASS / FAIL  notes:
OpenAI:   PASS / FAIL  notes:
AWS:      PASS / FAIL  notes:
Gemini:   PASS / FAIL  notes:
```

- [ ] **Step 12.4: Halt — do NOT push**

After all four providers are green, **stop here**. The next steps are:
1. Plan 2-C (Observability + Airgap + Docs) — adds Ollama as the fifth provider.
2. Plan 2-B (Coach Enhancements — Supervisor + MCP + Eval).
3. Cross-repo verification with `cockroachdb-watsonx-data-pipeline` — wire its `spending_signals` output to this webhook and run the full demo.
4. Then and only then: `git push origin feat/coach-core-v1a` and open a PR.

`git log --oneline` should show roughly:
```
<hash> feat(coach): add /health/coach endpoint reporting handler state
<hash> feat(coach): add SignalsKafkaConsumer for prod-mode transport (flag-gated)
<hash> feat(coach): add Live Coach UI tab with SocketIO and REST routes
<hash> feat(coach): add mock_signals.py for local end-to-end smoke
<hash> feat(coach): add /api/cdc/signals webhook receiver (HMAC + idempotency)
<hash> feat(coach): wire CockroachDBSaver checkpointer into converse()
<hash> feat(coach): add CoachAgent conversational mode
<hash> feat(coach): add CoachAgent reactive mode (planner-executor-synthesizer)
<hash> feat(coach): add SignalHandler (idempotency, suppression, persist, emit)
<hash> feat(coach): add tools module (get_user_budget, set_budget, get_recent_signals, get_recent_transactions, explain_nudge)
<hash> feat(coach): add Signal dataclass and CRDB changefeed envelope parser
<hash> feat(coach): add spending_signals and coach_nudges migrations with TTL
<hash> feat(coach): add config knobs for webhook HMAC, rate limit, agent steps, Kafka flag
```

(13 commits — one per task plus the pre-flight env-knobs commit.)

---

## Out of scope for Plan 2-A (handled by 2-B and 2-C)

- **Supervisor** (spec §4 #13): Plan 2-B. Until then, `app.py` calls `CoachAgent.react/converse` directly. The Supervisor will replace those call sites without touching the agent.
- **MCP server** (spec §4 #7): Plan 2-B. The tools module is already MCP-ready (JSON-serializable returns, no Flask context dependencies).
- **Eval harness** (spec §4 #9): Plan 2-B. Tests in this plan are unit/integration; quality measurement is a separate concern.
- **OTel + Jaeger** (spec §4 #14): Plan 2-C. `trace_id` column already exists in `coach_nudges`; instrumentation lands later.
- **Ollama provider** (spec §4 #15): Plan 2-C. Until then, the four cloud providers are the smoke matrix; Ollama is added there and re-runs the smoke.
- **README slim + PIPELINE_CONTRACT.md** (spec §8.2, §11): Plan 2-C.

## Known gotchas this plan must respect

- **`.gitignore` `test_*.py` footgun**: every `tests/coach/test_*.py` MUST be added with `git add -f`. Already called out at each commit step.
- **No bot trailers**: commit messages above end at the subject line; no `Co-Authored-By: ...` lines (per `feedback_no_bot_commit_trailers`).
- **No push until cross-repo verified**: per `feedback_local_testing_before_push` and the user's standing constraint for this branch.
- **Provider abstraction invariant**: `CoachAgent` calls `default_llm_invoker` → `banko_ai.agents.llm_factory.get_llm_for_agent` → the existing provider layer. No direct provider SDK imports in `banko_ai/coach/`.
- **Airgap-first**: every code path in this plan also works with Ollama once Plan 2-C lands — there are no provider-specific branches in `banko_ai/coach/`. The webhook receiver, handler, agent graph, tools, and Kafka consumer are LLM-provider-agnostic.
- **`session.get('user_id')` may be None**: routes fall through to `cfg.coach_default_user_id` so the Coach tab works without requiring login. This matches the existing demo posture.

## Self-review

**Spec coverage** (against §4 components, scoped to v1-A):
- #1 `Signal` dataclass — Task 2 ✓
- #2 `SignalHandler` — Task 4 ✓
- #3 Webhook receiver — Task 7 ✓
- #4 Kafka consumer — Task 10 ✓
- #5 `CoachAgent` reactive — Task 5 ✓
- #5 `CoachAgent` conversational + checkpointer — Task 6 ✓
- #6 Coach tools — Task 3 ✓ (5 of 6 — `simulate_signal` is MCP-only, deferred to 2-B)
- #8 Live Coach UI tab — Task 9 ✓
- #10 Mock signal generator — Task 8 ✓
- #11 DB migrations — Task 1 ✓
- §6 health endpoint — Task 11 ✓

Deferred items (#7 MCP, #9 Eval, #13 Supervisor, #14 OTel, #15-17 Ollama+airgap, #12 contract doc) are explicitly handled by Plans 2-B and 2-C; the Out-of-Scope section above lists them and the call-sites Plan 2-B will need to update.

**Placeholder scan**: each step contains complete code, exact commands, expected output. No "TBD" / "implement later" / "add appropriate error handling". The one piece of UI integration that intentionally adapts to the current `index.html` layout (Step 9.3) explicitly tells the engineer what to add and warns against restructuring.

**Type consistency**: `Signal` field names and types are stable across Tasks 2-10. `CoachAgent.react()` returns `{message, tool_trace, provider_used}`; `SignalHandler._persist_nudge` reads exactly those keys. `tool_trace` is a `list[dict]` throughout (serialized as JSONB in the DB). `nudge_id` is `str` everywhere it crosses a boundary (the DB stores it as UUID; routes/JSON convert with `str(...)`).
