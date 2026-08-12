"""
LLM Factory for Agents

Provides LangChain-compatible LLM instances based on configured AI provider.
This centralizes LLM creation logic for all agents (receipt, fraud, budget).
"""

import os
from typing import Any

from banko_ai.config.settings import get_config


def get_llm_for_agent(temperature: float = 0.7, model_override: str | None = None) -> Any:
    """
    Get LangChain-compatible LLM instance based on configured AI provider.
    
    Args:
        temperature: LLM temperature setting (0.0-1.0)
        model_override: Use this model instead of the config default
        
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
            api_key = os.getenv('OPENAI_API_KEY') or getattr(config, 'openai_api_key', None)
            if api_key:
                api_key = api_key.strip().replace('\n', '').replace(' ', '')
            else:
                print("⚠️ LLM Factory: OPENAI_API_KEY not found in environment")
            return ChatOpenAI(
                model=model_override or config.openai_model,
                api_key=api_key,
                base_url=os.getenv('OPENAI_BASE_URL') or None,
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
                model_id=model_override or config.aws_model,
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
            # ChatWatsonx talks to the chat endpoint. The old WatsonxLLM used
            # the deprecated /ml/v1/text/generation completion endpoint, which
            # made chat-tuned models leak raw scaffolding into agent replies.
            from langchain_ibm import ChatWatsonx

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

            return ChatWatsonx(
                model_id=model_override or config.watsonx_model,
                url=watsonx_url,
                api_key=config.watsonx_api_key or os.getenv('WATSONX_API_KEY'),
                project_id=config.watsonx_project_id or os.getenv('WATSONX_PROJECT_ID'),
                temperature=temperature,
                max_tokens=2000,
            )
        except ImportError:
            raise ImportError(
                "langchain-ibm is required for Watsonx provider. "
                "Install with: pip install langchain-ibm"
            )
    
    elif config.ai_service == 'ollama':
        from langchain_openai import ChatOpenAI
        host = os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')
        # Ollama serves an OpenAI-compatible endpoint at /v1; the key is a
        # required-but-ignored placeholder.
        return ChatOpenAI(
            model=model_override or config.ollama_model,
            api_key='ollama',
            base_url=f"{host}/v1",
            temperature=temperature,
        )

    elif config.ai_service == 'gemini':
        # Try Vertex AI first (service account), then fall back to Generative AI API (API key)
        google_api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        google_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        google_project = os.getenv('GOOGLE_PROJECT_ID')
        
        if google_creds and google_project:
            try:
                from google.oauth2 import service_account
                from langchain_google_genai import ChatGoogleGenerativeAI
                credentials = service_account.Credentials.from_service_account_file(
                    google_creds,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                selected_model = model_override or config.google_model
                llm = ChatGoogleGenerativeAI(
                    model=selected_model,
                    credentials=credentials,
                    project=google_project,
                    location=os.getenv('GOOGLE_LOCATION', 'us-central1'),
                    vertexai=True,
                    temperature=temperature
                )
                print(f"✅ LLM Factory: Created Gemini LLM via Vertex AI (model={selected_model})")
                return llm
            except Exception as e:
                print(f"⚠️ LLM Factory: Vertex AI failed: {e}, trying API key fallback")
                pass
        
        if google_api_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=model_override or config.google_model,
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
            f"Supported: openai, aws, watsonx, gemini, ollama"
        )


def get_embedding_model():
    """
    Get sentence transformer embedding model.
    
    Returns:
        SentenceTransformer instance
    """
    from banko_ai.utils.embeddings import load_embedding_model
    return load_embedding_model('all-MiniLM-L6-v2')
