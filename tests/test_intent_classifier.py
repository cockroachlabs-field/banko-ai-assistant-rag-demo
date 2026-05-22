"""Tests for the intent classification guardrail."""

from banko_ai.utils.intent_classifier import (
    REDIRECT_MESSAGE,
    _lexical_or_fuzzy_financial_hit,
    is_financial_query,
)

FINANCIAL_QUERIES = [
    "coffee",
    "how much did I spend on coffee",
    "show me my grocery expenses",
    "what is my monthly budget",
    "any duplicate transactions",
    "restaurant spending last week",
    "upload a receipt",
    "credit card charges this month",
    "am I over budget",
    "show me recurring payments",
    "how much do I owe",
    "starbucks",
    "uber rides",
    "amazon purchases",
]

NON_FINANCIAL_QUERIES = [
    "what is the weather today",
    "who is the president",
    "write me a poem",
    "how to cook pasta",
    "tell me a joke",
    "what time is it",
    "capital of France",
    "explain quantum physics",
]


def test_financial_queries_pass():
    for query in FINANCIAL_QUERIES:
        assert is_financial_query(query), f"Expected financial: {query}"


def test_non_financial_queries_blocked():
    for query in NON_FINANCIAL_QUERIES:
        assert not is_financial_query(query), f"Expected non-financial: {query}"


def test_redirect_message_mentions_banko():
    assert "Banko" in REDIRECT_MESSAGE
    assert "finance" in REDIRECT_MESSAGE.lower()


# Typo regression: before the embedding gate was added on 2026-03-17, every
# query went straight to RAG and the LLM tolerated misspellings. The gate
# rejected "delta exepnses" (MiniLM scored it 0.107 financial vs 0.193
# non-financial). The lexical+fuzzy pre-pass restores typo tolerance for
# queries that name known financial concepts.
TYPO_QUERIES = [
    "delta exepnses",        # 'expenses' typo
    "delta exepnse",         # 'expense' typo
    "starbcks spending",     # 'starbucks' typo
    "how much did i spnd",   # 'spend' typo
    "amazn purchases",       # 'amazon' typo
    "groceriess this month", # 'groceries' typo
    "starbcks last week",    # 'starbucks' typo
]


def test_typo_queries_pass_via_lexical_or_fuzzy():
    for query in TYPO_QUERIES:
        assert is_financial_query(query), f"Expected financial (typo): {query}"


def test_currency_symbol_short_circuits():
    """A '$' in the query is a strong financial signal; should pass without
    needing the embedding model."""
    assert _lexical_or_fuzzy_financial_hit("$42 at the coffee shop")
    assert _lexical_or_fuzzy_financial_hit("how much is $5")


def test_lexical_hit_on_exact_keyword():
    """Exact substring match against FINANCIAL_KEYWORDS short-circuits to
    True without ever loading the embedding model."""
    assert _lexical_or_fuzzy_financial_hit("uber")
    assert _lexical_or_fuzzy_financial_hit("show my budget")
    assert _lexical_or_fuzzy_financial_hit("any refunds")


def test_fuzzy_hit_on_close_misspelling():
    """The fuzzy pass catches single-character typos in core financial
    vocabulary (cutoff=0.80, minimum token length 4)."""
    assert _lexical_or_fuzzy_financial_hit("show my exepnses")  # expenses
    assert _lexical_or_fuzzy_financial_hit("trasaction history")  # transaction


def test_fuzzy_pass_does_not_fire_on_unrelated_long_words():
    """Cutoff 0.80 + min length 4 must reject genuinely unrelated long words.
    Without this, the gate would let everything through and the embedding
    fallback would never run."""
    assert not _lexical_or_fuzzy_financial_hit("philosophy lecture")
    assert not _lexical_or_fuzzy_financial_hit("quantum entanglement")
