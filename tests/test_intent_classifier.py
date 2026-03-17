"""Tests for the intent classification guardrail."""

from banko_ai.utils.intent_classifier import is_financial_query, REDIRECT_MESSAGE

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
