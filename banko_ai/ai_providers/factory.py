"""
AI Provider Factory for creating provider instances.

This module provides a factory pattern for creating AI provider instances
based on configuration.
"""

from typing import Dict, Any, Type
from .base import AIProvider, AIProviderError
from .openai_provider import OpenAIProvider
from .aws_provider import AWSProvider
from .watsonx_provider import WatsonxProvider
from .gemini_provider import GeminiProvider


class AIProviderFactory:
    """Factory for creating AI provider instances."""
    
    _providers: Dict[str, Type[AIProvider]] = {
        "openai": OpenAIProvider,
        "aws": AWSProvider,
        "watsonx": WatsonxProvider,
        "gemini": GeminiProvider,
    }
    
    @classmethod
    def create_provider(cls, service_name: str, config: Dict[str, Any], cache_manager=None) -> AIProvider:
        """
        Create an AI provider instance.
        
        Args:
            service_name: Name of the AI service (openai, aws, watsonx, gemini)
            config: Configuration dictionary for the provider
            cache_manager: Optional cache manager instance
            
        Returns:
            AIProvider instance
            
        Raises:
            AIProviderError: If the service is not supported
        """
        service_name = service_name.lower()
        
        if service_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise AIProviderError(
                f"Unsupported AI service: {service_name}. "
                f"Available services: {available}"
            )
        
        provider_class = cls._providers[service_name]
        
        try:
            # Pass cache_manager to all providers that support it
            if hasattr(provider_class, '__init__'):
                # Check if the provider's __init__ method accepts cache_manager parameter
                import inspect
                sig = inspect.signature(provider_class.__init__)
                if 'cache_manager' in sig.parameters:
                    return provider_class(config, cache_manager)
                else:
                    return provider_class(config)
            else:
                return provider_class(config)
        except Exception as e:
            raise AIProviderError(
                f"Failed to create {service_name} provider: {str(e)}"
            )
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available AI providers."""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AIProvider]) -> None:
        """
        Register a new AI provider.
        
        Args:
            name: Name of the provider
            provider_class: Provider class that implements AIProvider
        """
        cls._providers[name.lower()] = provider_class
