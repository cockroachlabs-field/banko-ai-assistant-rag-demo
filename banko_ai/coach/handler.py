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
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

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
    suppressed_types: Iterable[SignalType] = field(default_factory=tuple)
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

        # A Kafka event can outlive its source row (test cleanup, TTL,
        # clear-demo-users). Check before invoking the LLM: the nudge
        # insert would fail its foreign key anyway, and the model call
        # is the expensive part.
        if not self._signal_row_exists(signal):
            log.info("signal row no longer exists, skipping stale event",
                     extra={"signal_id": signal.signal_id})
            return {"status": "stale", "signal_id": signal.signal_id}

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

    def _signal_row_exists(self, signal: Signal) -> bool:
        eng = self._engine()
        with eng.connect() as conn:
            row = conn.execute(text(
                "SELECT 1 FROM spending_signals WHERE signal_id = :s"
            ), {"s": signal.signal_id}).fetchone()
        eng.dispose()
        return row is not None

    def _mark_consumed(self, signal: Signal) -> None:
        eng = self._engine()
        with eng.begin() as conn:
            conn.execute(text(
                "UPDATE spending_signals SET consumed_at = now() "
                "WHERE signal_id = :s"
            ), {"s": signal.signal_id})
        eng.dispose()

    def _persist_nudge(self, signal: Signal, nudge: dict[str, Any]) -> str:
        eng = self._engine()
        with eng.begin() as conn:
            from ..utils.migration import regional_tables_ready
            from ..web.auth import resolve_user_region

            cols = ["signal_id", "user_id", "message", "tool_trace",
                    "provider_used", "trace_id"]
            placeholders = [":sig", ":u", ":msg", "CAST(:trace AS JSONB)",
                           ":prov", ":trace_id"]
            params = {
                "sig": signal.signal_id,
                "u": signal.user_id,
                "msg": nudge["message"],
                "trace": json.dumps(nudge.get("tool_trace") or []),
                "prov": nudge.get("provider_used"),
                "trace_id": nudge.get("trace_id"),
            }

            if regional_tables_ready(self.database_url):
                user_region = resolve_user_region(signal.user_id, self.database_url)
                if user_region:
                    cols.append("crdb_region")
                    placeholders.append(":region")
                    params["region"] = user_region

            sql = f"""
                INSERT INTO coach_nudges ({", ".join(cols)})
                VALUES ({", ".join(placeholders)})
                RETURNING nudge_id
            """
            row = conn.execute(text(sql), params).fetchone()
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
        else:
            sub = signal.payload.get("subscription", "a subscription")
            msg = (f"A recurring charge changed: {sub}. Review the new amount. "
                   "(Coach AI is offline.)")
        return {"message": msg, "tool_trace": [{"fallback": True,
                                                 "error": error}]}
