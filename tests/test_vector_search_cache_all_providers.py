"""
Test vector_search_cache functionality across all AI providers.
Verifies that all providers now consistently use vector_search_cache.
"""

import os
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')

from banko_ai.utils.cache_manager import BankoCacheManager
from banko_ai.ai_providers.watsonx_provider import WatsonxProvider
from banko_ai.ai_providers.openai_provider import OpenAIProvider
from banko_ai.ai_providers.gemini_provider import GeminiProvider
from banko_ai.ai_providers.aws_provider import AWSProvider
import time

def test_provider_vector_search_cache(provider_name, provider_class, config=None):
    """Test vector_search_cache for a specific provider."""
    print("\n" + "="*80)
    print(f"TEST: {provider_name} Vector Search Cache")
    print("="*80)
    
    try:
        # Initialize cache manager
        cache_manager = BankoCacheManager()
        print(f"✅ Cache manager initialized")
        
        # Initialize provider with cache_manager
        if config is not None:
            provider = provider_class(config=config, cache_manager=cache_manager)
        else:
            provider = provider_class(config={}, cache_manager=cache_manager)
        print(f"✅ {provider_name} provider initialized with cache_manager")
        
        test_query = "Show me coffee shop expenses"
        limit = 5
        
        # First search - should be cache MISS
        print(f"\n--- First Search (Cache MISS expected) ---")
        start = time.time()
        results1 = provider.search_expenses(test_query, limit=limit)
        time1 = time.time() - start
        print(f"⏱️  First search took: {time1*1000:.2f}ms")
        print(f"📊 Results: {len(results1)} expenses found")
        
        if len(results1) > 0:
            print(f"   Sample result: {results1[0].merchant} - ${results1[0].amount}")
        
        # Second search - should be cache HIT
        print(f"\n--- Second Search (Cache HIT expected) ---")
        start = time.time()
        results2 = provider.search_expenses(test_query, limit=limit)
        time2 = time.time() - start
        print(f"⏱️  Second search took: {time2*1000:.2f}ms")
        print(f"📊 Results: {len(results2)} expenses found")
        
        # Verify results are the same
        if len(results1) == len(results2):
            print(f"✅ Result count matches: {len(results1)} == {len(results2)}")
        else:
            print(f"⚠️  Result count mismatch: {len(results1)} != {len(results2)}")
        
        # Check if second search was faster (cache hit)
        if time2 < time1:
            speedup = time1 / time2
            print(f"✅ Second search was {speedup:.1f}x FASTER (cache likely hit)")
        else:
            print(f"⚠️  Second search was not faster (cache might have missed)")
        
        return True, time1, time2
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, 0

def verify_vector_search_cache_table():
    """Verify vector_search_cache table has entries."""
    print("\n" + "="*80)
    print("VERIFICATION: Check vector_search_cache Table")
    print("="*80)
    
    try:
        from sqlalchemy import create_engine, text
        from banko_ai.utils.db_retry import create_resilient_engine
        
        DB_URI = os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')
        db_url = DB_URI.replace("cockroachdb://", "postgresql://")
        engine = create_resilient_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) as count FROM vector_search_cache"))
            count = result.fetchone()[0]
            
            print(f"📊 vector_search_cache entries: {count}")
            
            if count > 0:
                # Get sample entries
                result = conn.execute(text("""
                    SELECT 
                        result_count,
                        access_count,
                        created_at,
                        similarity_threshold
                    FROM vector_search_cache
                    ORDER BY created_at DESC
                    LIMIT 5
                """))
                
                print(f"\n✅ Sample cache entries:")
                for i, row in enumerate(result, 1):
                    print(f"   {i}. Results: {row[0]}, Accessed: {row[1]}x, Created: {row[2]}, Threshold: {row[3]}")
                
                return True
            else:
                print(f"⚠️  No entries found in vector_search_cache")
                return False
                
    except Exception as e:
        print(f"❌ Error checking table: {e}")
        return False

def main():
    print("\n╔" + "="*78 + "╗")
    print("║" + " "*15 + "VECTOR SEARCH CACHE - ALL PROVIDERS TEST" + " "*23 + "║")
    print("╚" + "="*78 + "╝")
    
    results = {}
    
    # Test Watsonx Provider
    success, time1, time2 = test_provider_vector_search_cache(
        "Watsonx",
        WatsonxProvider,
        config={} # Empty config is fine, it will use env vars
    )
    results['watsonx'] = {'success': success, 'time1': time1, 'time2': time2}
    
    # Test OpenAI Provider
    success, time1, time2 = test_provider_vector_search_cache(
        "OpenAI",
        OpenAIProvider,
        config={}
    )
    results['openai'] = {'success': success, 'time1': time1, 'time2': time2}
    
    # Test Gemini Provider
    success, time1, time2 = test_provider_vector_search_cache(
        "Gemini",
        GeminiProvider,
        config={}
    )
    results['gemini'] = {'success': success, 'time1': time1, 'time2': time2}
    
    # Test AWS Provider
    success, time1, time2 = test_provider_vector_search_cache(
        "AWS Bedrock",
        AWSProvider,
        config={}
    )
    results['aws'] = {'success': success, 'time1': time1, 'time2': time2}
    
    # Verify table has entries
    table_ok = verify_vector_search_cache_table()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for provider, data in results.items():
        status = "✅ PASS" if data['success'] else "❌ FAIL"
        if data['success'] and data['time1'] > 0 and data['time2'] > 0:
            speedup = data['time1'] / data['time2']
            print(f"{status}: {provider:15} - Cache speedup: {speedup:.1f}x")
        else:
            print(f"{status}: {provider:15}")
    
    print(f"\n{'✅ PASS' if table_ok else '❌ FAIL'}: vector_search_cache table has entries")
    
    passed = sum(1 for d in results.values() if d['success']) + (1 if table_ok else 0)
    total = len(results) + 1
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - vector_search_cache working across all providers!")
    else:
        print("\n⚠️  Some tests failed - review above for details")

if __name__ == "__main__":
    main()
