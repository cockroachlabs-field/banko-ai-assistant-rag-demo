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


def test_integrity_error_goes_to_dlq_not_redelivery():
    # A signal whose parent row vanished (test cleanup, TTL) raises a
    # constraint violation on nudge insert. That is permanent: it must
    # land in the DLQ and commit, never loop through redelivery.
    from sqlalchemy.exc import IntegrityError
    handler = MagicMock()
    handler.handle.side_effect = IntegrityError("stmt", {}, Exception("fk"))
    commit = MagicMock()
    dlq = MagicMock()
    fake_consumer = iter([_fake_msg(_valid_signal_payload("k-fk"), offset=5)])
    consumer = SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: fake_consumer,
        commit_fn=commit,
        dlq_send_fn=dlq,
    )
    consumer.run_once()
    assert handler.handle.call_count == 1
    assert dlq.call_count == 1
    assert commit.call_count == 1


def test_transient_handler_error_still_redelivers():
    handler = MagicMock()
    handler.handle.side_effect = RuntimeError("provider timeout")
    commit = MagicMock()
    fake_consumer = iter([_fake_msg(_valid_signal_payload("k-transient"))])
    consumer = SignalsKafkaConsumer(
        handler=handler,
        kafka_consumer_factory=lambda: fake_consumer,
        commit_fn=commit,
    )
    consumer.run_once()
    assert commit.call_count == 0  # not committed, Kafka redelivers
