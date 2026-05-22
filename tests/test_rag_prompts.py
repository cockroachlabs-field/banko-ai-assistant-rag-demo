"""Tests for the centralized Banko RAG prompt builder.

Why this file exists: the same prompt template used to be duplicated byte-for-byte
across watsonx/openai/aws/gemini providers, and the wording was weak enough that
different chat models produced wildly different output shapes for the same query
(see cache evidence from the 2026-05-22 smoke). The helper in
`banko_ai/ai_providers/rag_prompts.py` is the single source of truth — these
tests pin the structural promises that demos depend on so a future "clean up the
prompt" pass cannot quietly drop a section header.
"""
from __future__ import annotations

import pytest

from banko_ai.ai_providers.rag_prompts import build_banko_rag_prompt

SAMPLE_QUESTION = "What did I spend on coffee last month?"
SAMPLE_DATA = (
    "• **Food** at Starbucks: $4.95 on 2026-04-12 (Visa) - Latte\n"
    "• **Food** at Blue Bottle: $5.50 on 2026-04-18 (Visa) - Pour over"
)
SAMPLE_RECS = "• Consider brewing at home twice a week to cut ~$30/month."


def test_all_three_section_headers_present():
    """Every demo response is rendered with `marked.min.js`. If a header goes
    missing, the UI collapses to a wall of plain text — that was the regression
    that triggered this refactor."""
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, SAMPLE_RECS)
    assert "## 💡 Quick Answer" in out
    assert "## 📊 Breakdown" in out
    assert "## 🎯 Recommendations" in out


def test_question_and_data_are_interpolated():
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, SAMPLE_RECS)
    assert SAMPLE_QUESTION in out
    assert "Starbucks" in out
    assert "Blue Bottle" in out
    assert SAMPLE_RECS in out


def test_empty_recommendations_render_as_explicit_none():
    """An empty recommendations block used to produce a stray blank line that
    some models interpreted as 'no insights available, skip this section'. We
    now emit '(none)' so the model always sees a populated field."""
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, "")
    assert "Pre-computed insights:\n(none)" in out


def test_whitespace_only_recommendations_treated_as_empty():
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, "   \n  ")
    assert "Pre-computed insights:\n(none)" in out


@pytest.mark.parametrize("english_value", ["en", "en-US", "English", "", None])
def test_english_languages_emit_no_extra_clause(english_value):
    """Adding 'Respond entirely in English.' to an English prompt is noise that
    some smaller models echo back in the response."""
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, language=english_value)
    assert "Respond entirely in" not in out


@pytest.mark.parametrize(
    "code,expected_name",
    [
        ("es-ES", "Spanish"),
        ("fr-FR", "French"),
        ("de-DE", "German"),
        ("ja-JP", "Japanese"),
        ("hi-IN", "Hindi"),
    ],
)
def test_known_language_codes_emit_human_readable_names(code, expected_name):
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, language=code)
    assert f"Respond entirely in {expected_name}." in out


def test_unknown_language_code_falls_back_to_raw_value():
    """If the chat UI ever adds a language we haven't mapped, the prompt must
    still produce SOMETHING reasonable rather than silently drop the clause."""
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA, language="xx-YY")
    assert "Respond entirely in xx-YY." in out


def test_prompt_carries_invent_nothing_rule():
    """The receipt-OCR work proved that models will happily fabricate
    transactions if not explicitly forbidden. Pin the rule wording so a future
    edit can't soften it."""
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA)
    assert "never invent transactions" in out


def test_prompt_caps_response_length():
    """250 words is what the chat UI's bubble layout was tuned for. A 600-word
    wall makes the demo look unscripted."""
    out = build_banko_rag_prompt(SAMPLE_QUESTION, SAMPLE_DATA)
    assert "under 250 words" in out
