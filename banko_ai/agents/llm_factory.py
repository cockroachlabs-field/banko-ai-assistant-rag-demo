"""
LLM Factory for Agents

Provides LangChain-compatible LLM instances based on configured AI provider.
This centralizes LLM creation logic for all agents (receipt, fraud, budget).
"""

import os
from typing import Any

from banko_ai.config.settings import get_config


def get_llm_for_agent(temperature: float = 0.7) -> Any:
    """
    Get LangChain-compatible LLM instance based on configured AI provider.
    
    Args:
        temperature: LLM temperature setting (0.0-1.0)
        
    Returns:
        LangChain LLM instance
        
    Raises:
        ValueError: If AI service is not supported
        ImportError: If required langchain package is not installed
    """
    config = get_config()
    
    if config.ai_service == 'openai':
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.openai_model,
                api_key=os.getenv('OPENAI_API_KEY'),
                temperature=temperature
            )
        except ImportError:
            raise ImportError(
                "langchain-openai is required for OpenAI provider. "
                "Install with: pip install langchain-openai"
            )
    
    elif config.ai_service == 'aws':
        try:
            from langchain_aws import ChatBedrock
            return ChatBedrock(
                model_id=config.aws_model,
                region_name=os.getenv('AWS_REGION', 'us-east-1'),
                model_kwargs={'temperature': temperature}
            )
        except ImportError:
            raise ImportError(
                "langchain-aws is required for AWS provider. "
                "Install with: pip install langchain-aws"
            )
    
    elif config.ai_service == 'watsonx':
        try:
            from langchain_ibm import WatsonxLLM
            
            # Get Watsonx base URL (not the full endpoint path)
            # langchain_ibm expects base URL like: https://us-south.ml.cloud.ibm.com
            watsonx_url = os.getenv('WATSONX_API_URL') or os.getenv('WATSONX_URL')
            
            # If not set, use default base URL (US South region)
            if not watsonx_url:
                watsonx_url = 'https://us-south.ml.cloud.ibm.com'
            
            # Strip off any path/query parameters if present (langchain_ibm adds them)
            if '/ml/v1' in watsonx_url or '?' in watsonx_url:
                # Extract just the base URL
                from urllib.parse import urlparse
                parsed = urlparse(watsonx_url)
                watsonx_url = f"{parsed.scheme}://{parsed.netloc}"
            
            return WatsonxLLM(
                model_id=config.watsonx_model,
                url=watsonx_url,
                apikey=config.watsonx_api_key or os.getenv('WATSONX_API_KEY'),
                project_id=config.watsonx_project_id or os.getenv('WATSONX_PROJECT_ID'),
                params={
                    'temperature': temperature,
                    'max_new_tokens': 2000,
                    'min_new_tokens': 10,
                    'decoding_method': 'sample',  # Changed from 'greedy' for better JSON generation
                    'repetition_penalty': 1.0,
                    'top_k': 50,
                    'top_p': 0.95
                }
            )
        except ImportError:
            raise ImportError(
                "langchain-ibm is required for Watsonx provider. "
                "Install with: pip install langchain-ibm"
            )
    
    elif config.ai_service == 'gemini':
        # Try Vertex AI first (service account), then fall back to Generative AI API (API key)
        google_api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        google_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        google_project = os.getenv('GOOGLE_PROJECT_ID')
        
        if google_creds and google_project:
            try:
                import google.auth
                from langchain_google_genai import ChatGoogleGenerativeAI
                credentials, _ = google.auth.default()
                return ChatGoogleGenerativeAI(
                    model=config.google_model,
                    credentials=credentials,
                    project=google_project,
                    temperature=temperature
                )
            except Exception:
                pass
        
        if google_api_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=config.google_model,
                    google_api_key=google_api_key,
                    temperature=temperature
                )
            except ImportError:
                raise ImportError(
                    "langchain-google-genai is required for Gemini provider. "
                    "Install with: pip install langchain-google-genai"
                )
        
        raise ValueError(
            "Gemini requires either GOOGLE_APPLICATION_CREDENTIALS + GOOGLE_PROJECT_ID "
            "(Vertex AI) or GOOGLE_API_KEY (Generative AI API)"
        )
    
    else:
        raise ValueError(
            f"Unsupported AI service: {config.ai_service}. "
            f"Supported: openai, aws, watsonx, gemini"
        )


def get_embedding_model():
    """
    Get sentence transformer embedding model.
    
    Returns:
        SentenceTransformer instance
    """
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2')
