from config import API_KEY
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import numpy as np
import boto3
import json
import os
import sys

# Add watsonx directory to path to import transaction categorizer
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'watsonx'))
from transaction_categorizer import categorizer

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

def get_query_embedding(query_text):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode(query_text)
    return query_embedding

def numpy_vector_to_pg_vector(vector):
    return json.dumps(vector.flatten().tolist())

def search_expenses(query, limit=5):
    """
    Search for expenses using semantic similarity with intelligent caching.
    """
    print(f"\n🔍 AWS BEDROCK SEARCH (with caching):")
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
            search_results = [dict(row._mapping) for row in results]
            print(f"4. Database query returned {len(search_results)} expense records")
            
            # Cache the results for future use
            if cache_manager and search_results:
                cache_manager.cache_vector_search_results(raw_embedding, search_results)
                print(f"5. ✅ Cached vector search results for future queries")
            
            return search_results
    except Exception as e:
        print(f"❌ Error executing query: {e}")
        return []

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

def RAG_response(prompt, search_results=None, use_bedrock=True):
    """
    Generate a RAG response using AWS Bedrock with intelligent caching.
    """
    print(f"\n🤖 AWS BEDROCK RAG (with caching):")
    print(f"1. Query: '{prompt[:60]}...'")
    
    if not use_bedrock:
        return "AWS Bedrock integration is disabled."
    
    # Check for cached response first
    if cache_manager:
        cached_response = cache_manager.get_cached_response(
            prompt, search_results or [], "bedrock"
        )
        if cached_response:
            print(f"2. ✅ Response cache HIT! Returning cached response")
            return cached_response
        print(f"2. ❌ Response cache MISS, generating fresh response")
    else:
        print(f"2. No cache manager available, generating fresh response")
    
    if use_bedrock:
        # Initialize Bedrock client
        bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

        # Generate financial insights and categorization analysis
        insights = get_financial_insights(search_results)
        category_analysis = analyze_transaction_categories(search_results)
        budget_recommendations = generate_budget_recommendations(insights, prompt, category_analysis)

        # Prepare the search results text with enhanced analysis
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
                            "text": f"""You are Banko, a financial assistant. Answer based on this expense data:

Q: {prompt}

Data:
{search_results_text}

{budget_recommendations if budget_recommendations else ''}

Provide helpful insights with numbers, markdown formatting, and actionable advice."""
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
        print(f"3. 🔄 Calling AWS Bedrock API...")
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        ai_response = response_body['content'][0]['text']
        print(f"4. ✅ AWS Bedrock response generated successfully")
        
        # Cache the response for future similar queries
        if cache_manager and ai_response:
            # Estimate token usage (rough approximation)
            enhanced_prompt = payload['messages'][0]['content'][0]['text']
            prompt_tokens = len(enhanced_prompt.split()) * 1.3  # ~1.3 tokens per word
            response_tokens = len(ai_response.split()) * 1.3
            
            cache_manager.cache_response(
                prompt, ai_response, search_results or [], "bedrock",
                int(prompt_tokens), int(response_tokens)
            )
            print(f"5. ✅ Cached response (est. {int(prompt_tokens + response_tokens)} tokens)")
        
        return ai_response
    #else:
        # Use OpenAI client
    #    result = client.chat.completions.create(
    #        model="gpt-4o-mini",
    #        messages=[
    #            {"role": "user", "content": prompt}
    #        ]
    #    )
    #    return result.choices[0].message.content