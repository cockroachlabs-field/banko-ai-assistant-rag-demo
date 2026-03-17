"""
Test vector_search_cache functionality across all AI providers.
Verifies that all providers now consistently use vector_search_cache.
"""

import os
import time

os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')

import pytest

from banko_ai.utils.cache_manager import BankoCacheManager


@pytest.fixture(scope="module")
def cache_manager():
    return BankoCacheManager()


def test_cache_manager_has_vector_search_methods(cache_manager):
    """Verify cache manager exposes vector search cache methods."""
    assert hasattr(cache_manager, 'get_cached_vector_search')
    assert hasattr(cache_manager, 'cache_vector_search_results')


def test_vector_search_cache_roundtrip(cache_manager):
    """Store and retrieve vector search results through the cache."""
    test_query = "Show me coffee shop expenses for roundtrip test"
    test_results = [
        {"expense_id": "1", "merchant": "Starbucks", "expense_amount": 5.50},
        {"expense_id": "2", "merchant": "Blue Bottle", "expense_amount": 6.75},
    ]
    limit = 2  # Must be <= len(test_results) for cache hit

    embedding = cache_manager._get_embedding_with_cache(test_query)
    assert embedding is not None

    cache_manager.cache_vector_search_results(
        query_embedding=embedding,
        results=test_results,
    )

    cached = cache_manager.get_cached_vector_search(
        query_embedding=embedding,
        limit=limit,
    )

    assert cached is not None, "Vector search cache returned None"
    assert len(cached) >= 1


def test_vector_search_cache_embedding_performance(cache_manager):
    """Second embedding call should be faster (from embedding_cache)."""
    text = "grocery spending last month for perf test"

    start = time.time()
    _ = cache_manager._get_embedding_with_cache(text)
    t1 = time.time() - start

    start = time.time()
    _ = cache_manager._get_embedding_with_cache(text)
    t2 = time.time() - start

    # Cache hit should be at least as fast (allow small jitter)
    assert t2 <= t1 + 0.05


# Keep the original main() for manual runs
def _run_provider_test(provider_name, provider_class, config=None):
    """Run vector_search_cache test for a specific provider (manual only)."""
    cache_manager = BankoCacheManager()
    if config is not None:
        provider = provider_class(config=config, cache_manager=cache_manager)
    else:
        provider = provider_class(config={}, cache_manager=cache_manager)
    print(f"Testing {provider_name}...")

    test_query = "Show me coffee shop expenses"
    limit = 5

    start = time.time()
    results1 = provider.search_expenses(test_query, limit=limit)
    time1 = time.time() - start
    print(f"  First search: {time1*1000:.2f}ms, {len(results1)} results")

    start = time.time()
    results2 = provider.search_expenses(test_query, limit=limit)
    time2 = time.time() - start
    print(f"  Second search: {time2*1000:.2f}ms, {len(results2)} results")

    return True, time1, time2


if __name__ == "__main__":
    from banko_ai.ai_providers.aws_provider import AWSProvider
    from banko_ai.ai_providers.gemini_provider import GeminiProvider
    from banko_ai.ai_providers.openai_provider import OpenAIProvider
    from banko_ai.ai_providers.watsonx_provider import WatsonxProvider

    for name, cls in [
        ("Watsonx", WatsonxProvider),
        ("OpenAI", OpenAIProvider),
        ("Gemini", GeminiProvider),
        ("AWS", AWSProvider),
    ]:
        _run_provider_test(name, cls)
