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
    search_embedding = numpy_vector_to_pg_vector(model.encode(query))
    
    search_query = text("""
        SELECT 
            expense_id,
            description,
            expense_amount,
            merchant,
            shopping_type,
            payment_method,
            embedding <=> :search_embedding as similarity_score
        FROM expenses
        ORDER BY embedding <=> :search_embedding
        LIMIT :limit
    """)
    
    with engine.connect() as conn:
        result = conn.execute(search_query, {'search_embedding': search_embedding, 'limit': limit})
        return [dict(row._mapping) for row in result]

def main():
    query = "shopping credit card"
    results = search_expenses(query)
    print(f"\nSearch results for: '{query}'\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Description: {result['description']}")
        print(f"   Amount: ${result['expense_amount']:.2f}")
        print(f"   Merchant: {result['merchant']}")
        print(f"   Type: {result['shopping_type']}")
        print(f"   Payment: {result['payment_method']}")
        print(f"   Similarity Score: {result['similarity_score']:.4f}")
        print()

if __name__ == "__main__":
    main()
