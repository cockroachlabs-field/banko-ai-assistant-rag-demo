"""
IBM Watsonx AI Integration Module for Banko Assistant

This module provides integration with IBM Watsonx AI services to power the 
Banko Assistant's conversational capabilities. It includes functions for:
- Expense data search and retrieval
- RAG (Retrieval Augmented Generation) responses
- Financial data analysis

Dependencies:
- requests: For HTTP API calls to Watsonx
- numpy: For vector operations
- json: For data serialization
- sentence_transformers: For embedding generation
- sqlalchemy: For database operations

Author: Banko AI Team
Date: 2025
"""

import os
import requests
import json
import numpy as np
import sys
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from .transaction_categorizer import categorizer

# Import cache manager
sys.path.append('..')
try:
    from cache_manager import cache_manager
except ImportError:
    print("⚠️ Cache manager not available, running without caching")
    cache_manager = None

# Database connection settings
DB_URI = os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")
engine = create_engine(DB_URI)

# Watsonx API Configuration
WATSONX_API_URL = "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29"
DEFAULT_MODEL_ID = "openai/gpt-oss-120b"
DEFAULT_PROJECT_ID = "e63e496b-aad4-49e0-906f-9e5e0e93039d"

def get_watsonx_config():
    """
    Retrieve Watsonx configuration from environment variables or config file.
    
    Returns:
        dict: Configuration dictionary containing API key, project ID, and model ID
        
    Raises:
        ValueError: If required configuration is missing
    """
    try:
        # First try to get from config file
        from config import WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_MODEL_ID
        return {
            'api_key': WATSONX_API_KEY,
            'project_id': WATSONX_PROJECT_ID,
            'model_id': WATSONX_MODEL_ID
        }
    except ImportError:
        # Fall back to environment variables
        api_key = os.getenv('WATSONX_API_KEY')
        project_id = os.getenv('WATSONX_PROJECT_ID', DEFAULT_PROJECT_ID)
        model_id = os.getenv('WATSONX_MODEL_ID', DEFAULT_MODEL_ID)
        
        if not api_key:
            raise ValueError("Watsonx API key not found in config.py or environment variables")
        
        return {
            'api_key': api_key,
            'project_id': project_id,
            'model_id': model_id
        }

def get_query_embedding(query_text):
    """
    Generate embeddings for a given query text using SentenceTransformer.
    
    Args:
        query_text (str): The text query to embed
        
    Returns:
        numpy.ndarray: The embedding vector for the query
    """
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode(query_text)
    return query_embedding

def numpy_vector_to_pg_vector(vector):
    """
    Convert a numpy vector to PostgreSQL-compatible vector format.
    
    Args:
        vector (numpy.ndarray): Input vector
        
    Returns:
        str: JSON string representation of the vector
    """
    return json.dumps(vector.flatten().tolist())

def search_expenses(query, limit=5):
    """
    Search for expenses using semantic similarity with the query.
    Uses intelligent caching to reduce embedding computation and database queries.
    
    This function creates embeddings for the search query and finds the most
    similar expenses in the database using vector similarity search.
    
    Args:
        query (str): Natural language query for expense search
        limit (int): Maximum number of results to return (default: 5)
        
    Returns:
        list: List of dictionaries containing expense records with similarity scores
    """
    print(f"\n🔍 WATSONX SEARCH (with caching):")
    print(f"1. Query: '{query}' | Limit: {limit}")
    
    # Use cached embedding generation if available
    if cache_manager:
        raw_embedding = cache_manager._get_embedding_with_cache(query)
        
        # Check for cached vector search results
        cached_results = cache_manager.get_cached_vector_search(raw_embedding, limit)
        if cached_results:
            print(f"2. ✅ Vector search cache HIT! Found {len(cached_results)} cached results")
            return cached_results[:limit]
        print(f"2. ❌ Vector search cache MISS, querying database")
    else:
        # Fallback to direct embedding generation
        model = SentenceTransformer('all-MiniLM-L6-v2')
        raw_embedding = model.encode(query)
        print(f"2. Generated fresh embedding (no cache available)")
    
    search_embedding = numpy_vector_to_pg_vector(raw_embedding)
    print(f"3. Search embedding: {len(json.loads(search_embedding))} dimensions")
    
    # Vector similarity search query
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
            search_results = [dict(row._mapping) for row in results]
            print(f"4. Database query returned {len(search_results)} expense records")
            
            # Cache the results for future use
            if cache_manager and search_results:
                cache_manager.cache_vector_search_results(raw_embedding, search_results)
                print(f"5. ✅ Cached vector search results for future queries")
            
            return search_results
    except Exception as e:
        print(f"❌ Error executing expense search query: {e}")
        return []

def get_access_token(api_key):
    """
    Get access token from IBM Cloud IAM using the API key.
    
    Args:
        api_key (str): IBM Cloud API key
        
    Returns:
        str: Access token for API calls
        
    Raises:
        Exception: If token retrieval fails
    """
    token_url = "https://iam.cloud.ibm.com/identity/token"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": api_key
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"Failed to get access token (status {response.status_code}): {response.text}")
        
        token_data = response.json()
        return token_data.get('access_token')
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Token request failed: {str(e)}")
    except json.JSONDecodeError:
        raise Exception("Invalid JSON response from IBM Cloud IAM")

def call_watsonx_api(messages, config=None):
    """
    Make a direct API call to IBM Watsonx chat endpoint.
    
    Args:
        messages (list): List of message objects for the chat
        config (dict, optional): Watsonx configuration override
        
    Returns:
        str: Generated response from Watsonx
        
    Raises:
        Exception: If API call fails or returns non-200 status
    """
    if config is None:
        config = get_watsonx_config()
    
    # Get access token from API key
    access_token = get_access_token(config['api_key'])
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    body = {
        "project_id": config['project_id'],
        "model_id": config['model_id'],
        "messages": messages,
        "frequency_penalty": 0,
        "max_tokens": 2000,
        "presence_penalty": 0,
        "temperature": 0.7,
        "top_p": 1
    }
    
    try:
        response = requests.post(
            WATSONX_API_URL,
            headers=headers,
            json=body,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Watsonx API error (status {response.status_code}): {response.text}")
        
        data = response.json()
        
        # Extract the assistant's response from the API response
        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0]['message']['content']
        elif 'generated_text' in data:
            return data['generated_text']
        else:
            # Handle different response formats
            print(f"Unexpected Watsonx response format: {data}")
            return "I apologize, but I'm having trouble generating a response right now."
            
    except requests.exceptions.Timeout:
        raise Exception("Watsonx API request timed out")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Watsonx API request failed: {str(e)}")
    except json.JSONDecodeError:
        raise Exception("Invalid JSON response from Watsonx API")

def get_financial_insights(search_results):
    """Generate comprehensive financial insights from expense data."""
    if not search_results:
        return {}
    
    total_amount = sum(float(result['expense_amount']) for result in search_results)
    categories = {}
    merchants = {}
    payment_methods = {}
    
    for result in search_results:
        # Category analysis
        category = result['shopping_type']
        categories[category] = categories.get(category, 0) + float(result['expense_amount'])
        
        # Merchant analysis
        merchant = result['merchant']
        merchants[merchant] = merchants.get(merchant, 0) + float(result['expense_amount'])
        
        # Payment method analysis
        payment = result['payment_method']
        payment_methods[payment] = payment_methods.get(payment, 0) + float(result['expense_amount'])
    
    # Find top categories and merchants
    top_category = max(categories.items(), key=lambda x: x[1]) if categories else None
    top_merchant = max(merchants.items(), key=lambda x: x[1]) if merchants else None
    
    return {
        'total_amount': total_amount,
        'num_transactions': len(search_results),
        'avg_transaction': total_amount / len(search_results),
        'categories': categories,
        'top_category': top_category,
        'top_merchant': top_merchant,
        'payment_methods': payment_methods
    }

def analyze_transaction_categories(search_results):
    """Analyze and categorize transactions using ML-based categorization."""
    if not search_results:
        return {}
    
    # Use the transaction categorizer to analyze patterns
    analysis = categorizer.analyze_spending_patterns(search_results)
    
    return analysis

def generate_budget_recommendations(insights, prompt, category_analysis=None):
    """Generate personalized budget recommendations based on spending patterns."""
    if not insights:
        return ""
    
    recommendations = []
    
    # High spending category recommendations
    if insights.get('top_category'):
        category, amount = insights['top_category']
        recommendations.append(f"Your highest spending category is **{category}** at **${amount:.2f}**. Consider setting a monthly budget limit for this category.")
    
    # Average transaction analysis
    avg_amount = insights.get('avg_transaction', 0)
    if avg_amount > 100:
        recommendations.append(f"Your average transaction is **${avg_amount:.2f}**. Consider reviewing larger purchases to identify potential savings.")
    
    # Merchant frequency analysis
    if insights.get('top_merchant'):
        merchant, amount = insights['top_merchant']
        recommendations.append(f"You frequently shop at **{merchant}** (${amount:.2f} total). Look for loyalty programs or discounts at this merchant.")
    
    # Smart categorization recommendations
    if category_analysis and category_analysis.get('recommendations'):
        recommendations.extend(category_analysis['recommendations'])
    
    # Categorization insights
    if category_analysis and category_analysis.get('uncategorized_count', 0) > 0:
        uncategorized_count = category_analysis['uncategorized_count']
        recommendations.append(f"**🏷️ Categorization**: {uncategorized_count} transactions could benefit from better categorization for improved budget tracking.")
    
    # Anomaly alerts
    if category_analysis and category_analysis.get('anomalies'):
        anomaly_count = len(category_analysis['anomalies'])
        if anomaly_count > 0:
            recommendations.append(f"**⚠️ Spending Alert**: {anomaly_count} unusual transactions detected that may need review.")
    
    # General budgeting tips
    if insights.get('total_amount', 0) > 500:
        recommendations.append("💡 **Budget Tip**: Consider the 50/30/20 rule: 50% for needs, 30% for wants, 20% for savings and debt repayment.")
    
    return "\n".join(recommendations) if recommendations else ""

def RAG_response(prompt, search_results=None, use_watsonx=True):
    """
    Generate a RAG (Retrieval Augmented Generation) response using IBM Watsonx.
    Uses intelligent caching to reduce token usage for similar queries.
    
    This function combines the user's prompt with relevant expense data from the
    search results to provide contextual, accurate responses about financial information.
    
    Args:
        prompt (str): User's question or query
        search_results (list, optional): List of relevant expense records
        use_watsonx (bool): Whether to use Watsonx (default: True)
        
    Returns:
        str: AI-generated response incorporating the search results
    """
    print(f"\n🤖 WATSONX RAG (with caching):")
    print(f"1. Query: '{prompt[:60]}...'")
    
    if not use_watsonx:
        return "Watsonx integration is disabled."
    
    # Check for cached response first
    if cache_manager:
        cached_response = cache_manager.get_cached_response(
            prompt, search_results or [], "watsonx"
        )
        if cached_response:
            print(f"2. ✅ Response cache HIT! Returning cached response")
            return cached_response
        print(f"2. ❌ Response cache MISS, generating fresh response")
    else:
        print(f"2. No cache manager available, generating fresh response")
    
    try:
        # Generate financial insights and categorization analysis
        insights = get_financial_insights(search_results)
        category_analysis = analyze_transaction_categories(search_results)
        budget_recommendations = generate_budget_recommendations(insights, prompt, category_analysis)
        
        # Prepare the search results context with enhanced analysis
        search_results_text = ""
        if search_results:
            search_results_text = "\n".join(
                f"• **{result['shopping_type']}** at {result['merchant']}: ${result['expense_amount']} ({result['payment_method']}) - {result['description']}"
                for result in search_results
            )
            
            # Add financial summary
            if insights:
                search_results_text += f"\n\n**📊 Financial Summary:**\n"
                search_results_text += f"• Total Amount: **${insights['total_amount']:.2f}**\n"
                search_results_text += f"• Number of Transactions: **{insights['num_transactions']}**\n"
                search_results_text += f"• Average Transaction: **${insights['avg_transaction']:.2f}**\n"
                if insights.get('top_category'):
                    cat, amt = insights['top_category']
                    search_results_text += f"• Top Category: **{cat}** (${amt:.2f})\n"
        else:
            search_results_text = "No specific expense records found for this query."
        
        # Create optimized prompt (reduced tokens while maintaining quality)
        enhanced_prompt = f"""You are Banko, a financial assistant. Answer based on this expense data:

Q: {prompt}

Data:
{search_results_text}

{budget_recommendations if budget_recommendations else ''}

Provide helpful insights with numbers, markdown formatting, and actionable advice."""
        
        # Prepare messages for chat format
        messages = [
            {
                "role": "user",
                "content": enhanced_prompt
            }
        ]
        
        # Call Watsonx API
        print(f"3. 🔄 Calling Watsonx API...")
        response = call_watsonx_api(messages)
        print(f"4. ✅ Watsonx response generated successfully")
        
        # Cache the response for future similar queries
        if cache_manager and response:
            # Estimate token usage (rough approximation)
            prompt_tokens = len(enhanced_prompt.split()) * 1.3  # ~1.3 tokens per word
            response_tokens = len(response.split()) * 1.3
            
            cache_manager.cache_response(
                prompt, response, search_results or [], "watsonx",
                int(prompt_tokens), int(response_tokens)
            )
            print(f"5. ✅ Cached response (est. {int(prompt_tokens + response_tokens)} tokens)")
        
        return response
        
    except Exception as e:
        error_msg = f"❌ Error generating Watsonx response: {str(e)}"
        print(error_msg)
        return f"I apologize, but I'm experiencing technical difficulties. Please try again later. (Error: {str(e)})"

def search_expenses_with_cache_info(query, limit=5):
    """
    Enhanced search function that returns both results and cache hit/miss information
    for demo purposes.
    """
    cache_info = {
        "embedding_cache": "miss",
        "vector_search_cache": "miss"
    }
    
    print(f"\n🔍 WATSONX SEARCH (with cache info):")
    print(f"1. Query: '{query}' | Limit: {limit}")
    
    # Track cache performance
    if cache_manager:
        # Generate/get embedding and track cache status
        text_hash = cache_manager._generate_hash(query)
        
        # Check if embedding is cached
        from sqlalchemy import text as sql_text
        try:
            with cache_manager.engine.connect() as conn:
                cache_query = sql_text("SELECT embedding FROM embedding_cache WHERE text_hash = :text_hash")
                result = conn.execute(cache_query, {'text_hash': text_hash})
                cached_embedding = result.fetchone()
                
                if cached_embedding:
                    cache_info["embedding_cache"] = "hit"
                    print("2. ✅ Embedding cache HIT")
                else:
                    cache_info["embedding_cache"] = "miss"
                    print("2. ❌ Embedding cache MISS")
        except:
            cache_info["embedding_cache"] = "miss"
        
        # Get embedding and check vector search cache
        raw_embedding = cache_manager._get_embedding_with_cache(query)
        cached_results = cache_manager.get_cached_vector_search(raw_embedding, limit)
        
        if cached_results:
            print(f"3. ✅ Vector search cache HIT! Found {len(cached_results)} cached results")
            cache_info["vector_search_cache"] = "hit"
            return cached_results[:limit], cache_info
        else:
            print(f"3. ❌ Vector search cache MISS, querying database")
            cache_info["vector_search_cache"] = "miss"
    else:
        print("2. No cache manager available")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        raw_embedding = model.encode(query)
    
    # Perform regular search
    results = search_expenses(query, limit)
    return results, cache_info

def RAG_response_with_cache_info(prompt, search_results=None, use_watsonx=True):
    """
    Enhanced RAG function that returns both response and cache status for demo purposes.
    """
    print(f"\n🤖 WATSONX RAG (with cache info):")
    print(f"1. Query: '{prompt[:60]}...'")
    
    response_cache_status = "miss"
    
    if cache_manager:
        # Check for cached response
        cached_response = cache_manager.get_cached_response(
            prompt, search_results or [], "watsonx"
        )
        if cached_response:
            print(f"2. ✅ Response cache HIT! Returning cached response")
            response_cache_status = "hit"
            return cached_response, response_cache_status
        print(f"2. ❌ Response cache MISS, generating fresh response")
    
    # Generate fresh response
    response = RAG_response(prompt, search_results, use_watsonx)
    return response, response_cache_status

def test_watsonx_connection():
    """
    Test the connection to Watsonx API to verify configuration.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        config = get_watsonx_config()
        test_messages = [{"role": "user", "content": "Hello, this is a test message."}]
        response = call_watsonx_api(test_messages, config)
        return True, f"Watsonx connection successful. Response: {response[:100]}..."
    except Exception as e:
        return False, f"Watsonx connection failed: {str(e)}"

if __name__ == "__main__":
    # Test the Watsonx integration
    print("Testing Watsonx integration...")
    success, message = test_watsonx_connection()
    print(f"Test result: {message}")
    
    if success:
        print("\nTesting expense search...")
        results = search_expenses("restaurant expenses", limit=3)
        print(f"Found {len(results)} results")
        
        print("\nTesting RAG response...")
        rag_result = RAG_response("How much did I spend on restaurants?", results)
        print(f"RAG Response: {rag_result}")
