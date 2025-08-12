#!/usr/bin/env python3
"""
Standalone CockroachDB Vector Search Demo

This script demonstrates the vector search capabilities of CockroachDB
with the Banko AI expense data. It can be used independently to test
the database and vector search functionality.

Usage:
    python demo_standalone_search.py
"""

from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import numpy as np
import json
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database connection settings
DB_URI = "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

def get_query_embedding(query_text):
    """Generate embedding for a text query."""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode(query_text)
    return query_embedding

def numpy_vector_to_pg_vector(vector):
    """Convert numpy vector to PostgreSQL vector format."""
    return json.dumps(vector.flatten().tolist())

def search_expenses(query, limit=5):
    """Search expenses using vector similarity."""
    engine = create_engine(DB_URI)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Create embedding for the search query
    search_embedding = numpy_vector_to_pg_vector(model.encode(query))
    
    search_query = text("""
        SELECT 
            expense_id,
            description,
            expense_amount,
            merchant,
            shopping_type,
            payment_method,
            embedding <-> :search_embedding as similarity_score
        FROM expenses
        ORDER BY embedding <-> :search_embedding
        LIMIT :limit
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(search_query, {'search_embedding': search_embedding, 'limit': limit})
            return [dict(row._mapping) for row in result]
    except Exception as e:
        print(f"Error executing search: {e}")
        return []

def test_database_connection():
    """Test the database connection and show basic stats."""
    engine = create_engine(DB_URI)
    
    try:
        with engine.connect() as conn:
            # Test connection
            result = conn.execute(text('SELECT version()'))
            version = result.fetchone()[0]
            print(f"✅ Connected to: {version}")
            
            # Check if table exists
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'expenses'
            """))
            table_exists = result.fetchone()
            
            if table_exists:
                result = conn.execute(text('SELECT COUNT(*) FROM expenses'))
                count = result.fetchone()[0]
                print(f"✅ Expenses table exists with {count:,} records")
                return True
            else:
                print("❌ Expenses table does not exist")
                return False
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def interactive_search():
    """Interactive search mode."""
    print("\n🔍 Interactive Vector Search Mode")
    print("Type your queries (or 'quit' to exit):")
    
    while True:
        query = input("\n💬 Search query: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
            
        if not query:
            continue
            
        print(f"\n🔍 Searching for: '{query}'")
        results = search_expenses(query, limit=5)
        
        if results:
            print(f"\n📊 Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['description']}")
                print(f"   💰 Amount: ${result['expense_amount']:.2f}")
                print(f"   🏪 Merchant: {result['merchant']}")
                print(f"   📂 Category: {result['shopping_type']}")
                print(f"   💳 Payment: {result['payment_method']}")
                print(f"   📊 Similarity: {result['similarity_score']:.4f}")
        else:
            print("❌ No results found")

def demo_searches():
    """Run predefined demo searches."""
    demo_queries = [
        "restaurant meals and dining",
        "coffee and beverages",
        "gas and fuel expenses", 
        "online shopping purchases",
        "grocery store spending",
        "subscription services"
    ]
    
    print("\n🎯 Demo Vector Searches")
    print("=" * 50)
    
    for query in demo_queries:
        print(f"\n🔍 Query: '{query}'")
        results = search_expenses(query, limit=3)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"   {i}. {result['description']} - ${result['expense_amount']:.2f} (score: {result['similarity_score']:.3f})")
        else:
            print("   No results found")

def main():
    print("🏦 Banko AI - CockroachDB Vector Search Demo")
    print("=" * 50)
    
    # Test connection
    if not test_database_connection():
        print("\n❌ Cannot proceed without database connection")
        print("💡 Make sure CockroachDB is running and the expenses table exists")
        sys.exit(1)
    
    print("\nChoose an option:")
    print("1. Run demo searches")
    print("2. Interactive search mode")
    print("3. Both")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        demo_searches()
    elif choice == "2":
        interactive_search()
    elif choice == "3":
        demo_searches()
        interactive_search()
    else:
        print("Invalid choice. Running demo searches...")
        demo_searches()
    
    print("\n✅ Demo complete!")

if __name__ == "__main__":
    main()
