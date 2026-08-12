"""
Test that response cache (query_cache) now works correctly with normalized expense data.
This should fix the issue where identical queries were getting cache MISS.
"""

import os

os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')

import time

from banko_ai.ai_providers.openai_provider import OpenAIProvider
from banko_ai.utils.cache_manager import BankoCacheManager


def test_response_cache_with_identical_queries():
    """
    Test that the same query twice hits the response cache on 2nd try.
    This was broken before because similarity_score differences changed the hash.
    """
    print("\n" + "="*80)
    print("TEST: Response Cache with Identical Queries")
    print("="*80)
    
    try:
        # Initialize
        cache_manager = BankoCacheManager()
        provider = OpenAIProvider(config={}, cache_manager=cache_manager)
        
        test_query = "coffee"
        print(f"\nTest Query: '{test_query}'")
        print("Provider: OpenAI")
        
        # First query - should be MISS on both caches
        print(f"\n{'='*80}")
        print("FIRST QUERY (both caches should MISS)")
        print("="*80)
        
        results1 = provider.search_expenses(test_query, limit=10)
        
        print(f"\n📊 Vector search results: {len(results1)} expenses")
        if results1:
            print(f"   Sample: {results1[0].merchant} - ${results1[0].amount}")
        
        # Now call the full RAG response (which checks response cache)
        # This is a simplified simulation - in real usage this would happen in the flow
        print("\n⏭️  Now generating RAG response (checks response cache)...")
        
        # Convert SearchResult to dict format for cache
        search_results_dict = []
        for r in results1:
            search_results_dict.append({
                'expense_id': r.expense_id,
                'user_id': r.user_id,
                'description': r.description,
                'merchant': r.merchant,
                'expense_amount': r.amount,
                'expense_date': r.date,
                'similarity_score': r.similarity_score  # This will be excluded from hash!
            })
        
        # Check response cache
        cached_response = cache_manager.get_cached_response(test_query, search_results_dict, "openai")
        if cached_response:
            print("   ❌ UNEXPECTED: Response cache HIT on first query!")
        else:
            print("   ✅ Response cache MISS (expected)")
        
        # Store a mock response in cache
        mock_response = "Coffee expenses: $45.20 at Starbucks, $12.50 at Peet's"
        cache_manager.cache_response(test_query, mock_response, search_results_dict, "openai", 
                                     prompt_tokens=100, response_tokens=50)
        print("   ✅ Stored response in cache")
        
        # Second query - same query string
        print(f"\n{'='*80}")
        print("SECOND QUERY (response cache should HIT!)")
        print("="*80)
        
        results2 = provider.search_expenses(test_query, limit=10)
        
        print(f"\n📊 Vector search results: {len(results2)} expenses")
        
        # Convert results to dict (may have different similarity_scores from cache!)
        search_results_dict2 = []
        for r in results2:
            search_results_dict2.append({
                'expense_id': r.expense_id,
                'user_id': r.user_id,
                'description': r.description,
                'merchant': r.merchant,
                'expense_amount': r.amount,
                'expense_date': r.date,
                'similarity_score': r.similarity_score  # Might be slightly different!
            })
        
        # Check response cache - THIS SHOULD HIT NOW!
        cached_response2 = cache_manager.get_cached_response(test_query, search_results_dict2, "openai")
        
        if cached_response2:
            print("\n   ✅ ✅ ✅ RESPONSE CACHE HIT! ✅ ✅ ✅")
            print(f"   Response: {cached_response2[:60]}...")
            print("\n   🎉 FIX SUCCESSFUL: Response cache working with normalized expense data!")
            return True
        else:
            print("\n   ❌ Response cache MISS (should have been HIT)")
            print("\n   ⚠️  FIX MAY NOT BE WORKING - expense hash still different?")
            
            # Debug: Check if hashes match
            hash1 = cache_manager._generate_hash(
                cache_manager._normalize_expense_data_for_cache(search_results_dict)
            )
            hash2 = cache_manager._generate_hash(
                cache_manager._normalize_expense_data_for_cache(search_results_dict2)
            )
            
            print("\n   Debug Info:")
            print(f"   - Hash 1: {hash1[:20]}...")
            print(f"   - Hash 2: {hash2[:20]}...")
            print(f"   - Match: {hash1 == hash2}")
            
            if hash1 != hash2:
                print("\n   Issue: Hashes still don't match even after normalization")
                print("   This shouldn't happen with the fix!")
            
            return False
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n╔" + "="*78 + "╗")
    print("║" + " "*20 + "RESPONSE CACHE FIX VERIFICATION" + " "*26 + "║")
    print("╚" + "="*78 + "╝")
    
    success = test_response_cache_with_identical_queries()
    
    print("\n" + "="*80)
    print("RESULT")
    print("="*80)
    
    if success:
        print("\n✅ ✅ ✅ TEST PASSED ✅ ✅ ✅")
        print("\nResponse cache now works correctly!")
        print("Identical queries will hit the cache on 2nd try.")
        print("The fix successfully normalizes expense data before hashing.")
    else:
        print("\n❌ TEST FAILED")
        print("\nResponse cache still not working as expected.")
        print("Review debug output above for details.")

if __name__ == "__main__":
    main()
