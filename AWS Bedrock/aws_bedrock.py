from config import API_KEY
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import numpy as np
import boto3
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
    print(f"2. Search Embedding: {search_embedding}")
    print(f"3. Limit: {limit}")
    
    # Corrected search query
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
            results = conn.execute(search_query, 
                                 {'search_embedding': search_embedding, 'limit': limit})
            return [dict(row._mapping) for row in results]
    except Exception as e:
        print(f"Error executing query: {e}")
        return []

def RAG_response(prompt, search_results=None, use_bedrock=True):
    print(prompt)
    if use_bedrock:
        # Initialize Bedrock client
        bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

        # Prepare the search results text
        search_results_text = ""
        if search_results:
            search_results_text = "\n".join(
                f"Description: {result['description']}, Merchant: {result['merchant']}, "
                f"Amount: ${result['expense_amount']}, Type: {result['shopping_type']}"
                for result in search_results
            )

        # Define input parameters
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "top_k": 250,
            "stop_sequences": [],
            "temperature": 1,
            "top_p": 0.999,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{prompt}\n\nSearch Results:\n{search_results_text}"
                        }
                    ]
                }
            ]
        }

        # Convert to JSON format
        body = json.dumps(payload)

        # Choose inference profile ID
        model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        # Invoke model
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    #else:
        # Use OpenAI client
    #    result = client.chat.completions.create(
    #        model="gpt-4o-mini",
    #        messages=[
    #            {"role": "user", "content": prompt}
    #        ]
    #    )
    #    return result.choices[0].message.content