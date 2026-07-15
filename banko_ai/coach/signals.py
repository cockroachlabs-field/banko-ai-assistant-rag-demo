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
    def from_dict(cls, d: dict[str, Any]) -> Signal:
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
