from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import numpy as np
import json

# Database connection settings
DB_URI = "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"
engine = create_engine(DB_URI)

def get_query_embedding(query_text):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode(query_text)
    return query_embedding

def numpy_vector_to_pg_vector(vector):
    return json.dumps(vector.flatten().tolist())

def search_expenses(query, limit=5):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Create embedding for the search query
    raw_embedding = model.encode(query)
    search_embedding = numpy_vector_to_pg_vector(raw_embedding)
    
    # Debug prints
    print(f"\nDEBUG INFO:")
    print(f"1. Search Query: '{query}'")
    
    # Let's try some similar test queries to understand the semantic space
    test_queries = [
        query,  # original query
        f"Spent money on {query}",
        f"Purchase at {query}",
        f"Payment for {query}",
    ]
    
    print("\n2. Testing similar queries:")
    embeddings = model.encode(test_queries)
    for q, emb in zip(test_queries, embeddings):
        similarity = np.dot(emb, raw_embedding) / (
            np.linalg.norm(emb) * np.linalg.norm(raw_embedding)
        )
        print(f"   - '{q}': similarity = {similarity:.4f}")
    
    # Original search query
    search_query = text("""
        SELECT 
            description,
            merchant,
            shopping_type,
            expense_amount,
            embedding <=> :search_embedding as similarity_score
        FROM expenses
        ORDER BY embedding <=> :search_embedding
        LIMIT :limit
    """)
    
    with engine.connect() as conn:
        results = conn.execute(search_query, 
                             {'search_embedding': search_embedding, 'limit': limit})
        print("\n3. Top search results:")
        for row in results:
            print(f"\n   Score: {row.similarity_score:.4f}")
            print(f"   Description: {row.description}")
            print(f"   Merchant: {row.merchant}")
            print(f"   Type: {row.shopping_type}")
            print(f"   Amount: ${row.expense_amount}")
    
    return [dict(row._mapping) for row in results]

def main():
    query = "How is my gorcery spending?"
    results = search_expenses(query)
    print(f"\nSearch results for: '{query}'\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Description: {result['description']}")
        print(f"   Amount: ${result['expense_amount']:.2f}")
        print(f"   Merchant: {result['merchant']}")
        print(f"   Type: {result['shopping_type']}")
        print(f"   Similarity Score: {result['similarity_score']:.4f}")
        print()

if __name__ == "__main__":
    main()
