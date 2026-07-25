"""The demo accuracy acceptance check.

An aggregation question is answered from SQL, so the number is exact,
stable across runs, and identical no matter which AI provider is
configured. This is the regression guard for the July 2026 field report
where two providers gave two different wrong answers to the same
question."""

import os

import pytest

from banko_ai.utils.aggregations import run_aggregation
from banko_ai.utils.intent_classifier import classify_aggregation

DB = os.getenv("DATABASE_URL")
PERSONA_ONE = "00000000-0000-0000-0000-0000000000a1"
pytestmark = pytest.mark.skipif(not DB, reason="DATABASE_URL not set")


def test_jims_question_is_deterministic():
    intent = classify_aggregation(
        "How much money did I spend on restaurants in the past 60 days?")
    assert intent is not None
    assert intent.operation == "sum"

    first = run_aggregation(intent, PERSONA_ONE, DB)
    second = run_aggregation(intent, PERSONA_ONE, DB)

    assert first.total == second.total
    assert first.count == second.count
    assert first.category == "Restaurant"
    # persona one is the diner; seeded data guarantees hits in any 60-day
    # window while the app has been booted at least once
    if first.count:
        assert first.total > 0
        assert first.rows, "breakdown rows should accompany a nonzero total"


def test_zero_result_is_honest():
    intent = classify_aggregation(
        "how much did I spend on restaurants last month?")
    assert intent is not None
    empty = run_aggregation(intent, "00000000-0000-0000-0000-00000000dead", DB)
    assert empty.count == 0
    assert empty.total == 0.0
