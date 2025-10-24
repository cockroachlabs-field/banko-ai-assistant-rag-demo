"""
Banko AI Token Optimization & Caching System

This module implements a multi-layer caching strategy to reduce token usage:
1. Query Similarity Cache - Cache responses for semantically similar queries
2. Embedding Cache - Cache embeddings to avoid regeneration
3. Response Fragment Cache - Cache financial insights and recommendations
4. Vector Search Cache - Cache vector search results

Uses CockroachDB for persistent caching with TTL support.
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import decimal
import uuid
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, DateTime, Float, Boolean
from sqlalchemy import Text as TextColumn
from sqlalchemy.dialects.postgresql import JSONB
import os
from .db_retry import db_retry, create_resilient_engine

# Database configuration
DB_URI = os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")

# Apply CockroachDB version parsing workaround
from sqlalchemy.dialects.postgresql.base import PGDialect
original_get_server_version_info = PGDialect._get_server_version_info

def patched_get_server_version_info(self, connection):
    try:
        return original_get_server_version_info(self, connection)
    except Exception:
        return (25, 3, 0)

PGDialect._get_server_version_info = patched_get_server_version_info

# Convert cockroachdb:// to postgresql:// for SQLAlchemy compatibility
database_url = DB_URI.replace("cockroachdb://", "postgresql://")
engine = create_resilient_engine(database_url)

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal and UUID objects"""
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

def safe_json_dumps(obj, **kwargs):
    """Safe JSON dumps that handles Decimal and UUID objects"""
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)

class BankoCacheManager:
    """
    Intelligent caching system for Banko AI to optimize token usage.
    """
    
    def __init__(self, similarity_threshold=0.85, cache_ttl_hours=24):
        """
        Initialize the cache manager.
        
        Args:
            similarity_threshold: Minimum similarity score to consider queries equivalent
            cache_ttl_hours: Time-to-live for cached responses in hours
        """
        self.similarity_threshold = similarity_threshold
        self.cache_ttl_hours = cache_ttl_hours
        self.model = None  # Lazy load the model
        self._ensure_cache_tables()
    
    def _get_model(self):
        """Lazy load the SentenceTransformer model."""
        if self.model is None:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                print(f"Warning: Could not load SentenceTransformer model: {e}")
                print("Cache functionality will be limited.")
                return None
        return self.model
    
    def _ensure_cache_tables(self):
        """Create cache tables if they don't exist."""
        create_tables_sql = text("""
            -- Query cache for similar questions and responses
            CREATE TABLE IF NOT EXISTS query_cache (
                cache_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                query_hash STRING UNIQUE NOT NULL,
                query_text STRING NOT NULL,
                query_embedding VECTOR(384),
                response_text TEXT NOT NULL,
                response_tokens INTEGER DEFAULT 0,
                prompt_tokens INTEGER DEFAULT 0,
                ai_service STRING NOT NULL,
                expense_data_hash STRING,
                created_at TIMESTAMP DEFAULT now(),
                expires_at TIMESTAMP,
                hit_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT now(),
                INDEX idx_query_hash (query_hash),
                INDEX idx_expires_at (expires_at)
            );
            
            -- Embedding cache to avoid regenerating embeddings
            CREATE TABLE IF NOT EXISTS embedding_cache (
                embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                text_hash STRING UNIQUE NOT NULL,
                text_content STRING NOT NULL,
                embedding VECTOR(384) NOT NULL,
                model_name STRING NOT NULL DEFAULT 'all-MiniLM-L6-v2',
                created_at TIMESTAMP DEFAULT now(),
                access_count INTEGER DEFAULT 0,
                INDEX idx_text_hash (text_hash)
            );
            
            -- Financial insights cache for expense data combinations
            CREATE TABLE IF NOT EXISTS insights_cache (
                insight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                expense_data_hash STRING UNIQUE NOT NULL,
                total_amount DECIMAL(12,2),
                num_transactions INTEGER,
                avg_transaction DECIMAL(10,2),
                top_categories JSONB,
                insights_json JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT now(),
                expires_at TIMESTAMP,
                INDEX idx_expense_hash (expense_data_hash)
            );
            
            -- Vector search results cache
            CREATE TABLE IF NOT EXISTS vector_search_cache (
                search_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                query_embedding_hash STRING UNIQUE NOT NULL,
                search_results JSONB NOT NULL,
                result_count INTEGER,
                similarity_threshold FLOAT,
                created_at TIMESTAMP DEFAULT now(),
                expires_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                INDEX idx_embedding_hash (query_embedding_hash),
                INDEX idx_expires_at (expires_at)
            );
            
            -- Cache statistics for monitoring
            CREATE TABLE IF NOT EXISTS cache_stats (
                stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                cache_type STRING NOT NULL,
                operation STRING NOT NULL, -- 'hit', 'miss', 'write'
                tokens_saved INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT now(),
                details JSONB
            );
        """)
        
        try:
            with engine.connect() as conn:
                conn.execute(create_tables_sql)
                conn.commit()
                print("✅ Cache tables initialized successfully")
        except Exception as e:
            print(f"⚠️ Error creating cache tables: {e}")
    
    def _generate_hash(self, content: str) -> str:
        """Generate a consistent hash for content."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def _get_embedding_with_cache(self, input_text: str) -> np.ndarray:
        """Get embedding for text, using cache when possible."""
        text_hash = self._generate_hash(input_text)
        
        # Try to get from cache first
        cache_query = text("""
            SELECT embedding, access_count
            FROM embedding_cache 
            WHERE text_hash = :text_hash
        """)
        with engine.connect() as conn:
            result = conn.execute(cache_query, {'text_hash': text_hash})
            row = result.fetchone()
            
            if row:
                # Cache hit - update access count
                update_query = text("""
                    UPDATE embedding_cache 
                    SET access_count = access_count + 1 
                    WHERE text_hash = :text_hash
                """)
                conn.execute(update_query, {'text_hash': text_hash})
                conn.commit()
                
                self._log_cache_stat('embedding', 'hit', tokens_saved=10)
                return np.array(json.loads(row.embedding))
        
        # Cache miss - generate embedding and store
        model = self._get_model()
        if model is None:
            return None
        embedding = model.encode(input_text)
        embedding_json = json.dumps(embedding.tolist())
        
        try:
            with engine.connect() as conn:
                insert_query = text("""
                    INSERT INTO embedding_cache (text_hash, text_content, embedding, access_count)
                    VALUES (:text_hash, :text_content, :embedding, 1)
                    ON CONFLICT (text_hash) DO UPDATE SET access_count = embedding_cache.access_count + 1
                """)
                conn.execute(insert_query, {
                    'text_hash': text_hash,
                    'text_content': input_text[:500],  # Truncate for storage
                    'embedding': embedding_json
                })
                conn.commit()
                self._log_cache_stat('embedding', 'miss')
                
        except Exception as e:
            print(f"⚠️ Error caching embedding: {e}")
        
        return embedding
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def get_cached_response(self, query: str, expense_data: List[Dict], ai_service: str) -> Optional[str]:
        """
        Check if we have a cached response for a similar query.
        
        Args:
            query: User query text
            expense_data: Current expense data context
            ai_service: AI service being used (watsonx, bedrock)
        
        Returns:
            Cached response text if found, None otherwise
        """
        query_embedding = self._get_embedding_with_cache(query)
        expense_hash = self._generate_hash(safe_json_dumps(expense_data, sort_keys=True))
        
        # Find similar cached queries
        similarity_query = text("""
            SELECT cache_id, query_text, response_text, response_tokens, prompt_tokens,
                   query_embedding <-> :query_embedding as similarity_score,
                   hit_count, expires_at
            FROM query_cache 
            WHERE ai_service = :ai_service 
              AND (expense_data_hash = :expense_hash OR expense_data_hash IS NULL)
              AND expires_at > now()
            ORDER BY query_embedding <-> :query_embedding
            LIMIT 5
        """)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(similarity_query, {
                    'query_embedding': json.dumps(query_embedding.tolist()),
                    'ai_service': ai_service,
                    'expense_hash': expense_hash
                })
                
                for row in result:
                    similarity_score = 1 - row.similarity_score  # Convert distance to similarity
                    
                    if similarity_score >= self.similarity_threshold:
                        # Cache hit! Update statistics
                        update_query = text("""
                            UPDATE query_cache 
                            SET hit_count = hit_count + 1, last_accessed = now()
                            WHERE cache_id = :cache_id
                        """)
                        conn.execute(update_query, {'cache_id': row.cache_id})
                        conn.commit()
                        
                        tokens_saved = (row.response_tokens or 500) + (row.prompt_tokens or 400)
                        self._log_cache_stat('query', 'hit', tokens_saved=tokens_saved, details={
                            'original_query': row.query_text,
                            'new_query': query,
                            'similarity_score': similarity_score
                        })
                        
                        print(f"🎯 Cache HIT! Similarity: {similarity_score:.3f} | Tokens saved: {tokens_saved}")
                        print(f"   Original: '{row.query_text[:50]}...'")
                        print(f"   Current:  '{query[:50]}...'")
                        
                        return row.response_text
                
        except Exception as e:
            print(f"⚠️ Error checking query cache: {e}")
        
        self._log_cache_stat('query', 'miss')
        return None
    
    def cache_response(self, query: str, response: str, expense_data: List[Dict], 
                      ai_service: str, prompt_tokens: int = 0, response_tokens: int = 0):
        """
        Cache a query response for future use.
        
        Args:
            query: Original user query
            response: AI response
            expense_data: Expense data context
            ai_service: AI service used
            prompt_tokens: Number of prompt tokens used
            response_tokens: Number of response tokens generated
        """
        query_hash = self._generate_hash(query)
        query_embedding = self._get_embedding_with_cache(query)
        expense_hash = self._generate_hash(safe_json_dumps(expense_data, sort_keys=True))
        expires_at = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)
        
        try:
            with engine.connect() as conn:
                insert_query = text("""
                    INSERT INTO query_cache (
                        query_hash, query_text, query_embedding, response_text,
                        response_tokens, prompt_tokens, ai_service, expense_data_hash,
                        expires_at
                    ) VALUES (
                        :query_hash, :query_text, :query_embedding, :response_text,
                        :response_tokens, :prompt_tokens, :ai_service, :expense_hash,
                        :expires_at
                    )
                    ON CONFLICT (query_hash) DO UPDATE SET
                        response_text = EXCLUDED.response_text,
                        response_tokens = EXCLUDED.response_tokens,
                        prompt_tokens = EXCLUDED.prompt_tokens,
                        expires_at = EXCLUDED.expires_at,
                        hit_count = 0,
                        last_accessed = now()
                """)
                
                conn.execute(insert_query, {
                    'query_hash': query_hash,
                    'query_text': query,
                    'query_embedding': json.dumps(query_embedding.tolist()),
                    'response_text': response,
                    'response_tokens': response_tokens,
                    'prompt_tokens': prompt_tokens,
                    'ai_service': ai_service,
                    'expense_hash': expense_hash,
                    'expires_at': expires_at
                })
                conn.commit()
                
                self._log_cache_stat('query', 'write', details={
                    'query_length': len(query),
                    'response_length': len(response)
                })
                
        except Exception as e:
            print(f"⚠️ Error caching response: {e}")
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def get_cached_vector_search(self, query_embedding: np.ndarray, limit: int = 5) -> Optional[List[Dict]]:
        """Get cached vector search results."""
        embedding_hash = self._generate_hash(json.dumps(query_embedding.tolist()))
        
        cache_query = text("""
            SELECT search_results, access_count
            FROM vector_search_cache
            WHERE query_embedding_hash = :embedding_hash
              AND expires_at > now()
              AND result_count >= :limit
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(cache_query, {
                    'embedding_hash': embedding_hash,
                    'limit': limit
                })
                row = result.fetchone()
                
                if row:
                    # Update access count
                    update_query = text("""
                        UPDATE vector_search_cache 
                        SET access_count = access_count + 1 
                        WHERE query_embedding_hash = :embedding_hash
                    """)
                    conn.execute(update_query, {'embedding_hash': embedding_hash})
                    conn.commit()
                    
                    self._log_cache_stat('vector_search', 'hit', tokens_saved=50)
                    # search_results is already a list from JSONB, no need to parse
                    if isinstance(row.search_results, list):
                        return row.search_results[:limit]
                    else:
                        # Fallback: try to parse if it's a string
                        return json.loads(row.search_results)[:limit]
                    
        except Exception as e:
            print(f"⚠️ Error reading vector search cache: {e}")
        
        self._log_cache_stat('vector_search', 'miss')
        return None
    
    def cache_vector_search_results(self, query_embedding: np.ndarray, results: List[Dict]):
        """Cache vector search results."""
        embedding_hash = self._generate_hash(json.dumps(query_embedding.tolist()))
        expires_at = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)
        
        try:
            with engine.connect() as conn:
                insert_query = text("""
                    INSERT INTO vector_search_cache (
                        query_embedding_hash, search_results, result_count, 
                        similarity_threshold, expires_at
                    ) VALUES (
                        :embedding_hash, :results, :count, :threshold, :expires_at
                    )
                    ON CONFLICT (query_embedding_hash) DO UPDATE SET
                        search_results = EXCLUDED.search_results,
                        result_count = EXCLUDED.result_count,
                        expires_at = EXCLUDED.expires_at,
                        access_count = 0
                """)
                
                conn.execute(insert_query, {
                    'embedding_hash': embedding_hash,
                    'results': safe_json_dumps(results),
                    'count': len(results),
                    'threshold': self.similarity_threshold,
                    'expires_at': expires_at
                })
                conn.commit()
                
                self._log_cache_stat('vector_search', 'write')
                
        except Exception as e:
            print(f"⚠️ Error caching vector search: {e}")
    
    def get_cached_insights(self, expense_data: List[Dict]) -> Optional[Dict]:
        """
        Get cached financial insights for a set of expense data.
        
        Args:
            expense_data: List of expense dictionaries
            
        Returns:
            Cached insights dictionary if found, None otherwise
        """
        expense_hash = self._generate_hash(safe_json_dumps(expense_data, sort_keys=True))
        
        insights_query = text("""
            SELECT total_amount, num_transactions, avg_transaction, 
                   top_categories, insights_json
            FROM insights_cache 
            WHERE expense_data_hash = :expense_hash
              AND expires_at > now()
        """)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(insights_query, {'expense_hash': expense_hash})
                row = result.fetchone()
                
                if row:
                    self._log_cache_stat('insights', 'hit', tokens_saved=200)
                    print(f"🎯 Insights Cache HIT! Expense hash: {expense_hash[:8]}...")
                    return {
                        'total_amount': float(row.total_amount),
                        'num_transactions': row.num_transactions,
                        'avg_transaction': float(row.avg_transaction),
                        'top_categories': json.loads(row.top_categories) if isinstance(row.top_categories, str) else row.top_categories,
                        'insights': json.loads(row.insights_json) if isinstance(row.insights_json, str) else row.insights_json
                    }
        except Exception as e:
            print(f"⚠️ Error getting cached insights: {e}")
        
        self._log_cache_stat('insights', 'miss')
        return None
    
    def cache_insights(self, expense_data: List[Dict], insights: Dict):
        """
        Cache financial insights for expense data.
        
        Args:
            expense_data: List of expense dictionaries
            insights: Dictionary containing financial insights
        """
        expense_hash = self._generate_hash(safe_json_dumps(expense_data, sort_keys=True))
        expires_at = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)
        
        # Calculate summary statistics
        total_amount = sum(float(e.get('expense_amount', 0)) for e in expense_data)
        num_transactions = len(expense_data)
        avg_transaction = total_amount / num_transactions if num_transactions > 0 else 0
        
        # Get top categories
        categories = {}
        for exp in expense_data:
            cat = exp.get('shopping_type', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
        top_categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5])
        
        try:
            with engine.connect() as conn:
                insert_query = text("""
                    INSERT INTO insights_cache (
                        expense_data_hash, total_amount, num_transactions, 
                        avg_transaction, top_categories, insights_json, expires_at
                    ) VALUES (
                        :expense_hash, :total_amount, :num_transactions,
                        :avg_transaction, :top_categories, :insights_json, :expires_at
                    )
                    ON CONFLICT (expense_data_hash) DO UPDATE SET
                        total_amount = EXCLUDED.total_amount,
                        num_transactions = EXCLUDED.num_transactions,
                        avg_transaction = EXCLUDED.avg_transaction,
                        top_categories = EXCLUDED.top_categories,
                        insights_json = EXCLUDED.insights_json,
                        expires_at = EXCLUDED.expires_at,
                        created_at = now()
                """)
                conn.execute(insert_query, {
                    'expense_hash': expense_hash,
                    'total_amount': total_amount,
                    'num_transactions': num_transactions,
                    'avg_transaction': avg_transaction,
                    'top_categories': safe_json_dumps(top_categories),
                    'insights_json': safe_json_dumps(insights),
                    'expires_at': expires_at
                })
                conn.commit()
                self._log_cache_stat('insights', 'write')
        except Exception as e:
            print(f"⚠️ Error caching insights: {e}")
    
    def _log_cache_stat(self, cache_type: str, operation: str, tokens_saved: int = 0, details: Dict = None):
        """Log cache statistics for monitoring."""
        try:
            with engine.connect() as conn:
                insert_query = text("""
                    INSERT INTO cache_stats (cache_type, operation, tokens_saved, details)
                    VALUES (:cache_type, :operation, :tokens_saved, :details)
                """)
                conn.execute(insert_query, {
                    'cache_type': cache_type,
                    'operation': operation,
                    'tokens_saved': tokens_saved,
                    'details': json.dumps(details) if details else None
                })
                conn.commit()
        except Exception as e:
            print(f"⚠️ Error logging cache stats: {e}")
    
    def get_cache_stats(self, hours: int = 24) -> Dict:
        """Get cache performance statistics."""
        stats_query = text("""
            WITH cache_summary AS (
                SELECT 
                    cache_type,
                    operation,
                    COUNT(*) as count,
                    SUM(tokens_saved) as total_tokens_saved
                FROM cache_stats 
                WHERE timestamp >= now() - INTERVAL ':hours hours'
                GROUP BY cache_type, operation
            )
            SELECT 
                cache_type,
                SUM(CASE WHEN operation = 'hit' THEN count ELSE 0 END) as hits,
                SUM(CASE WHEN operation = 'miss' THEN count ELSE 0 END) as misses,
                SUM(CASE WHEN operation = 'write' THEN count ELSE 0 END) as writes,
                SUM(total_tokens_saved) as tokens_saved
            FROM cache_summary
            GROUP BY cache_type
            ORDER BY cache_type
        """)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(stats_query, {'hours': hours})
                stats = {}
                total_tokens_saved = 0
                
                for row in result:
                    hit_rate = row.hits / (row.hits + row.misses) if (row.hits + row.misses) > 0 else 0
                    stats[row.cache_type] = {
                        'hits': row.hits,
                        'misses': row.misses,
                        'writes': row.writes,
                        'hit_rate': hit_rate,
                        'tokens_saved': row.tokens_saved
                    }
                    total_tokens_saved += float(row.tokens_saved or 0)
                
                stats['total_tokens_saved'] = total_tokens_saved
                return stats
                
        except Exception as e:
            print(f"⚠️ Error getting cache stats: {e}")
            return {}
    
    def cleanup_expired_cache(self):
        """Remove expired cache entries."""
        cleanup_queries = [
            "DELETE FROM query_cache WHERE expires_at < now()",
            "DELETE FROM insights_cache WHERE expires_at < now()",
            "DELETE FROM vector_search_cache WHERE expires_at < now()"
        ]
        
        try:
            with engine.connect() as conn:
                for query in cleanup_queries:
                    result = conn.execute(text(query))
                    print(f"🧹 Cleaned up {result.rowcount} expired cache entries")
                conn.commit()
        except Exception as e:
            print(f"⚠️ Error cleaning up cache: {e}")

# Global cache manager instance
cache_manager = BankoCacheManager()
