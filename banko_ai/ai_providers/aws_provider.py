"""
AWS Bedrock AI provider implementation.

This module provides AWS Bedrock integration for vector search and RAG responses.
"""

import os
import json
from typing import List, Dict, Any, Optional
import boto3
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

from .base import AIProvider, SearchResult, RAGResponse, AIConnectionError, AIAuthenticationError


class AWSProvider(AIProvider):
    """AWS Bedrock AI provider implementation."""
    
    def __init__(self, config: Dict[str, Any], cache_manager=None):
        """Initialize AWS provider."""
        self.access_key_id = config.get("access_key_id")
        self.secret_access_key = config.get("secret_access_key")
        self.region = config.get("region", "us-east-1")
        self.bedrock_client = None
        self.embedding_model = None
        self.db_engine = None
        self.cache_manager = cache_manager
        super().__init__(config)
    
    def _validate_config(self) -> None:
        """Validate AWS configuration."""
        if not self.access_key_id or not self.secret_access_key:
            raise AIAuthenticationError("AWS access key ID and secret access key are required")
        
        # Initialize Bedrock client
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region
            )
        except Exception as e:
            raise AIConnectionError(f"Failed to initialize AWS Bedrock client: {str(e)}")
    
    def get_default_model(self) -> str:
        """Get the default AWS model."""
        return "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    
    def get_available_models(self) -> List[str]:
        """Get available AWS models."""
        return [
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            "us.anthropic.claude-3-opus-20240229-v1:0",
            "us.anthropic.claude-3-sonnet-20240229-v1:0",
            "us.anthropic.claude-3-haiku-20240307-v1:0"
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
            
            # Convert to PostgreSQL vector format
            search_embedding = json.dumps(query_embedding.tolist())
            
            # Build SQL query
            sql = """
            SELECT 
                expense_id,
                user_id,
                description,
                merchant,
                expense_amount,
                expense_date,
                1 - (embedding <-> %s) as similarity_score
            FROM expenses
            WHERE 1 - (embedding <-> %s) > %s
            """
            
            params = [search_embedding, search_embedding, threshold]
            
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
        """Generate RAG response using AWS Bedrock."""
        try:
            print(f"\n🤖 AWS BEDROCK RAG (with caching):")
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
                    query, search_results_dict, "aws"
                )
                if cached_response:
                    print(f"2. ✅ Response cache HIT! Returning cached response")
                    return RAGResponse(
                        response=cached_response,
                        sources=context,
                        metadata={
                            'provider': 'aws',
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
            
            # Prepare the prompt
            prompt = f"""You are Banko, a financial assistant. Answer based on this expense data:

Q: {query}

Data:
{context_text}

Provide helpful insights with numbers, markdown formatting, and actionable advice."""
            
            # Define input parameters for Claude
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
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            # Convert to JSON format
            body = json.dumps(payload)
            
            # Use current model
            model_id = self.current_model
            
            # Invoke model
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=body
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            ai_response = response_body['content'][0]['text']
            
            # Cache the response for future similar queries
            if self.cache_manager and ai_response:
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
                
                # Estimate token usage (rough approximation for AWS)
                prompt_tokens = len(query.split()) * 1.3  # ~1.3 tokens per word
                response_tokens = len(ai_response.split()) * 1.3
                
                self.cache_manager.cache_response(
                    query, ai_response, search_results_dict, "aws",
                    int(prompt_tokens), int(response_tokens)
                )
                print(f"3. ✅ Cached response (est. {int(prompt_tokens + response_tokens)} tokens)")
            
            return RAGResponse(
                response=ai_response,
                sources=context,
                metadata={
                    "model": "claude-3-5-sonnet",
                    "region": self.region,
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
        """Test AWS Bedrock connection."""
        try:
            # Test with a simple completion
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 5,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Hello"}]
                    }
                ]
            }
            
            response = self.bedrock_client.invoke_model(
                modelId=self.current_model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text'] is not None
        except Exception:
            return False
    
    def _prepare_context(self, context: List[SearchResult]) -> str:
        """Prepare context text from search results."""
        if not context:
            return "No relevant expense data found."
        
        context_parts = []
        for i, result in enumerate(context, 1):
            context_parts.append(
                f"• **{result.description}** at {result.merchant}: ${result.amount:.2f} "
                f"({result.date}) - similarity: {result.similarity_score:.3f}"
            )
        
        return "\n".join(context_parts)
