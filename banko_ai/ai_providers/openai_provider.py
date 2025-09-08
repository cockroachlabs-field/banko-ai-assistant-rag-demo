"""
OpenAI AI provider implementation.

This module provides OpenAI integration for vector search and RAG responses.
"""

import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import numpy as np
from sqlalchemy import create_engine, text

from .base import AIProvider, SearchResult, RAGResponse, AIConnectionError, AIAuthenticationError


class OpenAIProvider(AIProvider):
    """OpenAI AI provider implementation."""
    
    def __init__(self, config: Dict[str, Any], cache_manager=None):
        """Initialize OpenAI provider."""
        self.api_key = config.get("api_key")
        self.client = None
        self.embedding_model = None
        self.db_engine = None
        self.cache_manager = cache_manager
        super().__init__(config)
    
    def _validate_config(self) -> None:
        """Validate OpenAI configuration."""
        if not self.api_key:
            raise AIAuthenticationError("OpenAI API key is required")
        
        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            raise AIConnectionError(f"Failed to initialize OpenAI client: {str(e)}")
    
    def get_default_model(self) -> str:
        """Get the default OpenAI model."""
        return "gpt-3.5-turbo"
    
    def get_available_models(self) -> List[str]:
        """Get available OpenAI models."""
        return [
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k", 
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini"
        ]
    
    def _get_embedding_model(self) -> SentenceTransformer:
        """Get or create the embedding model."""
        if self.embedding_model is None:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                raise AIConnectionError(f"Failed to load embedding model: {str(e)}")
        return self.embedding_model
    
    def _get_db_engine(self):
        """Get database engine."""
        if self.db_engine is None:
            database_url = os.getenv("DATABASE_URL", "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")
            try:
                self.db_engine = create_engine(database_url)
            except Exception as e:
                raise AIConnectionError(f"Failed to connect to database: {str(e)}")
        return self.db_engine
    
    def search_expenses(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[SearchResult]:
        """Search for expenses using vector similarity."""
        try:
            # Generate query embedding
            embedding_model = self._get_embedding_model()
            query_embedding = embedding_model.encode([query])[0]
            
            # Build SQL query
            sql = """
            SELECT 
                expense_id,
                user_id,
                description,
                merchant,
                expense_amount,
                expense_date,
                1 - (embedding <=> %s) as similarity_score
            FROM expenses
            WHERE 1 - (embedding <=> %s) > %s
            """
            
            params = [query_embedding.tolist(), query_embedding.tolist(), threshold]
            
            if user_id:
                sql += " AND user_id = %s"
                params.append(user_id)
            
            sql += " ORDER BY similarity_score DESC LIMIT %s"
            params.append(limit)
            
            # Execute query
            engine = self._get_db_engine()
            with engine.connect() as conn:
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
                    metadata={}
                ))
            
            return results
            
        except Exception as e:
            raise AIConnectionError(f"Search failed: {str(e)}")
    
    def generate_rag_response(
        self, 
        query: str, 
        context: List[SearchResult],
        user_id: Optional[str] = None,
        language: str = "en"
    ) -> RAGResponse:
        """Generate RAG response using OpenAI."""
        try:
            print(f"\n🤖 OPENAI RAG (with caching):")
            print(f"1. Query: '{query[:60]}...'")
            
            # Check for cached response first
            if self.cache_manager:
                # Convert SearchResult objects to dict format for cache lookup
                search_results_dict = []
                for result in context:
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
                
                cached_response = self.cache_manager.get_cached_response(
                    query, search_results_dict, "openai"
                )
                if cached_response:
                    print(f"2. ✅ Response cache HIT! Returning cached response")
                    return RAGResponse(
                        response=cached_response,
                        sources=context,
                        metadata={
                            'provider': 'openai',
                            'model': self.get_default_model(),
                            'user_id': user_id,
                            'language': language,
                            'cached': True
                        }
                    )
                print(f"2. ❌ Response cache MISS, generating fresh response")
            else:
                print(f"2. No cache manager available, generating fresh response")
            
            # Prepare context
            context_text = self._prepare_context(context)
            
            # Prepare system message
            system_message = f"""You are a helpful AI assistant for expense analysis. 
            You have access to the user's expense data and can help answer questions about their spending patterns.
            
            Please respond in {language} if requested, otherwise use English.
            
            Use the provided expense data to answer questions accurately and helpfully."""
            
            # Prepare user message
            user_message = f"""Query: {query}
            
            Relevant expense data:
            {context_text}
            
            Please provide a helpful response based on the expense data above."""
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            
            # Cache the response for future similar queries
            if self.cache_manager and response_text:
                # Convert SearchResult objects to dict format for caching
                search_results_dict = []
                for result in context:
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
                
                # Use actual token counts from OpenAI response
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                response_tokens = response.usage.completion_tokens if response.usage else 0
                
                self.cache_manager.cache_response(
                    query, response_text, search_results_dict, "openai",
                    prompt_tokens, response_tokens
                )
                print(f"3. ✅ Cached response ({prompt_tokens + response_tokens} tokens)")
            
            return RAGResponse(
                response=response_text,
                sources=context,
                metadata={
                    "model": "gpt-3.5-turbo",
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "language": language
                }
            )
            
        except Exception as e:
            raise AIConnectionError(f"RAG response generation failed: {str(e)}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        try:
            embedding_model = self._get_embedding_model()
            embedding = embedding_model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            raise AIConnectionError(f"Embedding generation failed: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test OpenAI connection."""
        try:
            # Test with a simple completion
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return response.choices[0].message.content is not None
        except Exception:
            return False
    
    def _prepare_context(self, context: List[SearchResult]) -> str:
        """Prepare context text from search results."""
        if not context:
            return "No relevant expense data found."
        
        context_parts = []
        for i, result in enumerate(context, 1):
            context_parts.append(
                f"{i}. {result.description} at {result.merchant} - "
                f"${result.amount:.2f} on {result.date} "
                f"(similarity: {result.similarity_score:.3f})"
            )
        
        return "\n".join(context_parts)
