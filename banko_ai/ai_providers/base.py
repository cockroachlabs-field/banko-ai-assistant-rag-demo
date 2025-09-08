"""
Base AI provider interface and common functionality.

This module defines the abstract base class for AI providers and common error handling.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


class AIProviderError(Exception):
    """Base exception for AI provider errors."""
    pass


class AIConnectionError(AIProviderError):
    """Exception raised when AI service connection fails."""
    pass


class AIAuthenticationError(AIProviderError):
    """Exception raised when AI service authentication fails."""
    pass


class AIQuotaExceededError(AIProviderError):
    """Exception raised when AI service quota is exceeded."""
    pass


@dataclass
class SearchResult:
    """Result from vector similarity search."""
    expense_id: str
    user_id: str
    description: str
    merchant: str
    amount: float
    date: str
    similarity_score: float
    metadata: Dict[str, Any]


@dataclass
class RAGResponse:
    """Response from RAG (Retrieval-Augmented Generation) query."""
    response: str
    sources: List[SearchResult]
    metadata: Dict[str, Any]


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the AI provider with configuration."""
        self.config = config
        self.current_model = config.get("model", self.get_default_model())
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass
    
    @abstractmethod
    def search_expenses(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[SearchResult]:
        """
        Search for expenses using vector similarity.
        
        Args:
            query: Search query text
            user_id: Optional user ID to filter results
            limit: Maximum number of results to return
            threshold: Minimum similarity score threshold
            
        Returns:
            List of SearchResult objects
        """
        pass
    
    @abstractmethod
    def generate_rag_response(
        self, 
        query: str, 
        context: List[SearchResult],
        user_id: Optional[str] = None,
        language: str = "en"
    ) -> RAGResponse:
        """
        Generate a RAG response using the provided context.
        
        Args:
            query: User query
            context: List of relevant search results
            user_id: Optional user ID
            language: Response language code
            
        Returns:
            RAGResponse object
        """
        pass
    
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for the given text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the AI service.
        
        Returns:
            True if connection is successful, False otherwise
        """
        pass
    
    def get_provider_name(self) -> str:
        """Get the name of this AI provider."""
        return self.__class__.__name__.replace("Provider", "").lower()
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information and status."""
        return {
            "name": self.get_provider_name(),
            "connected": self.test_connection(),
            "current_model": self.current_model,
            "config_keys": list(self.config.keys())
        }
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass
    
    def get_available_models(self) -> List[str]:
        """Get available models for this provider."""
        # Default implementation - can be overridden by providers
        return [self.current_model]
    
    def set_model(self, model: str) -> bool:
        """
        Switch to a different model.
        
        Args:
            model: Model name to switch to
            
        Returns:
            True if model was switched successfully, False otherwise
        """
        available_models = self.get_available_models()
        if model in available_models:
            self.current_model = model
            return True
        return False
    
    def get_current_model(self) -> str:
        """Get the current model."""
        return self.current_model
