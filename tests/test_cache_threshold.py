#!/usr/bin/env python3
"""
Test script to demonstrate configurable cache thresholds.
Shows how different threshold settings affect cache hit rates.
"""

import os
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")

# Apply CockroachDB version patch
from sqlalchemy.dialects.postgresql.base import PGDialect
original_get_server_version_info = PGDialect._get_server_version_info
def patched_get_server_version_info(self, connection):
    try:
        return original_get_server_version_info(self, connection)
    except Exception:
        return (25, 3, 0)
PGDialect._get_server_version_info = patched_get_server_version_info

from banko_ai.utils.cache_manager import BankoCacheManager

# Test queries with known similarity scores
test_pairs = [
    ("coffee", "what did i spend on coffee", 0.69),
    ("coffee expenses", "my coffee spending", 0.88),
    ("travel costs", "how much did I spend on travel", 0.82),
]

print("=" * 70)
print("CACHE THRESHOLD COMPARISON")
print("=" * 70)

# Test different thresholds
thresholds = [0.70, 0.75, 0.85]

for threshold in thresholds:
    print(f"\n{'='*70}")
    print(f"Testing with threshold: {threshold}")
    print(f"{'='*70}\n")
    
    # Create cache manager with this threshold
    cache_mgr = BankoCacheManager(
        similarity_threshold=threshold,
        cache_ttl_hours=24,
        strict_mode=True
    )
    
    for query1, query2, sim_score in test_pairs:
        would_match = sim_score >= threshold
        icon = "✅" if would_match else "❌"
        
        print(f"{icon} Query pair: '{query1}' ↔ '{query2}'")
        print(f"   Similarity: {sim_score:.2f} | Would cache? {would_match}")
    
    print()

print("\n" + "=" * 70)
print("STRICT MODE vs LENIENT MODE")
print("=" * 70)

print("\n📊 STRICT MODE (default - requires exact data match):")
print("   - Higher accuracy: Returns cached response only if search results match")
print("   - Lower cache hit rate: Different search results = cache MISS")
print("   - Best for: Financial advisory, critical applications")

print("\n🚀 LENIENT MODE (CACHE_STRICT_MODE=false):")
print("   - Higher cache hit rate: Matches on query similarity alone")
print("   - Lower accuracy: May return response with different expense data")
print("   - Best for: Demos, high-traffic scenarios, less critical queries")

print("\n" + "=" * 70)
print("RECOMMENDATIONS FOR RE:INVENT DEMO")
print("=" * 70)
print("""
For best demo experience, use:

export CACHE_SIMILARITY_THRESHOLD="0.75"
export CACHE_STRICT_MODE="true"
export CACHE_TTL_HOURS="24"

This provides:
✅ Good balance between cache hits and accuracy
✅ Similar queries like "coffee" and "coffee expenses" will match
✅ Data consistency ensured (strict mode)
✅ Clear demo of caching benefits

To show aggressive caching (more cache hits):
export CACHE_SIMILARITY_THRESHOLD="0.70"
export CACHE_STRICT_MODE="false"

To show conservative caching (fewer cache hits, highest accuracy):
export CACHE_SIMILARITY_THRESHOLD="0.85"
export CACHE_STRICT_MODE="true"
""")

print("=" * 70)
print("\n💡 TIP: Monitor cache hit rate in your logs:")
print("   - Look for '🎯 Cache HIT!' messages")
print("   - Check confidence levels: HIGH (≥0.90), MEDIUM (0.70-0.89), LOW (<0.70)")
print("   - Adjust threshold based on your cache hit rate vs accuracy needs")
print()
