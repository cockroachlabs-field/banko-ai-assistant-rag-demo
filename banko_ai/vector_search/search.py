"""
Vector search engine for expense data.

This module provides vector similarity search functionality with user-specific
filtering and advanced indexing support.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

from ..ai_providers.base import SearchResult
from ..utils.db_retry import db_retry, create_resilient_engine


class VectorSearchEngine:
    """Vector search engine for expense data with user-specific filtering."""
    
    def __init__(self, database_url: Optional[str] = None, cache_manager=None):
        """Initialize the vector search engine."""
        self.database_url = database_url or os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")
        self.cache_manager = cache_manager
        
        # Apply version parsing workaround for CockroachDB
        from sqlalchemy.dialects.postgresql.base import PGDialect
        original_get_server_version_info = PGDialect._get_server_version_info
        
        def patched_get_server_version_info(self, connection):
            try:
                return original_get_server_version_info(self, connection)
            except Exception:
                return (25, 3, 0)
        
        PGDialect._get_server_version_info = patched_get_server_version_info
        
        # Convert cockroachdb:// to postgresql:// for SQLAlchemy compatibility
        database_url = self.database_url.replace("cockroachdb://", "postgresql://")
        self.engine = create_resilient_engine(
            database_url,
            pool_size=10,
            max_overflow=20
        )
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def simple_search_expenses(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Simple search function that matches the original implementation exactly.
        Returns list of dictionaries like the original search_expenses function.
        """
        print(f"\n🔍 SIMPLE VECTOR SEARCH:")
        print(f"1. Query: '{query}' | Limit: {limit}")
        
        # Generate embedding
        raw_embedding = self.embedding_model.encode(query)
        print(f"2. Generated embedding with {len(raw_embedding)} dimensions")
        
        # Convert to PostgreSQL vector format (matching original implementation)
        import json
        search_embedding = json.dumps(raw_embedding.flatten().tolist())
        
        # Use the exact same query as the original implementation
        search_query = text("""
            SELECT 
                description,
                merchant,
                shopping_type,
                expense_amount,
                embedding <-> :search_embedding as similarity_score
            FROM expenses
            ORDER BY embedding <-> :search_embedding
            LIMIT :limit
        """)
        
        with self.engine.connect() as conn:
            results = conn.execute(search_query, 
                                 {'search_embedding': search_embedding, 'limit': limit})
            search_results = [dict(row._mapping) for row in results]
            print(f"3. Database query returned {len(search_results)} expense records")
            
            return search_results
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def search_expenses(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.7,
        use_user_index: bool = True
    ) -> List[SearchResult]:
        """
        Search for expenses using vector similarity.
        
        Args:
            query: Search query text
            user_id: Optional user ID to filter results
            limit: Maximum number of results to return
            threshold: Minimum similarity score threshold
            use_user_index: Whether to use user-specific vector index
            
        Returns:
            List of SearchResult objects
        """
        print(f"\n🔍 VECTOR SEARCH (with caching):")
        print(f"1. Query: '{query}' | Limit: {limit}")
        
        # Use cached embedding generation if available
        if self.cache_manager:
            raw_embedding = self.cache_manager._get_embedding_with_cache(query)
            
            # Check for cached vector search results
            cached_results = self.cache_manager.get_cached_vector_search(raw_embedding, limit)
            if cached_results:
                print(f"2. ✅ Vector search cache HIT! Found {len(cached_results)} cached results")
                # Convert cached results to SearchResult objects
                search_results = []
                for result in cached_results[:limit]:
                    search_results.append(SearchResult(
                        expense_id=result['expense_id'],
                        user_id=result['user_id'],
                        description=result['description'],
                        merchant=result['merchant'],
                        amount=result['expense_amount'],
                        date=result['expense_date'],
                        similarity_score=result['similarity_score'],
                        metadata={
                            'shopping_type': result['shopping_type'],
                            'payment_method': result['payment_method'],
                            'recurring': result.get('recurring', False),
                            'tags': result.get('tags', [])
                        }
                    ))
                return search_results
            print(f"2. ❌ Vector search cache MISS, querying database")
        else:
            # Fallback to direct embedding generation
            query_embedding = self.embedding_model.encode([query])[0]
            raw_embedding = query_embedding
            print(f"2. Generated fresh embedding (no cache available)")
        
        # Convert to PostgreSQL vector format (matching original implementation)
        import json
        search_embedding = json.dumps(raw_embedding.flatten().tolist())
        
        # Build SQL query based on whether we're using user-specific search
        if user_id and use_user_index:
            sql = self._build_user_specific_query()
        else:
            sql = self._build_general_query()
        
        # Prepare parameters as a dictionary
        params = {
            'search_embedding': search_embedding,
            'limit': limit
        }

        if user_id:
            params['user_id'] = user_id

        # Execute query
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
        
        # Convert to SearchResult objects
        results = []
        for row in rows:
            results.append(SearchResult(
                expense_id=str(row[0]),
                user_id=str(row[1]),
                description=row[2] or "",
                merchant=row[3] or "",
                amount=float(row[4]),
                date=str(row[5]),
                similarity_score=float(row[6]),
                metadata={
                    "shopping_type": row[7] if len(row) > 7 else None,
                    "payment_method": row[8] if len(row) > 8 else None,
                    "recurring": row[9] if len(row) > 9 else None,
                    "tags": row[10] if len(row) > 10 else None
                }
            ))
            
            print(f"3. Database query returned {len(results)} expense records")
            
            # Cache the results for future use (convert back to dict format for caching)
            if self.cache_manager and results:
                # Convert SearchResult objects back to dict format for caching
                search_results_dict = []
                for result in results:
                    search_results_dict.append({
                        'expense_id': result.expense_id,
                        'user_id': result.user_id,
                        'description': result.description,
                        'merchant': result.merchant,
                        'expense_amount': result.amount,
                        'expense_date': result.date,
                        'similarity_score': result.similarity_score,
                        'shopping_type': result.metadata.get('shopping_type'),
                        'payment_method': result.metadata.get('payment_method'),
                        'recurring': result.metadata.get('recurring'),
                        'tags': result.metadata.get('tags')
                    })
                
                self.cache_manager.cache_vector_search_results(raw_embedding, search_results_dict)
                print(f"4. ✅ Cached vector search results for future queries")
            
            return results
    
    def _build_user_specific_query(self) -> str:
        """Build SQL query for user-specific vector search."""
        return """
        SELECT 
            expense_id,
            user_id,
            description,
            merchant,
            expense_amount,
            expense_date,
            embedding <-> :search_embedding as similarity_score,
            shopping_type,
            payment_method,
            recurring,
            tags
        FROM expenses
        WHERE user_id = :user_id
        ORDER BY embedding <-> :search_embedding
        LIMIT :limit
        """
    
    def _build_general_query(self) -> str:
        """Build SQL query for general vector search."""
        return """
        SELECT 
            expense_id,
            user_id,
            description,
            merchant,
            expense_amount,
            expense_date,
            embedding <-> :search_embedding as similarity_score,
            shopping_type,
            payment_method,
            recurring,
            tags
        FROM expenses
        ORDER BY embedding <-> :search_embedding
        LIMIT :limit
        """
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def search_by_category(
        self, 
        category: str, 
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """Search expenses by category."""
        sql = """
        SELECT 
            expense_id,
            user_id,
            description,
            merchant,
            expense_amount,
            expense_date,
            1.0 as similarity_score,
            shopping_type,
            payment_method,
            recurring,
            tags
        FROM expenses
        WHERE shopping_type ILIKE %s
        """
        
        params = [f"%{category}%"]
        
        if user_id:
            sql += " AND user_id = %s"
            params.append(user_id)
        
        sql += " ORDER BY expense_date DESC LIMIT %s"
        params.append(limit)
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
        
        results = []
        for row in rows:
            results.append(SearchResult(
                expense_id=str(row[0]),
                user_id=str(row[1]),
                description=row[2] or "",
                merchant=row[3] or "",
                amount=float(row[4]),
                date=str(row[5]),
                similarity_score=float(row[6]),
                metadata={
                    "shopping_type": row[7],
                    "payment_method": row[8],
                    "recurring": row[9],
                    "tags": row[10]
                }
            ))
        
        return results
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def search_by_merchant(
        self, 
        merchant: str, 
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """Search expenses by merchant."""
        sql = """
        SELECT 
            expense_id,
            user_id,
            description,
            merchant,
            expense_amount,
            expense_date,
            1.0 as similarity_score,
            shopping_type,
            payment_method,
            recurring,
            tags
        FROM expenses
        WHERE merchant ILIKE %s
        """
        
        params = [f"%{merchant}%"]
        
        if user_id:
            sql += " AND user_id = %s"
            params.append(user_id)
        
        sql += " ORDER BY expense_date DESC LIMIT %s"
        params.append(limit)
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()
        
        results = []
        for row in rows:
            results.append(SearchResult(
                expense_id=str(row[0]),
                user_id=str(row[1]),
                description=row[2] or "",
                merchant=row[3] or "",
                amount=float(row[4]),
                date=str(row[5]),
                similarity_score=float(row[6]),
                metadata={
                    "shopping_type": row[7],
                    "payment_method": row[8],
                    "recurring": row[9],
                    "tags": row[10]
                }
            ))
        
        return results
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def get_user_spending_summary(
        self, 
        user_id: str, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get spending summary for a specific user."""
        sql = """
        SELECT 
            COUNT(*) as transaction_count,
            SUM(expense_amount) as total_amount,
            AVG(expense_amount) as average_amount,
            shopping_type,
            COUNT(*) as category_count
        FROM expenses
        WHERE user_id = :user_id
        AND expense_date >= CURRENT_DATE - INTERVAL ':days days'
        GROUP BY shopping_type
        ORDER BY total_amount DESC
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {'user_id': user_id, 'days': days})
            rows = result.fetchall()
        
        summary = {
            "user_id": user_id,
            "period_days": days,
            "total_transactions": sum(row[0] for row in rows),
            "total_amount": sum(row[1] for row in rows),
            "average_transaction": sum(row[2] for row in rows) / len(rows) if rows else 0,
            "categories": []
        }
        
        for row in rows:
            summary["categories"].append({
                "category": row[3],
                "count": row[0],
                "total_amount": float(row[1]),
                "average_amount": float(row[2])
            })
        
        return summary
    
    @db_retry(max_attempts=3, initial_delay=0.5)
    def get_similar_expenses(
        self, 
        expense_id: str, 
        limit: int = 5
    ) -> List[SearchResult]:
        """Find expenses similar to a given expense."""
        # First get the expense details
        expense_sql = """
        SELECT user_id, description, merchant, embedding
        FROM expenses
        WHERE expense_id = %s
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(expense_sql), [expense_id])
            row = result.fetchone()
            
            if not row:
                return []
            
            user_id, description, merchant, embedding = row
            
            # Search for similar expenses
            similar_sql = """
            SELECT 
                expense_id,
                user_id,
                description,
                merchant,
                expense_amount,
                expense_date,
                1 - (embedding <-> %s) as similarity_score,
                shopping_type,
                payment_method,
                recurring,
                tags
            FROM expenses
            WHERE expense_id != %s
            AND user_id = %s
            ORDER BY similarity_score DESC
            LIMIT %s
            """
            
            result = conn.execute(text(similar_sql), [embedding, expense_id, user_id, limit])
            rows = result.fetchall()
        
        results = []
        for row in rows:
            results.append(SearchResult(
                expense_id=str(row[0]),
                user_id=str(row[1]),
                description=row[2] or "",
                merchant=row[3] or "",
                amount=float(row[4]),
                date=str(row[5]),
                similarity_score=float(row[6]),
                metadata={
                    "shopping_type": row[7],
                    "payment_method": row[8],
                    "recurring": row[9],
                    "tags": row[10]
                }
            ))
        
        return results
