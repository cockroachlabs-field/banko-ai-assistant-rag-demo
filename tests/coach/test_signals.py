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
