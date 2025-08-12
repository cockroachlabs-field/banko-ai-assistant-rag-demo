#!/usr/bin/env python3
"""
Banko AI Token Optimization Demo

This script demonstrates the token optimization capabilities by:
1. Running similar queries to show cache hits
2. Measuring token savings
3. Demonstrating different cache layers (embedding, vector search, response)
4. Showing cache performance statistics

Run this after starting the Banko AI services to see caching in action.
"""

import requests
import time
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
DEMO_QUERIES = [
    # Similar queries that should show cache hits
    "Show me my grocery spending",
    "How much did I spend on groceries?",
    "What are my food expenses?",
    "Tell me about my grocery purchases",
    
    # Different category queries
    "How much did I spend on gas?",
    "Show me my fuel expenses",
    "What are my transportation costs?",
    
    # Budget-related queries
    "How can I save money on food?",
    "Give me budget tips for groceries",
    "What's my spending pattern for dining out?",
    
    # Repeated queries (should be immediate cache hits)
    "Show me my grocery spending",  # Exact repeat
    "How much did I spend on groceries?",  # Exact repeat
]

def make_query(query):
    """Make a query to the Banko AI assistant."""
    try:
        response = requests.post(
            f"{BASE_URL}/banko",
            data={'user_input': query},
            timeout=30
        )
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

def get_cache_stats():
    """Get current cache statistics."""
    try:
        response = requests.get(f"{BASE_URL}/cache-stats")
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*80}")
    print(f" {text}")
    print(f"{'='*80}")

def print_subheader(text):
    """Print a formatted subheader."""
    print(f"\n{'-'*60}")
    print(f" {text}")
    print(f"{'-'*60}")

def main():
    """Run the token optimization demo."""
    print_header("🎯 BANKO AI TOKEN OPTIMIZATION DEMO")
    print("This demo shows how intelligent caching reduces token usage and costs.")
    print("\n📊 What we'll demonstrate:")
    print("  1. Embedding cache - Reusing embeddings for similar text")
    print("  2. Vector search cache - Caching database query results")  
    print("  3. Response cache - Reusing AI responses for similar questions")
    print("  4. Token savings measurement and cost analysis")
    
    # Get initial cache stats
    print_subheader("📈 Initial Cache Statistics")
    initial_stats = get_cache_stats()
    if "error" not in initial_stats:
        initial_tokens_saved = initial_stats.get('overall_metrics', {}).get('total_tokens_saved', 0)
        print(f"💰 Tokens saved so far: {initial_tokens_saved:,}")
        print(f"💵 Estimated cost savings: ${initial_stats.get('overall_metrics', {}).get('estimated_cost_savings_usd', 0):.4f}")
    else:
        print(f"⚠️ Could not get cache stats: {initial_stats.get('error')}")
        initial_tokens_saved = 0
    
    # Run demo queries
    print_subheader("🔄 Running Demo Queries with Cache Analysis")
    total_queries = len(DEMO_QUERIES)
    
    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"\n[Query {i}/{total_queries}] {query}")
        
        start_time = time.time()
        success, response = make_query(query)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        if success:
            print(f"  ✅ Response received in {response_time:.2f}s")
            
            # Get updated cache stats
            current_stats = get_cache_stats()
            if "error" not in current_stats:
                current_tokens_saved = current_stats.get('overall_metrics', {}).get('total_tokens_saved', 0)
                tokens_saved_this_query = current_tokens_saved - initial_tokens_saved
                
                hit_rate = current_stats.get('overall_metrics', {}).get('overall_hit_rate', 0)
                print(f"  📊 Cache hit rate: {hit_rate:.1f}%")
                
                if i > 1:  # Skip first query since it can't be a cache hit
                    if tokens_saved_this_query > 0:
                        print(f"  🎯 Cache HIT! Tokens saved: {tokens_saved_this_query}")
                    else:
                        print(f"  ❌ Cache MISS - generating fresh response")
        else:
            print(f"  ❌ Query failed: {response}")
        
        # Small delay between queries
        if i < total_queries:
            time.sleep(1)
    
    # Final statistics
    print_subheader("📊 Final Cache Performance Report")
    final_stats = get_cache_stats()
    
    if "error" not in final_stats:
        overall = final_stats.get('overall_metrics', {})
        details = final_stats.get('cache_details', {})
        
        print(f"📈 OVERALL PERFORMANCE:")
        print(f"  Total Requests: {overall.get('total_requests', 0):,}")
        print(f"  Cache Hits: {overall.get('total_hits', 0):,}")
        print(f"  Hit Rate: {overall.get('overall_hit_rate', 0):.1f}%")
        print(f"  Tokens Saved: {overall.get('total_tokens_saved', 0):,}")
        print(f"  Estimated Cost Savings: ${overall.get('estimated_cost_savings_usd', 0):.4f}")
        
        print(f"\n🔍 CACHE BREAKDOWN:")
        for cache_type, stats in details.items():
            if cache_type != 'total_tokens_saved':
                hits = stats.get('hits', 0)
                misses = stats.get('misses', 0)
                writes = stats.get('writes', 0)
                tokens_saved = stats.get('tokens_saved', 0)
                hit_rate = stats.get('hit_rate', 0) * 100
                
                print(f"  {cache_type.upper()} Cache:")
                print(f"    Hits: {hits} | Misses: {misses} | Writes: {writes}")
                print(f"    Hit Rate: {hit_rate:.1f}% | Tokens Saved: {tokens_saved:,}")
        
        # Calculate potential savings
        total_queries_made = overall.get('total_requests', 0)
        if total_queries_made > 0:
            avg_tokens_per_uncached_query = 900  # Estimated average
            total_tokens_without_cache = total_queries_made * avg_tokens_per_uncached_query
            total_tokens_with_cache = total_tokens_without_cache - overall.get('total_tokens_saved', 0)
            efficiency_improvement = (overall.get('total_tokens_saved', 0) / total_tokens_without_cache) * 100
            
            print(f"\n💡 OPTIMIZATION IMPACT:")
            print(f"  Tokens without cache: {total_tokens_without_cache:,}")
            print(f"  Tokens with cache: {total_tokens_with_cache:,}")
            print(f"  Efficiency improvement: {efficiency_improvement:.1f}%")
    else:
        print(f"⚠️ Could not get final stats: {final_stats.get('error')}")
    
    print_subheader("🎉 Demo Complete!")
    print("Key takeaways:")
    print("  ✅ Embedding cache reduces computation time for similar queries")
    print("  ✅ Vector search cache eliminates redundant database queries")
    print("  ✅ Response cache provides instant answers for similar questions")
    print("  ✅ Multi-layer caching can reduce token usage by 50-80%")
    print("  ✅ Cost savings scale with usage volume")
    
    print(f"\n📊 Monitor ongoing performance:")
    print(f"  Cache Stats: {BASE_URL}/cache-stats")
    print(f"  AI Status: {BASE_URL}/ai-status")
    print(f"  Cache Cleanup: curl -X POST {BASE_URL}/cache-cleanup")

if __name__ == "__main__":
    main()
